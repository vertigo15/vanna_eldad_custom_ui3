"""Jeen Insights FastAPI entrypoint.

The actual app construction lives in `src.api`. This module exists so the
existing `uvicorn src.main:app` invocation (and the Dockerfile that uses it)
keeps working without modification.
"""

from __future__ import annotations

from src.api import app
from src.config import settings

__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
