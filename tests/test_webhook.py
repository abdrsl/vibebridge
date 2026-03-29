#!/usr/bin/env python3
"""
测试自定义命令的Webhook集成
"""

import json
import requests
import sys


def send_webhook_v2(text: str):
    """发送v2格式的webhook"""
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": "test_event_id",
            "event_type": "im.message.receive_v1",
            "create_time": "1603723919000000",
            "token": "v2",
            "app_id": "cli_test",
            "tenant_key": "test_tenant",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_test_user",
                    "union_id": "on_test_user",
                    "user_id": "user_test",
                },
                "sender_type": "user",
                "tenant_key": "test_tenant",
            },
            "message": {
                "message_id": "om_test_message",
                "root_id": "om_test_root",
                "parent_id": "om_test_parent",
                "create_time": "1603723919000000",
                "chat_id": "oc_test_chat",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
                "mentions": [],
            },
        },
    }

    url = "http://127.0.0.1:8000/feishu/webhook/opencode"
    print(f"Sending webhook for command: {text}")
    response = requests.post(url, json=payload, timeout=10)
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    return response.json()


if __name__ == "__main__":
    # 测试所有自定义命令
    commands = ["清空session", "kimi", "deepseek", "git 提交", "启动服务器", "模型"]
    for cmd in commands:
        print("\n" + "=" * 60)
        try:
            result = send_webhook_v2(cmd)
            print(f"Command '{cmd}' -> {result.get('ok', '?')}")
        except Exception as e:
            print(f"Error: {e}")
        print("=" * 60)
