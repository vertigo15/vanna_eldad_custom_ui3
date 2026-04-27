"""Health + root information endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from src.api import state
from src.config import settings

router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    return {
        "service": "Jeen Insights",
        "version": "2.0.0",
        "status": "running",
    }


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "registry_ready": state.agent_registry is not None,
        "services": {
            "llm": f"Azure OpenAI {settings.AZURE_OPENAI_DEPLOYMENT_NAME}",
            "metadata_db": f"{settings.METADATA_DB_HOST}/{settings.METADATA_DB_NAME}",
        },
    }
