"""API tests for VibeBridge (new architecture)."""

import pytest
from fastapi.testclient import TestClient

from vibebridge.server import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "VibeBridge"
    assert body["status"] == "ok"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "providers" in body


def test_system_status(client):
    resp = client.get("/system/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "providers" in body


def test_feishu_webhook_challenge(client):
    resp = client.post(
        "/im/feishu/webhook",
        json={"challenge": "test-challenge-123"},
    )
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "test-challenge-123"


def test_feishu_webhook_unsupported_event(client):
    resp = client.post(
        "/im/feishu/webhook",
        json={
            "schema": "2.0",
            "header": {"event_type": "im.message.delete_v1"},
            "event": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "skipped" in body
