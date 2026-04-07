#!/usr/bin/env python3
"""
测试实时OpenCode任务执行
"""

import json
import time

import requests

webhook_url = "http://localhost:8000/feishu/webhook/opencode"


def send_task(command):
    """发送OpenCode任务到webhook"""
    message_id = f"om_test_{int(time.time())}_{hash(command) % 10000}"

    payload = {
        "schema": "2.0",
        "header": {
            "event_id": f"test_task_{int(time.time())}",
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

    print(f"发送任务: '{command}'")
    print(f"消息ID: {message_id}")
    print("聊天ID: oc_REDACTED_CHAT_ID")

    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        print(f"响应状态: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"响应内容: {json.dumps(result, ensure_ascii=False)}")

            if result.get("ok"):
                session_id = result.get("session_id")
                status = result.get("status")
                print("✅ 任务已接受")
                print(f"   Session ID: {session_id}")
                print(f"   状态: {status}")

                if status == "running":
                    print("   🚀 任务正在执行中...")
                    print("   请检查飞书消息查看实时输出")
                elif status == "pending_confirmation":
                    print("   📋 需要用户确认")
                    print("   请检查飞书消息查看确认卡片")
                else:
                    print(f"   ❓ 未知状态: {status}")
            else:
                print(f"❌ 任务失败: {result.get('error', 'unknown error')}")
        else:
            print(f"❌ HTTP错误: {response.text}")

        return response.json() if response.status_code == 200 else None

    except Exception as e:
        print(f"❌ 请求异常: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    print("=== 测试实时OpenCode任务 ===")
    print()

    # 测试1: 简单列表任务
    print("测试1: 简单文件列表任务")
    print("-" * 40)
    result1 = send_task("ls -la")

    time.sleep(2)

    # 测试2: 更复杂的任务
    print("\n\n测试2: 查看目录结构")
    print("-" * 40)
    result2 = send_task("列出当前目录的详细结构")

    time.sleep(2)

    # 测试3: 检查session状态
    print("\n\n测试3: 检查服务状态")
    print("-" * 40)
    try:
        status_resp = requests.get("http://localhost:8000/", timeout=5)
        print(f"服务状态: {status_resp.status_code}")
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            print(f"服务信息: {json.dumps(status_data, indent=2)}")
    except Exception as e:
        print(f"状态检查失败: {e}")


if __name__ == "__main__":
    main()
