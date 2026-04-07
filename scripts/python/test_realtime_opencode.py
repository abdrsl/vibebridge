#!/usr/bin/env python3
"""
测试OpenCode实时显示功能
模拟飞书消息，要求OpenCode执行一个简单任务
"""

import json
import time

import requests

# 服务器地址
webhook_url = "http://localhost:8000/feishu/webhook/opencode"


# 创建测试消息 - 发送OpenCode命令
def send_opencode_command(command):
    """发送OpenCode命令到webhook"""
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": f"test_opencode_{int(time.time())}",
            "event_type": "im.message.receive_v1",
            "create_time": str(int(time.time() * 1000)),
            "token": "test_token",
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
                "message_id": f"om_opencode_{int(time.time())}",
                "root_id": "",
                "parent_id": "",
                "create_time": str(int(time.time() * 1000)),
                "chat_id": "oc_REDACTED_CHAT_ID",  # 测试聊天ID
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": command}, ensure_ascii=False),
                "mentions": [],
            },
        },
    }

    print(f"发送命令: {command}")
    print(f"到聊天: {payload['event']['message']['chat_id']}")

    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        print(f"响应状态: {response.status_code}")
        print(f"响应内容: {response.text}")
        return response
    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("=== 测试OpenCode实时显示功能 ===")
    print(f"服务器: {webhook_url}")
    print()

    # 测试1: 简单的OpenCode命令
    print("测试1: 简单的OpenCode命令")
    print("-" * 40)
    response1 = send_opencode_command("列出当前目录的文件")
    print()

    # 等待一下，让OpenCode处理
    print("等待OpenCode处理...")
    time.sleep(5)

    # 测试2: 另一个命令
    print("\n测试2: 另一个命令")
    print("-" * 40)
    response2 = send_opencode_command("创建一个测试文件")
    print()

    print("\n测试完成")
    print("注意: 检查服务器日志查看OpenCode实时输出")
