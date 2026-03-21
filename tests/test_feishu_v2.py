"""
测试飞书v2格式webhook的兼容性
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_v2_format_basic():
    """测试基本的v2格式webhook"""
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": "test_v2",
            "event_type": "im.message.receive_v1",
            "create_time": "1603723919000000",
            "token": "v2",
            "app_id": "cli_test",
            "tenant_key": "test",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_test",
                    "union_id": "on_test",
                    "user_id": "test_user",
                },
                "sender_type": "user",
                "tenant_key": "test",
            },
            "message": {
                "message_id": "om_test",
                "root_id": "om_test",
                "parent_id": "om_test",
                "create_time": "1603723919000000",
                "chat_id": "oc_test",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"测试v2格式"}',
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["source"] == "feishu"
    assert body["parsed_text"] == "测试v2格式"


def test_v1_format_compatibility():
    """测试v1格式向后兼容"""
    payload = {
        "event_type": "im.message.receive_v1",
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_test",
                    "union_id": "on_test",
                    "user_id": "test_user",
                },
                "sender_type": "user",
                "tenant_key": "test",
            },
            "message": {
                "message_id": "om_test",
                "root_id": "om_test",
                "parent_id": "om_test",
                "create_time": "1603723919000000",
                "chat_id": "oc_test",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"测试v1格式"}',
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["source"] == "feishu"
    assert body["parsed_text"] == "测试v1格式"


def test_simplified_format():
    """测试简化格式（只有text字段）"""
    payload = {"text": "简化格式测试"}

    resp = client.post("/feishu/webhook", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["source"] == "feishu"
    assert body["parsed_text"] == "简化格式测试"


def test_v2_empty_message():
    """测试v2格式的空消息"""
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": "test_v2_empty",
            "event_type": "im.message.receive_v1",
            "create_time": "1603723919000000",
            "token": "v2",
            "app_id": "cli_test",
            "tenant_key": "test",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_test",
                    "union_id": "on_test",
                    "user_id": "test_user",
                },
                "sender_type": "user",
                "tenant_key": "test",
            },
            "message": {
                "message_id": "om_test",
                "root_id": "om_test",
                "parent_id": "om_test",
                "create_time": "1603723919000000",
                "chat_id": "oc_test",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":""}',
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["task"]["status"] == "ignored"


def test_v2_help_message():
    """测试v2格式的help消息"""
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": "test_v2_help",
            "event_type": "im.message.receive_v1",
            "create_time": "1603723919000000",
            "token": "v2",
            "app_id": "cli_test",
            "tenant_key": "test",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_test",
                    "union_id": "on_test",
                    "user_id": "test_user",
                },
                "sender_type": "user",
                "tenant_key": "test",
            },
            "message": {
                "message_id": "om_test",
                "root_id": "om_test",
                "parent_id": "om_test",
                "create_time": "1603723919000000",
                "chat_id": "oc_test",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"help"}',
                "mentions": [],
            },
        },
    }

    resp = client.post("/feishu/webhook", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["task"]["status"] == "completed"
    assert "llm_result" in body
    assert "帮助" in body["llm_result"] or "AI" in body["llm_result"]
