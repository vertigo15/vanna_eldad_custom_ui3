"""FastAPI lifespan: builds and tears down shared services.

This is the single source of truth for the app's startup/shutdown order.
Routes never instantiate services themselves; they read from `src.api.state`
(via `src.api.dependencies` getters).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.agent import AgentRegistry
from src.agent.conversation_history import ConversationHistoryService
from src.agent.llm_service import AzureOpenAILlmService
from src.agent.user_resolver import SimpleUserResolver
from src.api import state
from src.config import settings
from src.connections import ConnectionService
from src.metadata import MetadataLoader, close_metadata_pool, get_metadata_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialise services on app startup; close them on shutdown."""
    logger.info("🚀 Starting Jeen Insights...")
    pool = await get_metadata_pool()

    state.metadata_loader = MetadataLoader(pool)
    state.connection_service = ConnectionService(pool)
    state.history_service = ConversationHistoryService(pool)

    llm_service = AzureOpenAILlmService(
        api_key=settings.AZURE_OPENAI_API_KEY,
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )

    state.agent_registry = AgentRegistry(
        llm_service=llm_service,
        metadata_loader=state.metadata_loader,
        connection_service=state.connection_service,
        history_service=state.history_service,
        user_resolver=SimpleUserResolver(),
    )

    logger.info("✅ Jeen Insights ready")
    try:
        yield
    finally:
        logger.info("👋 Shutting down Jeen Insights")
        if state.agent_registry:
            await state.agent_registry.close()
        await close_metadata_pool()
        # Reset handles so a hot-reload cycle doesn't leave stale references.
        state.agent_registry = None
        state.metadata_loader = None
        state.connection_service = None
        state.history_service = None
