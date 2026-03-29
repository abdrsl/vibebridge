#!/usr/bin/env python3
import json
import requests
import time
import uuid


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
    print(f"Sending command: {text}")
    print(f"Message ID: {message_id}")
    response = requests.post(url, json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")
    try:
        return response.json()
    except:
        return {}


if __name__ == "__main__":
    cmd = "模型"
    print("Testing command:", cmd)
    result = send_command(cmd)
    print("Result:", json.dumps(result, indent=2))
    print("\nWaiting for logs...")
    time.sleep(2)
