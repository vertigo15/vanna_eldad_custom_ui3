"""Dataset insights + profiling reports."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from src.api.dependencies import get_history_service, resolve_agent
from src.api.models import (
    GenerateInsightsRequest,
    GenerateInsightsResponse,
    GenerateProfileRequest,
)
from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["insights"])


@router.post("/generate-insights", response_model=GenerateInsightsResponse)
async def generate_insights_endpoint(request: GenerateInsightsRequest):
    agent = await resolve_agent(request.connection)
    logger.info("Generating insights for: %s", request.question[:50])
    try:
        # Imported inline to keep startup fast (pandas/numpy heavy paths).
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

        history = get_history_service() if request.query_id else None
        if history and request.query_id:
            try:
                await history.add_insight(
                    query_id=request.query_id,
                    insight_type="summary",
                    content=insights.get("summary", "Analysis complete"),
                    llm_model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    llm_execution_time_ms=exec_time_ms,
                    tokens_input=insights.get("usage", {}).get("prompt_tokens", 0),
                    tokens_output=insights.get("usage", {}).get("completion_tokens", 0),
                )
                for finding in insights.get("findings", []):
                    await history.add_insight(
                        query_id=request.query_id,
                        insight_type="finding",
                        content=finding,
                        llm_model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    )
                for suggestion in insights.get("suggestions", []):
                    await history.add_insight(
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


@router.post("/generate-profile")
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
