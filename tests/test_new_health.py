#!/usr/bin/env python3
"""Quick test for new src.main health endpoint."""

import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.json()}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "timestamp" in body
    assert "multi_agent_system" in body
    print("Health endpoint OK")


def test_root():
    resp = client.get("/")
    print(f"Root status: {resp.status_code}")
    body = resp.json()
    print(f"Root body: {body}")
    assert resp.status_code == 200
    assert body["status"] == "ok"
    print("Root endpoint OK")


if __name__ == "__main__":
    try:
        test_health()
        test_root()
        print("All tests passed")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
