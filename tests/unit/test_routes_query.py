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
