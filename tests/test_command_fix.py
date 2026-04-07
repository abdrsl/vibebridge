#!/usr/bin/env python3
"""
测试命令处理修复
"""

import json
import time

import requests

webhook_url = "http://localhost:8000/feishu/webhook/opencode"


def test_command(command):
    """测试单个命令"""
    message_id = f"om_test_{int(time.time())}"
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": f"test_{int(time.time())}",
            "event_type": "im.message.receive_v1",
            "create_time": str(int(time.time() * 1000)),
            "token": "test_token",
            "app_id": "cli_xxxxxxxxxxxxxxxx",
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
                "message_id": message_id,
                "root_id": "",
                "parent_id": "",
                "create_time": str(int(time.time() * 1000)),
                "chat_id": "oc_REDACTED_CHAT_ID",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": command}, ensure_ascii=False),
                "mentions": [],
            },
        },
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        print(f"命令: '{command}'")
        print(f"状态: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"结果: {json.dumps(result, ensure_ascii=False)}")
            return result
        else:
            print(f"错误: {response.text}")
            return None
    except Exception as e:
        print(f"异常: {e}")
        return None


if __name__ == "__main__":
    print("测试命令处理...")

    # 测试1: webhook模式
    print("\n1. 测试'webhook模式'命令:")
    result1 = test_command("webhook模式")

    time.sleep(1)

    # 测试2: websocket模式
    print("\n2. 测试'websocket模式'命令:")
    result2 = test_command("websocket模式")

    time.sleep(1)

    # 测试3: 简单命令
    print("\n3. 测试'hello'命令:")
    result3 = test_command("hello")

    time.sleep(1)

    # 测试4: 列出文件任务
    print("\n4. 测试OpenCode任务:")
    result4 = test_command("列出当前目录的文件")
