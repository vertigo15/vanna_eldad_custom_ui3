"""Tests for `src.api.routes.query` validation paths.

We intentionally don't go past the validation layer here — the agent itself
is exercised by integration tests, not unit tests.
"""

from __future__ import annotations


def test_query_rejects_empty_question(client, fake_state):
    resp = client.post(
        "/api/query",
        json={"question": "   ", "connection": "sales_db"},
    )
    assert resp.status_code == 400
    assert "Question cannot be empty" in resp.json()["detail"]


def test_query_returns_503_when_registry_missing(client, empty_state):
    resp = client.post(
        "/api/query",
        json={"question": "show all customers", "connection": "sales_db"},
    )
    assert resp.status_code == 503


def test_tables_requires_connection(client, fake_state):
    # FastAPI returns 422 on a missing required query param.
    resp = client.get("/api/tables")
    assert resp.status_code == 422


# ── /api/tables-rich ──────────────────────────────────────────────────────────

def test_tables_rich_requires_connection(client, fake_state):
    """Missing `connection` query param → 422."""
    resp = client.get("/api/tables-rich")
    assert resp.status_code == 422


def test_tables_rich_returns_503_when_loader_missing(client, empty_state):
    """MetadataLoader not initialised → 503."""
    resp = client.get("/api/tables-rich?connection=sales_db")
    assert resp.status_code == 503


def test_tables_rich_returns_table_list(client, fake_state):
    """Happy path: returns [{name, description, col_count}] from the loader."""
    from unittest.mock import AsyncMock

    expected = [
        {"name": "orders",   "description": "Customer orders", "col_count": 12},
        {"name": "products", "description": None,              "col_count": 5},
    ]
    fake_state.metadata_loader.load_tables_rich = AsyncMock(return_value=expected)

    resp = client.get("/api/tables-rich?connection=sales_db")

    assert resp.status_code == 200
    body = resp.json()
    assert body["tables"] == expected
    fake_state.metadata_loader.load_tables_rich.assert_called_once_with("sales_db")


def test_tables_rich_returns_empty_list(client, fake_state):
    """Catalog with no tables returns an empty list (not an error)."""
    from unittest.mock import AsyncMock

    fake_state.metadata_loader.load_tables_rich = AsyncMock(return_value=[])

    resp = client.get("/api/tables-rich?connection=empty_db")

    assert resp.status_code == 200
    assert resp.json() == {"tables": []}
