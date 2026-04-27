"""HTTP API package.

`app` is the singleton FastAPI instance used in production
(`uvicorn src.main:app` re-exports it from `src.main`).

Tests should call `create_app()` directly to get a fresh instance.
"""

from src.api.app_factory import create_app

app = create_app()

__all__ = ["app", "create_app"]
