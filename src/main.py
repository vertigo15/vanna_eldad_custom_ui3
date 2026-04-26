"""FastAPI application for Jeen Insights.

The app no longer owns a single agent for a single data source. It owns an
`AgentRegistry` that lazily builds one agent per `source_key` (active
connection from `public.metadata_sources`). Every endpoint that operates on a
dataset must include `connection` (= source_key) on the request.
"""

from __future__ import annotations

import json
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent import AgentRegistry, JeenInsightsAgent
from src.agent.conversation_history import ConversationHistoryService
from src.agent.llm_service import AzureOpenAILlmService
from src.agent.user_resolver import SimpleUserResolver
from src.config import settings
from src.connections import ConnectionNotFound, ConnectionService, UnsupportedConnectionType
from src.metadata import MetadataLoader, close_metadata_pool, get_metadata_pool

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level handles populated on startup.
agent_registry: Optional[AgentRegistry] = None
metadata_loader: Optional[MetadataLoader] = None
connection_service: Optional[ConnectionService] = None
history_service: Optional[ConversationHistoryService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_registry, metadata_loader, connection_service, history_service

    logger.info("🚀 Starting Jeen Insights...")
    pool = await get_metadata_pool()

    metadata_loader = MetadataLoader(pool)
    connection_service = ConnectionService(pool)
    history_service = ConversationHistoryService(pool)

    llm_service = AzureOpenAILlmService(
        api_key=settings.AZURE_OPENAI_API_KEY,
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )

    agent_registry = AgentRegistry(
        llm_service=llm_service,
        metadata_loader=metadata_loader,
        connection_service=connection_service,
        history_service=history_service,
        user_resolver=SimpleUserResolver(),
    )

    logger.info("✅ Jeen Insights ready")
    try:
        yield
    finally:
        logger.info("👋 Shutting down Jeen Insights")
        if agent_registry:
            await agent_registry.close()
        await close_metadata_pool()


app = FastAPI(
    title="Jeen Insights",
    description=(
        "Natural-language analytics over registered data connections, powered by "
        "Azure OpenAI and curated metadata from the shared Jeen metadata DB."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
async def _resolve_agent(source_key: Optional[str]) -> JeenInsightsAgent:
    if not agent_registry:
        raise HTTPException(status_code=503, detail="Service not initialized")
    if not source_key:
        raise HTTPException(
            status_code=400,
            detail="Missing 'connection' (source_key). Pick one from /api/connections.",
        )
    try:
        return await agent_registry.get_agent(source_key)
    except ConnectionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except UnsupportedConnectionType as e:
        raise HTTPException(status_code=501, detail=str(e)) from e


def _extract_json_object(raw: str) -> Optional[Dict[str, Any]]:
    """Best-effort decoder for LLM-produced ECharts/JSON payloads.

    Strategy:
    1. Strip markdown fences and outer whitespace.
    2. Trim to the outermost {...}.
    3. Try strict json.loads.
    4. If that fails, sanitize common LLM artefacts (JS comments, trailing
       commas, formatter function bodies) and retry.
    """
    if not raw:
        return None
    text = raw.strip()
    # Strip ```json or ``` fences
    if text.startswith("```"):
        # remove the opening fence (and optional language tag)
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", text)
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
    # Trim to outermost braces
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("Strict JSON parse failed (%s); attempting cleanup", e)

    cleaned = _sanitize_llm_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Lenient JSON parse failed too: %s", e)
        logger.debug("Cleaned LLM text was: %s", cleaned[:1500])
        return None


def _sanitize_llm_json(text: str) -> str:
    """Strip JS comments, trailing commas, and JS function bodies."""
    # Drop // line comments
    text = re.sub(r"//[^\n]*", "", text)
    # Drop /* block comments */
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # Replace JS function expressions used in formatter / etc. with the literal
    # ECharts placeholder string '{value}' so the JSON is still valid.
    text = re.sub(
        r"function\s*\([^)]*\)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
        '"{value}"',
        text,
        flags=re.S,
    )
    # Drop trailing commas: ,] or ,}
    text = re.sub(r",(\s*[\]}])", r"\1", text)
    return text.strip()


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str
    connection: str
    session_id: Optional[UUID] = None
    user_context: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    question: str
    query_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    sql: Optional[str]
    results: Optional[Dict[str, Any]]
    prompt: Optional[Dict[str, Any]] = None
    error: Optional[str]


class ColumnInfo(BaseModel):
    name: str
    type: str


class GenerateChartRequest(BaseModel):
    connection: str
    columns: List[ColumnInfo]
    column_names: List[str]
    sample_data: List[List[Any]]
    all_data: Optional[List[List[Any]]] = None
    chart_type: Optional[str] = "auto"


class GenerateChartResponse(BaseModel):
    chart_config: Dict[str, Any]
    chart_type: str
    prompt: Optional[str] = None
    system_message: Optional[str] = None


class GenerateInsightsRequest(BaseModel):
    connection: str
    dataset: Dict[str, Any]
    question: str
    query_id: Optional[UUID] = None


class GenerateInsightsResponse(BaseModel):
    summary: str
    findings: List[str]
    suggestions: List[str]
    prompt: Optional[str] = None
    system_message: Optional[str] = None


class GenerateProfileRequest(BaseModel):
    dataset: Dict[str, Any]
    report_type: str = "ydata"


class EnhanceChartRequest(BaseModel):
    connection: str
    columns: List[ColumnInfo]
    sample_data: List[List[Any]]
    chart_type: str
    current_config: Dict[str, Any]


class FeedbackRequest(BaseModel):
    query_id: UUID
    feedback: str
    corrected_sql: Optional[str] = None
    notes: Optional[str] = None


class PinQuestionRequest(BaseModel):
    connection: str
    user_id: str = "default"
    question: str


class SuggestQuestionsRequest(BaseModel):
    connection: str
    partial: str
    recent_questions: Optional[List[str]] = None
    table_names: Optional[List[str]] = None


# ----------------------------------------------------------------------
# Public root + health
# ----------------------------------------------------------------------
@app.get("/")
async def root():
    return {"service": "Jeen Insights", "version": app.version, "status": "running"}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "registry_ready": agent_registry is not None,
        "services": {
            "llm": f"Azure OpenAI {settings.AZURE_OPENAI_DEPLOYMENT_NAME}",
            "metadata_db": f"{settings.METADATA_DB_HOST}/{settings.METADATA_DB_NAME}",
        },
    }


# ----------------------------------------------------------------------
# Connection management
# ----------------------------------------------------------------------
@app.get("/api/connections")
async def list_connections():
    if not connection_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    connections = await connection_service.list_connections()
    return {"connections": [c.to_public_dict() for c in connections]}


@app.get("/api/connections/{source_key}")
async def get_connection(source_key: str):
    if not connection_service or not metadata_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        connection = await connection_service.get_connection(source_key)
    except ConnectionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    summary = await metadata_loader.metadata_summary(source_key)
    return {**connection.to_public_dict(), "metadata_summary": summary}


@app.post("/api/connections/{source_key}/refresh-metadata")
async def refresh_connection_metadata(source_key: str):
    if not metadata_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    metadata_loader.invalidate(source_key)
    return {"status": "ok", "message": f"Metadata cache invalidated for {source_key}"}


# ----------------------------------------------------------------------
# Autocomplete: Tier 2 catalog (knowledge_pairs questions)
# ----------------------------------------------------------------------
@app.get("/api/knowledge-questions")
async def get_knowledge_questions(
    connection: str = Query(..., description="source_key of the active connection"),
):
    if not metadata_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    items = await metadata_loader.load_knowledge_questions(connection)
    return {
        "connection": connection,
        "questions": items,
        "truncated": len(items) >= 2000,  # server cap; UI may want to hint
    }


# ----------------------------------------------------------------------
# Autocomplete: `#` trigger — columns for the active connection
# ----------------------------------------------------------------------
@app.get("/api/knowledge-columns")
async def get_knowledge_columns(
    connection: str = Query(..., description="source_key of the active connection"),
    table: Optional[str] = Query(None, description="Optional: scope to one table"),
):
    if not metadata_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    items = await metadata_loader.load_columns(connection, table)
    return {
        "connection": connection,
        "table": table,
        "columns": items,
        "truncated": (len(items) >= 5000 if not table else len(items) >= 2000),
    }


# ----------------------------------------------------------------------
# Autocomplete: Tier 3 LLM
# ----------------------------------------------------------------------
_AUTOCOMPLETE_PROMPT_PATH = (
    Path(__file__).resolve().parent / "agent" / "prompts" / "autocomplete_suggestions.md"
)
_MAX_PARTIAL_CHARS = 200
_MAX_TABLES_INJECTED = 200
_MAX_RECENT_INJECTED = 10
_MAX_RECENT_CHARS = 1500


def _load_autocomplete_prompt() -> str:
    """Re-read the externalised prompt on every call so editing the .md file
    has zero deploy cost in dev."""
    return _AUTOCOMPLETE_PROMPT_PATH.read_text(encoding="utf-8")


# Accept any of these key spellings from the LLM and coerce to {wrong, right}.
_CORRECTION_WRONG_KEYS = ("wrong", "from", "old", "misspelled", "typo", "input")
_CORRECTION_RIGHT_KEYS = ("right", "to", "new", "correct", "correction", "fixed")


def _normalise_corrections(items: Any) -> List[Dict[str, str]]:
    """Coerce a parsed `corrections` payload into a clean list of {wrong, right}.

    Accepts strings, {wrong,right}, {from,to}, {old,new}, {misspelled,correct},
    arrow-strings like "prooduct -> product", and dicts mapping wrong->right.
    Drops empty / self-equal / duplicate entries; caps at 4.
    """
    out: List[Dict[str, str]] = []
    if not isinstance(items, list):
        return out
    seen: set[str] = set()
    for c in items:
        wrong = right = ""
        if isinstance(c, dict):
            for k in _CORRECTION_WRONG_KEYS:
                if c.get(k):
                    wrong = str(c.get(k)).strip()
                    break
            for k in _CORRECTION_RIGHT_KEYS:
                if c.get(k):
                    right = str(c.get(k)).strip()
                    break
            # Single-pair dict like {"prooduct": "product"}.
            if not (wrong and right) and len(c) == 1:
                k, v = next(iter(c.items()))
                if isinstance(k, str) and isinstance(v, str):
                    wrong, right = k.strip(), v.strip()
        elif isinstance(c, str):
            text = c.strip()
            for sep in ("->", "→", " => ", " : ", " — ", " - "):
                if sep in text:
                    a, _, b = text.partition(sep)
                    wrong, right = a.strip(" `'\""), b.strip(" `'\"")
                    break
            if not (wrong and right):
                # A bare string is only a useful correction if we can't tell
                # what was wrong; skip it (the UI has no anchor to replace).
                continue
        if not wrong or not right:
            continue
        if wrong.lower() == right.lower():
            continue
        key = right.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"wrong": wrong, "right": right})
        if len(out) >= 4:
            break
    return out


