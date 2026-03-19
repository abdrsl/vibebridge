from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_list_tasks():
    resp = client.get("/tasks")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "items" in body


def test_webhook_text(monkeypatch):
    def fake_ask_deepseek_for_design_advice(text: str) -> str:
        return "mocked llm result"

    monkeypatch.setattr(
        "app.main.ask_deepseek_for_design_advice",
        fake_ask_deepseek_for_design_advice,
    )

    resp = client.post(
        "/feishu/webhook",
        json={"text": "设计一个适合PETG打印的桌面线缆整理器"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["task"]["status"] == "completed"
    assert body["llm_result"] == "mocked llm result"
    assert "saved" in body
