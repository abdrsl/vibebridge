from fastapi.testclient import TestClient

from src.legacy.main import app

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
    # Create a mock system that is running
    class MockSystem:
        def is_running(self):
            return True

    # Mock get_system to return a running system
    monkeypatch.setattr("src.main.get_system", lambda: MockSystem())

    resp = client.post(
        "/feishu/webhook", json={"text": "设计一个适合PETG打印的桌面线缆整理器"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["task"]["status"] == "completed"
    # LLM返回实际内容，不再检查固定字符串
    assert "llm_result" in body
    assert len(body["llm_result"]) > 0


def test_webhook_v1_format(monkeypatch):
    # Create a mock system that is running
    class MockSystem:
        def is_running(self):
            return True

    # Mock get_system to return a running system
    monkeypatch.setattr("src.main.get_system", lambda: MockSystem())

    # 飞书v1格式webhook
    v1_payload = {
        "event_type": "im.message.receive_v1",
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_xxx",
                    "union_id": "on_xxx",
                    "user_id": "xxx",
                },
                "sender_type": "user",
                "tenant_key": "xxx",
            },
            "message": {
                "message_id": "om_xxx",
                "root_id": "om_xxx",
                "parent_id": "om_xxx",
                "create_time": "1603723919000000",
                "chat_id": "oc_xxx",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"测试v1格式消息"}',
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook", json=v1_payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["task"]["status"] == "completed"
    # LLM返回实际内容，不再检查固定字符串
    assert "llm_result" in body
    assert len(body["llm_result"]) > 0


def test_webhook_empty_message():
    # 测试空消息
    v2_payload = {
        "schema": "2.0",
        "header": {
            "event_id": "f1219f57",
            "event_type": "im.message.receive_v1",
            "create_time": "1603723919000000",
            "token": "v2",
            "app_id": "cli_xxx",
            "tenant_key": "xxx",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_xxx",
                    "union_id": "on_xxx",
                    "user_id": "xxx",
                },
                "sender_type": "user",
                "tenant_key": "xxx",
            },
            "message": {
                "message_id": "om_xxx",
                "root_id": "om_xxx",
                "parent_id": "om_xxx",
                "create_time": "1603723919000000",
                "chat_id": "oc_xxx",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":""}',  # 空消息
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook", json=v2_payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["source"] == "feishu"
    assert body["parsed_text"] == ""
    assert body["task"]["status"] == "ignored"
    assert body["llm_result"] is None


def test_webhook_help_message():
    # 测试help消息
    v2_payload = {
        "schema": "2.0",
        "header": {
            "event_id": "f1219f57",
            "event_type": "im.message.receive_v1",
            "create_time": "1603723919000000",
            "token": "v2",
            "app_id": "cli_xxx",
            "tenant_key": "xxx",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_xxx",
                    "union_id": "on_xxx",
                    "user_id": "xxx",
                },
                "sender_type": "user",
                "tenant_key": "xxx",
            },
            "message": {
                "message_id": "om_xxx",
                "root_id": "om_xxx",
                "parent_id": "om_xxx",
                "create_time": "1603723919000000",
                "chat_id": "oc_xxx",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"help"}',  # help消息
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook", json=v2_payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["source"] == "feishu"
    assert body["parsed_text"] == "help"
    assert body["task"]["status"] == "completed"
    assert "llm_result" in body
    assert "saved" in body


def test_webhook_opencode_v2_format():
    # 测试新的/feishu/webhook/opencode端点的v2格式
    v2_payload = {
        "schema": "2.0",
        "header": {
            "event_id": "f1219f57",
            "event_type": "im.message.receive_v1",
            "create_time": "1603723919000000",
            "token": "v2",
            "app_id": "cli_xxx",
            "tenant_key": "xxx",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_xxx",
                    "union_id": "on_xxx",
                    "user_id": "xxx",
                },
                "sender_type": "user",
                "tenant_key": "xxx",
            },
            "message": {
                "message_id": "om_xxx",
                "root_id": "om_xxx",
                "parent_id": "om_xxx",
                "create_time": "1603723919000000",
                "chat_id": "oc_xxx",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"测试opencode v2格式"}',
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook/opencode", json=v2_payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    # 由于会话管理，可能返回already_running状态
    assert "status" in body
    assert body["status"] in [
        "pending",
        "already_running",
        "created",
        "pending_confirmation",
    ]


def test_webhook_opencode_empty_message():
    # 测试新的/feishu/webhook/opencode端点的空消息
    v2_payload = {
        "schema": "2.0",
        "header": {
            "event_id": "f1219f57",
            "event_type": "im.message.receive_v1",
            "create_time": "1603723919000000",
            "token": "v2",
            "app_id": "cli_xxx",
            "tenant_key": "xxx",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_xxx",
                    "union_id": "on_xxx",
                    "user_id": "xxx",
                },
                "sender_type": "user",
                "tenant_key": "xxx",
            },
            "message": {
                "message_id": "om_xxx",
                "root_id": "om_xxx",
                "parent_id": "om_xxx",
                "create_time": "1603723919000000",
                "chat_id": "oc_xxx",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":""}',  # 空消息
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook/opencode", json=v2_payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    # 空消息可能被跳过或标记为重复
    assert body.get("skipped") is True or body.get("status") == "already_running"
    assert body.get("reason") in ["Empty message", "Duplicate message", None]


def test_webhook_opencode_help_message():
    # 测试新的/feishu/webhook/opencode端点的help消息
    v2_payload = {
        "schema": "2.0",
        "header": {
            "event_id": "f1219f57",
            "event_type": "im.message.receive_v1",
            "create_time": "1603723919000000",
            "token": "v2",
            "app_id": "cli_xxx",
            "tenant_key": "xxx",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_xxx",
                    "union_id": "on_xxx",
                    "user_id": "xxx",
                },
                "sender_type": "user",
                "tenant_key": "xxx",
            },
            "message": {
                "message_id": "om_xxx",
                "root_id": "om_xxx",
                "parent_id": "om_xxx",
                "create_time": "1603723919000000",
                "chat_id": "oc_xxx",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"help"}',  # help消息
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook/opencode", json=v2_payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    # help消息可能被处理或标记为重复
    assert (
        body.get("handled") is True
        or body.get("skipped") is True
        or body.get("status") == "already_running"
    )
    if body.get("action"):
        assert body.get("action") == "help"
