"""Tests for `src.api.routes.charts` validation paths.

The full LLM round-trip is covered by smoke tests against the running
container; here we only verify the cheap pre-LLM validation checks so a
fresh contributor breaking input validation gets a fast signal.
"""

from __future__ import annotations


def _valid_columns():
    return [{"name": "x", "type": "string"}, {"name": "y", "type": "number"}]


def _valid_payload(**overrides):
    payload = {
        "connection": "sales_db",
        "instruction": "add data labels",
        "current_config": {
            "xAxis": {"data": ["A", "B"]},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "data": [1, 2]}],
        },
        "columns": _valid_columns(),
        "column_names": ["x", "y"],
        "sample_data": [["A", 1], ["B", 2]],
    }
    payload.update(overrides)
    return payload


def test_edit_chart_rejects_empty_instruction(client, fake_state):
    resp = client.post(
        "/api/edit-chart", json=_valid_payload(instruction="   ")
    )
    assert resp.status_code == 400
    assert "instruction" in resp.json()["detail"]


def test_edit_chart_rejects_missing_current_config(client, fake_state):
    resp = client.post(
        "/api/edit-chart", json=_valid_payload(current_config={})
    )
    assert resp.status_code == 400
    assert "current_config" in resp.json()["detail"]


def test_edit_chart_returns_503_when_registry_missing(client, empty_state):
    resp = client.post("/api/edit-chart", json=_valid_payload())
    assert resp.status_code == 503
