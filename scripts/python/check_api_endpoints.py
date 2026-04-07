#!/usr/bin/env python3
"""
Test sending messages through the HTTP API.
"""

import asyncio
import json
import os
import sys

import aiohttp

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_api_endpoints():
    """Test the API endpoints."""
    base_url = "http://localhost:8000"

    print(f"🌐 Testing API endpoints at {base_url}")

    async with aiohttp.ClientSession() as session:
        # Test 1: Health check
        print("\n1️⃣ Testing health endpoint...")
        try:
            async with session.get(f"{base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Health check: {data}")
                else:
                    print(f"❌ Health check failed: {response.status}")
        except Exception as e:
            print(f"❌ Health check error: {e}")

        # Test 2: System status
        print("\n2️⃣ Testing system status...")
        try:
            async with session.get(f"{base_url}/system/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ System status: {data.get('ok')}")
                    print(f"   Agents: {data.get('agent_count')}")
                    for agent in data.get("agents", []):
                        print(f"   - {agent['name']}: {agent['running']}")
                else:
                    print(f"❌ System status failed: {response.status}")
        except Exception as e:
            print(f"❌ System status error: {e}")

        # Test 3: Create OpenCode task
        print("\n3️⃣ Testing OpenCode task creation...")
        try:
            task_data = {
                "message": "写一个Python脚本来打印'Hello, World!'",
                "feishu_chat_id": "test_chat_001",
                "notify_on_complete": False,
            }

            async with session.post(
                f"{base_url}/opencode/tasks", json=task_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Task created: {data.get('task_id')}")
                    print(f"   Status: {data.get('status')}")
                    print(f"   Message: {data.get('message')}")

                    # Get task details
                    task_id = data.get("task_id")
                    if task_id:
                        print(f"\n   Getting task details for {task_id}...")
                        async with session.get(
                            f"{base_url}/opencode/tasks/{task_id}"
                        ) as task_response:
                            if task_response.status == 200:
                                task_details = await task_response.json()
                                print("   ✅ Task details retrieved")
                                status = task_details.get("item", {}).get("status")
                                print(f"   Status: {status}")
                                user_message = task_details.get("item", {}).get(
                                    "user_message", ""
                                )
                                print(f"   User message: {user_message[:50]}...")
                            else:
                                print(
                                    f"   ❌ Failed to get task details: {task_response.status}"
                                )
                else:
                    print(f"❌ Task creation failed: {response.status}")
                    try:
                        error_data = await response.json()
                        print(f"   Error: {error_data}")
                    except:
                        print(f"   Error text: {await response.text()}")
        except Exception as e:
            print(f"❌ Task creation error: {e}")

        # Test 4: List tasks
        print("\n4️⃣ Testing task listing...")
        try:
            async with session.get(f"{base_url}/opencode/tasks?limit=5") as response:
                if response.status == 200:
                    data = await response.json()
                    tasks = data.get("items", [])
                    print(f"✅ Found {len(tasks)} tasks")
                    for i, task in enumerate(tasks[:3]):  # Show first 3
                        print(
                            f"   {i + 1}. {task.get('task_id', '')[:20]}... - {task.get('status')}"
                        )
                else:
                    print(f"❌ Task listing failed: {response.status}")
        except Exception as e:
            print(f"❌ Task listing error: {e}")

        # Test 5: Config check
        print("\n5️⃣ Testing configuration check...")
        try:
            async with session.get(f"{base_url}/config-check") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Configuration check:")
                    for key, value in data.items():
                        print(f"   {key}: {value}")
                else:
                    print(f"❌ Config check failed: {response.status}")
        except Exception as e:
            print(f"❌ Config check error: {e}")

        # Test 6: Feishu config check
        print("\n6️⃣ Testing Feishu configuration...")
        try:
            async with session.get(f"{base_url}/feishu/config-check") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Feishu configuration:")
                    for key, value in data.items():
                        print(f"   {key}: {'✅ Present' if value else '❌ Missing'}")
                else:
                    print(f"❌ Feishu config check failed: {response.status}")
        except Exception as e:
            print(f"❌ Feishu config check error: {e}")


async def test_webhook_simulation():
    """Simulate a Feishu webhook message."""
    print("\n🔔 Testing webhook simulation...")

    # This is a simplified webhook payload
    webhook_payload = {
        "schema": "2.0",
        "header": {
            "event_id": "test_event_001",
            "event_type": "im.message.receive_v1",
            "create_time": "2026-04-06T21:10:44Z",
            "token": "test_token",
            "app_id": "cli_test",
            "tenant_key": "test_tenant",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "union_id": "test_user_001",
                    "user_id": "test_user_001",
                    "open_id": "test_user_001",
                },
                "sender_type": "user",
                "tenant_key": "test_tenant",
            },
            "message": {
                "message_id": "test_msg_001",
                "root_id": "",
                "parent_id": "",
                "create_time": "2026-04-06T21:10:44Z",
                "chat_id": "test_chat_001",
                "chat_type": "group",
                "message_type": "text",
                "content": json.dumps({"text": "测试消息：帮我写一个Python函数"}),
                "mentions": [],
            },
        },
    }

    print("Webhook payload prepared (not sent - server would need to be running)")
    print(
        "To test webhook, you would POST to: http://localhost:8000/feishu/webhook/opencode"
    )
    print(f"Payload size: {len(json.dumps(webhook_payload))} bytes")


async def main():
    """Run all API tests."""
    print("=" * 60)
    print("OpenCode-Feishu Bridge - API Test")
    print("=" * 60)

    print("⚠️  Note: Make sure the server is running on localhost:8000")
    print(
        "   Start with: cd /home/user/workspace/opencode-feishu-bridge/src && python3 main.py"
    )
    print()

    try:
        await test_api_endpoints()
        await test_webhook_simulation()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("API测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
