#!/usr/bin/env python3
"""
测试所有自定义命令
"""

import json
import time
import uuid

import requests


def send_command(text: str):
    message_id = f"om_test_{uuid.uuid4().hex[:8]}"
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": f"test_{uuid.uuid4().hex[:8]}",
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
                "message_id": message_id,
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
    print(f"\n[{time.strftime('%H:%M:%S')}] 发送命令: {text}")
    print(f"消息ID: {message_id}")
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"状态码: {response.status_code}")
        try:
            body = response.json()
            print(f"响应: {json.dumps(body, ensure_ascii=False, indent=2)}")
        except:
            print(f"原始响应: {response.text[:200]}")
        return response.status_code, response.text
    except Exception as e:
        print(f"错误: {e}")
        return 0, str(e)


def main():
    commands = ["清空session", "kimi", "deepseek", "git 提交", "启动服务器", "模型"]

    print("=" * 60)
    print("开始测试所有自定义命令")
    print("=" * 60)

    for cmd in commands:
        send_command(cmd)
        time.sleep(1)  # 短暂延迟

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print("\n检查服务器日志以确认命令处理情况。")
    print("日志文件: logs/server.log")


if __name__ == "__main__":
    main()
