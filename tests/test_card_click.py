#!/usr/bin/env python3
"""
测试卡片点击确认
模拟飞书card.action.trigger事件
"""

import json
import time

import requests

# 服务器地址
webhook_url = "http://localhost:8000/feishu/webhook/opencode"


def test_card_click_confirm():
    """测试卡片点击确认"""
    print("=== 测试卡片点击确认 ===")
    print(f"服务器: {webhook_url}")
    print()

    # 模拟飞书card.action.trigger事件
    # 使用现有的session_id
    session_id = "fs_1775456902_dd137926"
    chat_id = "oc_REDACTED_CHAT_ID"
    user_id = "ou_test_user"

    payload = {
        "schema": "2.0",
        "header": {
            "event_id": f"test_card_click_{int(time.time())}",
            "event_type": "card.action.trigger",
            "create_time": str(int(time.time() * 1000)),
            "token": "test_token",
            "app_id": "cli_xxxxxxxxxxxxxxxx",
            "tenant_key": "test_tenant",
        },
        "event": {
            "action": {
                "tag": "button",
                "value": json.dumps(
                    {
                        "action": "confirm",
                        "session_id": session_id,
                    }
                ),
            },
            "operator": {
                "open_id": user_id,
                "user_id": "user_test",
            },
            "context": {
                "open_chat_id": chat_id,
                "chat_id": chat_id,
            },
        },
    }

    print(f"Session ID: {session_id}")
    print(f"Chat ID: {chat_id}")
    print(f"User ID: {user_id}")
    print("Action: confirm")
    print()

    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        print(f"响应状态: {response.status_code}")
        print(f"响应内容: {response.text}")

        response_json = response.json()
        print(f"解析响应: {response_json}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_card_click_confirm()
