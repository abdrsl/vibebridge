#!/usr/bin/env python3
"""
Simple API test using requests library.
"""

import time

import requests

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    print("1️⃣ Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Health check: OK")
            print(f"   Timestamp: {data.get('timestamp')}")
            print(f"   Multi-agent system: {data.get('multi_agent_system')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_system_status():
    """Test system status endpoint."""
    print("\n2️⃣ Testing system status...")
    try:
        response = requests.get(f"{BASE_URL}/system/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ System status: {data.get('ok')}")
            print(f"   Running: {data.get('running')}")
            print(f"   Agents: {data.get('agent_count')}")

            print("   Agent details:")
            for agent in data.get("agents", []):
                status = "🟢" if agent.get("running") else "🔴"
                print(f"     {status} {agent.get('name')} ({agent.get('id')})")
                if agent.get("capabilities"):
                    print(
                        f"       Capabilities: {', '.join(agent.get('capabilities', []))}"
                    )
            return True
        else:
            print(f"❌ System status failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ System status error: {e}")
        return False


def test_create_task():
    """Test creating an OpenCode task."""
    print("\n3️⃣ Testing OpenCode task creation...")

    task_data = {
        "message": "写一个Python函数来计算两个数的和",
        "feishu_chat_id": "test_chat_001",
        "notify_on_complete": False,
    }

    try:
        response = requests.post(
            f"{BASE_URL}/opencode/tasks", json=task_data, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            print("✅ Task created successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {data.get('status')}")
            print(f"   Message: {data.get('message')}")

            # Wait a bit and check task status
            print("\n   Waiting 2 seconds, then checking task status...")
            time.sleep(2)

            task_response = requests.get(
                f"{BASE_URL}/opencode/tasks/{task_id}", timeout=5
            )
            if task_response.status_code == 200:
                task_details = task_response.json()
                item = task_details.get("item", {})
                print("   ✅ Task details retrieved")
                print(f"   Status: {item.get('status')}")
                print(f"   User message: {item.get('user_message', '')[:50]}...")
                print(f"   Created at: {item.get('created_at')}")
                print(f"   Output count: {item.get('output_count')}")
            else:
                print(f"   ❌ Failed to get task details: {task_response.status_code}")

            return task_id
        else:
            print(f"❌ Task creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Task creation error: {e}")
        return None


def test_list_tasks():
    """Test listing tasks."""
    print("\n4️⃣ Testing task listing...")
    try:
        response = requests.get(f"{BASE_URL}/opencode/tasks?limit=3", timeout=5)
        if response.status_code == 200:
            data = response.json()
            tasks = data.get("items", [])
            print(f"✅ Found {len(tasks)} tasks")

            if tasks:
                print("   Recent tasks:")
                for i, task in enumerate(tasks):
                    task_id = task.get("task_id", "")[:20]
                    if len(task.get("task_id", "")) > 20:
                        task_id += "..."
                    print(f"   {i + 1}. {task_id}")
                    print(f"      Status: {task.get('status')}")
                    print(f"      Created: {task.get('created_at')}")
                    if task.get("user_message"):
                        print(f"      Message: {task.get('user_message', '')[:40]}...")
                    print()
            return True
        else:
            print(f"❌ Task listing failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Task listing error: {e}")
        return False


def test_config_check():
    """Test configuration check."""
    print("\n5️⃣ Testing configuration check...")
    try:
        response = requests.get(f"{BASE_URL}/config-check", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Configuration check:")

            config_items = [
                (
                    "DEEPSEEK_BASE_URL",
                    data.get("DEEPSEEK_BASE_URL"),
                    "LLM API base URL",
                ),
                ("DEEPSEEK_MODEL", data.get("DEEPSEEK_MODEL"), "LLM model"),
                (
                    "DEEPSEEK_API_KEY",
                    "Present" if data.get("DEEPSEEK_API_KEY_present") else "Missing",
                    "API key",
                ),
            ]

            for key, value, description in config_items:
                status = "✅" if value and value != "Missing" else "❌"
                display_value = value if value else "Not set"
                print(f"   {status} {key}: {display_value} ({description})")

            return True
        else:
            print(f"❌ Config check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Config check error: {e}")
        return False


def test_feishu_config():
    """Test Feishu configuration."""
    print("\n6️⃣ Testing Feishu configuration...")
    try:
        response = requests.get(f"{BASE_URL}/feishu/config-check", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Feishu configuration:")

            feishu_items = [
                ("FEISHU_APP_ID", data.get("FEISHU_APP_ID_present"), "Feishu App ID"),
                (
                    "FEISHU_APP_SECRET",
                    data.get("FEISHU_APP_SECRET_present"),
                    "Feishu App Secret",
                ),
            ]

            for key, present, description in feishu_items:
                status = "✅" if present else "❌"
                status_text = "Present" if present else "Missing"
                print(f"   {status} {key}: {status_text} ({description})")

            return True
        else:
            print(f"❌ Feishu config check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Feishu config check error: {e}")
        return False


def test_root_endpoint():
    """Test root endpoint."""
    print("\n7️⃣ Testing root endpoint...")
    try:
        response = requests.get(BASE_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Root endpoint: {data.get('name')} v{data.get('version')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Architecture: {data.get('architecture')}")
            print(f"   Agents: {data.get('agents')}")
            return True
        else:
            print(f"❌ Root endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Root endpoint error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("OpenCode-Feishu Bridge - Simple API Test")
    print("=" * 60)
    print(f"Testing API at: {BASE_URL}")
    print()

    # Run tests
    tests = [
        ("Health Check", test_health),
        ("System Status", test_system_status),
        ("Root Endpoint", test_root_endpoint),
        ("Config Check", test_config_check),
        ("Feishu Config", test_feishu_config),
        ("Create Task", test_create_task),
        ("List Tasks", test_list_tasks),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'=' * 40}")
        print(f"Test: {test_name}")
        print(f"{'=' * 40}")
        try:
            result = test_func()
            results.append((test_name, result is not False and result is not None))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"Passed: {passed}/{total}")
    print()

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")

    print("\n" + "=" * 60)
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {total - passed} test(s) failed")
    print("=" * 60)


if __name__ == "__main__":
    main()
