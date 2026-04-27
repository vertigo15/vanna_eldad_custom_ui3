"""Tests for `src.api.routes.connections`."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock


def _fake_connection(source_key="sales_db"):
    """Build an object with the same `to_public_dict` contract as Connection."""
    return SimpleNamespace(
        to_public_dict=lambda: {
            "id": 1,
            "source_key": source_key,
            "display_name": source_key,
            "description": None,
            "service_type": "Postgres",
            "database_type": "postgres",
            "connection_host": "host",
            "connection_port": 5432,
            "connection_database": "db",
            "db_schema": "public",
            "enable_ssl": True,
            "is_active": True,
        }
    )


def test_list_connections(client, fake_state):
    fake_state.connection_service.list_connections = AsyncMock(
        return_value=[_fake_connection("a"), _fake_connection("b")]
    )

    resp = client.get("/api/connections")

    assert resp.status_code == 200
    body = resp.json()
    assert [c["source_key"] for c in body["connections"]] == ["a", "b"]


def test_list_connections_returns_503_when_state_empty(client, empty_state):
    resp = client.get("/api/connections")
    assert resp.status_code == 503


def test_refresh_metadata_invalidates_loader(client, fake_state):
    resp = client.post("/api/connections/sales_db/refresh-metadata")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    fake_state.metadata_loader.invalidate.assert_called_once_with("sales_db")