@app.post("/api/suggest-questions")
async def suggest_questions(request: SuggestQuestionsRequest):
    """Tier 3 autocomplete: ask the LLM for completions when the cheap tiers
    returned nothing. Server-side guards: connection required, partial must be
    >= 10 chars (mirrors client gate), small token budget, JSON-only output.
    """
    partial = (request.partial or "").strip()
    if len(partial) < 10:
        raise HTTPException(
            status_code=400,
            detail="`partial` must be at least 10 characters.",
        )

    agent = await _resolve_agent(request.connection)

    # Build the table list. Trust the client's hint if it sent one (already
    # filtered to the active connection); otherwise derive from the metadata
    # bundle we cache for the system prompt.
    table_names = request.table_names or []
    if not table_names:
        bundle = await agent.metadata_loader.load_all(agent.source_key)
        # `tables` lines look like "- <table> - <description>"; pull just the name.
        for line in bundle.get("tables", "").splitlines():
            line = line.strip()
            if line.startswith("- "):
                head = line[2:].split(" - ", 1)[0].strip()
                if head:
                    table_names.append(head)
    table_names = table_names[:_MAX_TABLES_INJECTED]

    recent = (request.recent_questions or [])[:_MAX_RECENT_INJECTED]
    recent_blob = "\n".join(f"- {q}" for q in recent if q)[:_MAX_RECENT_CHARS] or "(none)"

    available_tables_blob = "\n".join(f"- {t}" for t in table_names) or "(no tables)"

    template = _load_autocomplete_prompt()
    prompt = template.format(
        partial=partial[:_MAX_PARTIAL_CHARS],
        available_tables=available_tables_blob,
        recent_questions=recent_blob,
        connection_display_name=agent.display_name,
        database_type=agent.database_type,
    )

    try:
        response = await agent.llm.generate(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": partial[:_MAX_PARTIAL_CHARS]},
            ],
            temperature=0.2,
            max_tokens=200,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Autocomplete LLM call failed")
        # Don't 500 — autocomplete is non-critical; return an empty result.
        return {"suggestions": [], "corrections": [], "error": str(e)}

    raw = response.get("content") or ""
    parsed = _extract_json_object(raw)
    if not isinstance(parsed, dict):
        logger.warning("Autocomplete: unparseable LLM response (%s chars)", len(raw))
        return {"suggestions": [], "corrections": []}

    suggestions = parsed.get("suggestions") or []
    corrections = parsed.get("corrections") or []
    # Defensive shape coercion + truncation.
    if not isinstance(suggestions, list):
        suggestions = []
    if not isinstance(corrections, list):
        corrections = []
    suggestions = [str(s).strip() for s in suggestions if s and str(s).strip()][:4]
    cleaned_corrections = _normalise_corrections(corrections)
    return {"suggestions": suggestions, "corrections": cleaned_corrections}


