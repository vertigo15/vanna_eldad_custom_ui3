"""Tests for `src.api.routes.health`."""

from __future__ import annotations


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"service": "Jeen Insights", "version": "2.0.0", "status": "running"}


def test_health_when_registry_ready(client, fake_state):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["registry_ready"] is True
    assert "llm" in body["services"]
    assert "metadata_db" in body["services"]


def test_health_when_registry_missing(client, empty_state):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    # `/health` is intentionally still 200 even when the registry isn't ready,
    # so probes can distinguish "service alive but not ready" from "down".
    assert body["status"] == "healthy"
    assert body["registry_ready"] is False
