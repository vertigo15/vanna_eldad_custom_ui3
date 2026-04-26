"""Jeen Insights agent: text-to-SQL orchestrator.

The agent fetches curated metadata from the shared metadata DB at the start
of every question (via `MetadataLoader`), substitutes it into the system
prompt, calls the LLM, executes the resulting SQL against the user-selected
data source, and writes a full lifecycle record to `insights_*` tables.

`AgentRegistry` lazily builds one `JeenInsightsAgent` per `source_key` and
shares the heavy collaborators (LLM service, metadata pool, history service,
connection service) across them.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from src.agent.conversation_history import ConversationHistoryService
from src.agent.llm_service import AzureOpenAILlmService
from src.agent.user_resolver import SimpleUserResolver
from src.config import settings
from src.connections import Connection, ConnectionService
from src.metadata import MetadataLoader
from src.tools.sql_tool import PostgresSqlRunner, RunSqlTool

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "prompts" / "jeen_insights_system.md"
)


def _load_prompt_template() -> str:
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Agent
# ----------------------------------------------------------------------
class JeenInsightsAgent:
    """Per-connection text-to-SQL agent."""

    def __init__(
        self,
        *,
        connection: Connection,
        sql_runner: PostgresSqlRunner,
        llm_service: AzureOpenAILlmService,
        metadata_loader: MetadataLoader,
        history_service: ConversationHistoryService,
        user_resolver: SimpleUserResolver,
        prompt_template: str,
    ):
        self.connection = connection
        self.source_key = connection.source_key
        self.display_name = connection.display_name
        self.database_type = connection.database_type
        self.sql_runner = sql_runner
        self.llm = llm_service
        self.metadata_loader = metadata_loader
        self.history = history_service
        self.user_resolver = user_resolver
        self.sql_tool = RunSqlTool(sql_runner)
        self._prompt_template = prompt_template

    async def process_question(
        self,
        *,
        question: str,
        session_id: Optional[UUID] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not session_id:
            session_id = uuid4()

        query_id: Optional[UUID] = None
        llm_latency_ms: Optional[int] = None

        try:
            user = await self.user_resolver.resolve_user(user_context or {})

            metadata_bundle = await self.metadata_loader.load_all(self.source_key)
            conversation_context = await self._fetch_conversation_context(session_id)

            query_id = await self.history.log_query(
                user_id=user.id,
                source_key=self.source_key,
                session_id=session_id,
                natural_language_query=question,
                dataset_id=self.source_key,
                rag_context=self._summarize_metadata(metadata_bundle),
            )

            system_prompt = self._build_system_prompt(metadata_bundle)

            messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
            for prev_qa in conversation_context:
                if prev_qa.get("natural_language_query") and prev_qa.get("generated_sql"):
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Generate SQL for: {prev_qa['natural_language_query']}",
                        }
                    )
                    messages.append(
                        {
                            "role": "assistant",
                            "content": (
                                "I'll generate SQL for that.\n\n"
                                f"SQL:\n{prev_qa['generated_sql']}"
                            ),
                        }
                    )
            messages.append({"role": "user", "content": f"Generate SQL for: {question}"})

            tools = [self.sql_tool.get_schema()]

            structured_prompt = {
                "tables": metadata_bundle.get("tables", ""),
                "columns": metadata_bundle.get("columns", ""),
                "relationships": metadata_bundle.get("relationships", ""),
                "sources": metadata_bundle.get("sources", ""),
                "knowledge_pairs": metadata_bundle.get("knowledge_pairs", ""),
                "business_terms": metadata_bundle.get("business_terms", ""),
                "tool_description": tools[0] if tools else None,
                "conversation_history": [
                    {
                        "question": prev.get("natural_language_query"),
                        "sql": prev.get("generated_sql"),
                    }
                    for prev in conversation_context
                    if prev.get("natural_language_query") and prev.get("generated_sql")
                ],
                "current_question": question,
                "full_text": system_prompt,
                "connection": {
                    "source_key": self.source_key,
                    "display_name": self.display_name,
                    "database_type": self.database_type,
                },
            }

            llm_start = time.time()
            response = await self.llm.generate(
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
                tools=tools,
            )
            llm_latency_ms = int((time.time() - llm_start) * 1000)

            result: Dict[str, Any] = {
                "question": question,
                "query_id": query_id,
                "session_id": session_id,
                "sql": None,
                "results": None,
                "prompt": structured_prompt,
                "error": None,
            }

            sql = self._extract_sql(response)
            if sql:
                result["sql"] = sql
                await self.history.update_llm_response(
                    query_id=query_id,
                    generated_sql=sql,
                    llm_model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    llm_latency_ms=llm_latency_ms or 0,
                    tokens_used=response.get("usage", {}).get("total_tokens", 0),
                )

                exec_start = time.time()
                query_result = await self.sql_runner.run_sql(sql)
                exec_time_ms = int((time.time() - exec_start) * 1000)
                result["results"] = query_result

                if "error" in query_result:
                    await self.history.update_execution(
                        query_id=query_id,
                        execution_status="error",
                        execution_time_ms=exec_time_ms,
                        row_count=0,
                        result_preview=None,
                        error_message=query_result["error"],
                    )
                    result["error"] = query_result["error"]
                else:
                    rows = query_result.get("rows", [])
                    await self.history.update_execution(
                        query_id=query_id,
                        execution_status="success",
                        execution_time_ms=exec_time_ms,
                        row_count=len(rows),
                        result_preview=rows[:10] if rows else None,
                        error_message=None,
                    )

            return result

        except Exception as e:  # noqa: BLE001
            logger.exception("Error processing question")
            if query_id:
                try:
                    await self.history.update_execution(
                        query_id=query_id,
                        execution_status="error",
                        execution_time_ms=None,
                        row_count=0,
                        result_preview=None,
                        error_message=str(e),
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to log error to history")
            return {
                "question": question,
                "query_id": query_id,
                "session_id": session_id,
                "sql": None,
                "results": None,
                "prompt": None,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _fetch_conversation_context(self, session_id: UUID) -> List[Dict[str, Any]]:
        try:
            ctx = await self.history.get_conversation_context(
                session_id=session_id, limit=2
            )
            ctx.reverse()  # chronological order, oldest first
            if ctx:
                logger.info(
                    "🧠 Short-term memory: %d previous Q&As loaded for %s",
                    len(ctx),
                    self.source_key,
                )
            return ctx
        except Exception:
            logger.exception("Failed to fetch conversation context")
            return []

    def _build_system_prompt(self, metadata_bundle: Dict[str, str]) -> str:
        return self._prompt_template.format(
            connection_display_name=self.display_name,
            database_type=self.database_type,
            tables=metadata_bundle.get("tables", ""),
            columns=metadata_bundle.get("columns", ""),
            relationships=metadata_bundle.get("relationships", ""),
            sources=metadata_bundle.get("sources", ""),
            knowledge_pairs=metadata_bundle.get("knowledge_pairs", ""),
            business_terms=metadata_bundle.get("business_terms", ""),
        )

    def _summarize_metadata(self, bundle: Dict[str, str]) -> Dict[str, int]:
        return {
            key: len([line for line in value.splitlines() if line.startswith("- ")])
            for key, value in bundle.items()
        }

    def _extract_sql(self, response: Dict[str, Any]) -> Optional[str]:
        # Tool call path
        tool_calls = response.get("tool_calls") or []
        for tc in tool_calls:
            if tc.get("function", {}).get("name") == "run_sql":
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (KeyError, json.JSONDecodeError):
                    continue
                sql = args.get("sql")
                if sql:
                    return sql

        # Fallback: parse SQL out of the assistant text
        text = response.get("content") or ""
        if not text:
            return None
        if "```sql" in text.lower():
            start = text.lower().find("```sql") + len("```sql")
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        if "SELECT" in text.upper():
            lines = text.splitlines()
            sql_lines: List[str] = []
            in_sql = False
            for line in lines:
                if "SELECT" in line.upper():
                    in_sql = True
                if in_sql:
                    sql_lines.append(line)
                    if ";" in line:
                        break
            return "\n".join(sql_lines).strip() or None
        return None


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------
class AgentRegistry:
    """Lazily builds one `JeenInsightsAgent` per `source_key`."""

    def __init__(
        self,
        *,
        llm_service: AzureOpenAILlmService,
        metadata_loader: MetadataLoader,
        connection_service: ConnectionService,
        history_service: ConversationHistoryService,
        user_resolver: SimpleUserResolver,
    ):
        self.llm = llm_service
        self.metadata_loader = metadata_loader
        self.connection_service = connection_service
        self.history = history_service
        self.user_resolver = user_resolver
        self._prompt_template = _load_prompt_template()
        self._agents: Dict[str, JeenInsightsAgent] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    async def get_agent(self, source_key: str) -> JeenInsightsAgent:
        if source_key in self._agents:
            return self._agents[source_key]
        lock = self._locks.setdefault(source_key, asyncio.Lock())
        async with lock:
            if source_key in self._agents:
                return self._agents[source_key]
            connection = await self.connection_service.get_connection(source_key)
            runner = await self.connection_service.get_runner(source_key)
            agent = JeenInsightsAgent(
                connection=connection,
                sql_runner=runner,
                llm_service=self.llm,
                metadata_loader=self.metadata_loader,
                history_service=self.history,
                user_resolver=self.user_resolver,
                prompt_template=self._prompt_template,
            )
            self._agents[source_key] = agent
            logger.info("✅ Built JeenInsightsAgent for source_key=%s", source_key)
            return agent

    async def close(self) -> None:
        await self.connection_service.close()
        self._agents.clear()