# ----------------------------------------------------------------------
# Query / data exploration
# ----------------------------------------------------------------------
@app.post("/api/query", response_model=QueryResponse)
async def query_database(request: QueryRequest):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    agent = await _resolve_agent(request.connection)
    try:
        result = await agent.process_question(
            question=request.question,
            session_id=request.session_id,
            user_context=request.user_context or {},
        )
        return QueryResponse(**result)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("Error processing question")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/tables")
async def list_tables(connection: str = Query(..., description="source_key of the active connection")):
    agent = await _resolve_agent(connection)
    try:
        tables = await agent.sql_runner.list_tables()
        return {"tables": tables}
    except Exception as e:  # noqa: BLE001
        logger.exception("Error listing tables")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/schema/{table_name}")
async def get_table_schema(
    table_name: str,
    connection: str = Query(..., description="source_key of the active connection"),
):
    agent = await _resolve_agent(connection)
    try:
        schema = await agent.sql_runner.get_table_schema(table_name)
        if not schema:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
        return {"table": table_name, "schema": schema}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("Error getting schema")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ----------------------------------------------------------------------
# Recent / pinned questions
# ----------------------------------------------------------------------
@app.get("/api/user/recent-questions")
async def get_user_recent_questions(
    connection: str = Query(...),
    user_id: str = "default",
    limit: int = 15,
):
    if not history_service:
        raise HTTPException(status_code=503, detail="History service unavailable")
    questions = await history_service.get_user_recent_questions(
        user_id=user_id, source_key=connection, limit=limit
    )
    return {"questions": questions}


