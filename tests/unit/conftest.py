"""Shared fixtures for unit tests.

We deliberately avoid the FastAPI lifespan in unit tests:
- Constructing `src.api.app` triggers `create_app()` (just route wiring).
- `TestClient(app)` used WITHOUT a `with` block does NOT execute the
  lifespan, so no DB pool, no Azure OpenAI client, no AgentRegistry are
  required. Tests that need services inject fakes into `src.api.state`
  via the `fake_state` fixture.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

# Required env vars for `src.config.Settings` to import without errors.
# Real values are irrelevant: nothing in unit tests connects to anything.
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.invalid")
os.environ.setdefault("METADATA_DB_HOST", "test")
os.environ.setdefault("METADATA_DB_NAME", "test")
os.environ.setdefault("METADATA_DB_USER", "test")
os.environ.setdefault("METADATA_DB_PASSWORD", "test")

from fastapi.testclient import TestClient  # noqa: E402

from src.api import app  # noqa: E402
from src.api import state as api_state  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Lifespan-free TestClient. Routes work; services come from `fake_state`."""
    return TestClient(app)


@pytest.fixture
def fake_state(monkeypatch):
    """Replace `src.api.state.<service>` handles with MagicMocks for the test.

    Returns a small object exposing the four mocks so tests can stub return
    values fluently:
        fake_state.connection_service.list_connections.return_value = ...
    """

    class _FakeState:
        connection_service = MagicMock(name="ConnectionService")
        metadata_loader = MagicMock(name="MetadataLoader")
        history_service = MagicMock(name="HistoryService")
        agent_registry = MagicMock(name="AgentRegistry")

    fakes = _FakeState()
    monkeypatch.setattr(api_state, "connection_service", fakes.connection_service)
    monkeypatch.setattr(api_state, "metadata_loader", fakes.metadata_loader)
    monkeypatch.setattr(api_state, "history_service", fakes.history_service)
    monkeypatch.setattr(api_state, "agent_registry", fakes.agent_registry)
    return fakes


@pytest.fixture
def empty_state(monkeypatch):
    """Force every service handle to None to exercise the 503 path."""
    monkeypatch.setattr(api_state, "connection_service", None)
    monkeypatch.setattr(api_state, "metadata_loader", None)
    monkeypatch.setattr(api_state, "history_service", None)
    monkeypatch.setattr(api_state, "agent_registry", None)