@app.get("/api/user/pinned-questions")
async def get_user_pinned_questions(connection: str = Query(...), user_id: str = "default"):
    if not history_service:
        raise HTTPException(status_code=503, detail="History service unavailable")
    questions = await history_service.get_user_pinned_questions(
        user_id=user_id, source_key=connection
    )
    return {"questions": questions}


@app.post("/api/user/pin-question")
async def pin_question(request: PinQuestionRequest):
    if not history_service:
        raise HTTPException(status_code=503, detail="History service unavailable")
    success = await history_service.pin_question(
        user_id=request.user_id,
        source_key=request.connection,
        question=request.question,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to pin question")
    return {"success": True, "message": "Question pinned"}


@app.post("/api/user/unpin-question")
async def unpin_question(request: PinQuestionRequest):
    if not history_service:
        raise HTTPException(status_code=503, detail="History service unavailable")
    success = await history_service.unpin_question(
        user_id=request.user_id,
        source_key=request.connection,
        question=request.question,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to unpin question")
    return {"success": True, "message": "Question unpinned"}


# ----------------------------------------------------------------------
# Insights / charting / profiling
# ----------------------------------------------------------------------
@app.post("/api/generate-insights", response_model=GenerateInsightsResponse)
async def generate_insights_endpoint(request: GenerateInsightsRequest):
    agent = await _resolve_agent(request.connection)
    logger.info("Generating insights for: %s", request.question[:50])
    try:
        from src.agent.insight_service import generate_insights

        # Use the curated metadata bundle as 'context' instead of the old RAG dict.
        bundle = await agent.metadata_loader.load_all(agent.source_key)
        context = {"documentation": [bundle.get("business_terms", "")]}

        start = time.time()
        insights = await generate_insights(
            dataset=request.dataset,
            context=context,
            original_question=request.question,
            llm_service=agent.llm,
        )
        exec_time_ms = int((time.time() - start) * 1000)

        if history_service and request.query_id:
            try:
                await history_service.add_insight(
                    query_id=request.query_id,
                    insight_type="summary",
                    content=insights.get("summary", "Analysis complete"),
                    llm_model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    llm_execution_time_ms=exec_time_ms,
                    tokens_input=insights.get("usage", {}).get("prompt_tokens", 0),
                    tokens_output=insights.get("usage", {}).get("completion_tokens", 0),
                )
                for finding in insights.get("findings", []):
                    await history_service.add_insight(
                        query_id=request.query_id,
                        insight_type="finding",
                        content=finding,
                        llm_model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    )
                for suggestion in insights.get("suggestions", []):
                    await history_service.add_insight(
                        query_id=request.query_id,
                        insight_type="suggestion",
                        content=suggestion,
                        llm_model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    )
            except Exception:  # noqa: BLE001
                logger.exception("Failed to log insights to history")

        return GenerateInsightsResponse(
            summary=insights.get("summary", "Analysis complete"),
            findings=insights.get("findings", []),
            suggestions=insights.get("suggestions", []),
            prompt=insights.get("prompt"),
            system_message=insights.get("system_message"),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Insights generation error")
        return GenerateInsightsResponse(
            summary="Unable to generate insights",
            findings=[],
            suggestions=[],
        )


@app.post("/api/generate-profile")
async def generate_profile_endpoint(request: GenerateProfileRequest):
    report_type = request.report_type.lower()
    logger.info("Generating data profile report using: %s", report_type)
    try:
        if report_type == "sweetviz":
            from src.agent.sweetviz_service import generate_sweetviz_report

            html_report = await generate_sweetviz_report(request.dataset)
        else:
            from src.agent.profiling_service import generate_profile_report

            html_report = await generate_profile_report(request.dataset)
        return {"html": html_report}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.exception("Profile generation error")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/generate-chart", response_model=GenerateChartResponse)
async def generate_chart(request: GenerateChartRequest):
    agent = await _resolve_agent(request.connection)
    chart_type_param = request.chart_type or "auto"

    system_prompt = (
        "You are a data visualization expert specializing in Apache ECharts.\n\n"
        "Analyze the data and return ONLY a valid ECharts configuration as JSON.\n\n"
        "STRICT JSON REQUIREMENTS:\n"
        "- Return pure JSON only \u2014 no explanation, no markdown fences (no ```), "
        "no comments (// or /* */), no JavaScript code.\n"
        "- All keys and string values must be double-quoted.\n"
        "- DO NOT use JavaScript function expressions anywhere (no "
        "`function (value) { ... }`). For formatters, use ECharts template strings "
        "such as \"{value}\", \"{c}\", \"{b}: {c}\", or \"{value}M\". If you need K/M/B "
        "abbreviations, pre-scale the data and put the unit in the axis label or in the "
        "formatter template (e.g. \"{value}K\").\n"
        "- No trailing commas. No undefined / NaN / single quotes. Use null for missing values.\n\n"
        "DESIGN GUIDELINES:\n"
        "- Choose an appropriate chart type for the data.\n"
        "- Apply smart number formatting (K/M/B abbreviations) via template strings.\n"
        "- Add a meaningful title and clear axis labels.\n"
        "- Include polished tooltips using template strings.\n"
        "- Ensure title and legend never overlap."
    )
    chart_type_instruction = (
        ""
        if chart_type_param == "auto"
        else (
            f"\n\nThe user has explicitly selected: {chart_type_param.upper()} CHART. "
            "You MUST return that chart type."
        )
    )
    user_prompt = (
        f"Create a chart visualization for this data.{chart_type_instruction}\n\n"
        f"Column Names:\n{json.dumps(request.column_names)}\n\n"
        "Column Information (with detected types):\n"
        + "\n".join(f"- {c.name} ({c.type})" for c in request.columns)
        + "\n\nData (first "
        + str(len(request.sample_data))
        + " rows):\n"
        + json.dumps(request.sample_data, indent=2)
        + "\n\nReturn ONLY the ECharts configuration JSON. No explanatory text."
    )

    try:
        response = await agent.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=4096,
        )
        raw = response.get("content") or ""
        chart_config = _extract_json_object(raw)
        if chart_config is None:
            logger.error(
                "Chart LLM response was not parseable JSON. First 500 chars: %s",
                raw[:500],
            )
            raise HTTPException(
                status_code=500,
                detail="LLM did not return valid JSON for the chart configuration. Try again.",
            )
        if not isinstance(chart_config, dict) or "series" not in chart_config:
            logger.error("Chart config missing 'series' field. Keys: %s", list(chart_config.keys()) if isinstance(chart_config, dict) else type(chart_config))
            raise HTTPException(status_code=500, detail="Chart config missing 'series' field")

        chart_type = "bar"
        series = chart_config.get("series") or []
        if series:
            chart_type = series[0].get("type", "bar")

        return GenerateChartResponse(
            chart_config=chart_config,
            chart_type=chart_type,
            prompt=user_prompt,
            system_message=system_prompt,
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("Chart generation error")
        raise HTTPException(status_code=500, detail=f"Chart generation failed: {e}") from e


@app.post("/api/enhance-chart")
async def enhance_chart_endpoint(request: EnhanceChartRequest):
    agent = await _resolve_agent(request.connection)
    system_prompt = (
        "You are a data visualization expert specializing in Apache ECharts. "
        "Enhance the provided basic ECharts config: meaningful title, smart "
        "number formatting (K/M/B), better colors, clear axis labels, polished "
        "tooltips. Return ONLY valid JSON, no markdown fences, no explanations."
    )
    user_prompt = (
        f"Enhance this {request.chart_type} chart configuration.\n\n"
        "Column Information:\n"
        + "\n".join(f"- {c.name} ({c.type})" for c in request.columns)
        + "\n\nSample Data (first few rows):\n"
        + json.dumps(request.sample_data[:5], indent=2)
        + "\n\nCurrent Basic Configuration:\n"
        + json.dumps(request.current_config, indent=2)
        + "\n\nReturn ONLY the JSON configuration, no other text."
    )
    try:
        response = await agent.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        raw = response.get("content") or ""
        enhanced_config = _extract_json_object(raw)
        if enhanced_config is None or not isinstance(enhanced_config, dict):
            logger.error(
                "Enhance-chart LLM response was not parseable JSON. First 500 chars: %s",
                raw[:500],
            )
            raise HTTPException(
                status_code=500,
                detail="LLM did not return valid JSON for the chart enhancement.",
            )
        return {"enhanced_config": enhanced_config}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("Chart enhancement error")
        raise HTTPException(status_code=500, detail=f"Chart enhancement failed: {e}") from e


# ----------------------------------------------------------------------
# Feedback / history
# ----------------------------------------------------------------------
@app.post("/api/feedback")
async def record_feedback(request: FeedbackRequest):
    if not history_service:
        raise HTTPException(status_code=503, detail="History service unavailable")
    await history_service.record_feedback(
        query_id=request.query_id,
        user_feedback=request.feedback,
        corrected_sql=request.corrected_sql,
        feedback_notes=request.notes,
    )
    return {"status": "success", "message": "Feedback recorded"}


@app.get("/api/conversation/{session_id}")
async def get_conversation_history(session_id: UUID, include_insights: bool = True):
    if not history_service:
        raise HTTPException(status_code=503, detail="History service unavailable")
    return await history_service.get_conversation_history(
        session_id=session_id, include_insights=include_insights
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
