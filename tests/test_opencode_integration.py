#!/usr/bin/env python3
"""
测试OpenCode集成功能
"""

import time

import requests


def test_opencode_integration():
    print("测试OpenCode集成功能")
    print("=" * 60)

    base_url = "http://127.0.0.1:8000"

    # 测试1: 创建OpenCode任务
    print("\n1. 创建OpenCode任务:")
    task_data = {
        "message": "创建一个简单的README.md文件",
        "feishu_chat_id": "oc_test_chat_opencode",
        "notify_on_complete": False,  # 测试时不通知飞书
    }

    try:
        response = requests.post(
            f"{base_url}/opencode/tasks", json=task_data, timeout=30
        )
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.text}")

        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            if task_id:
                print(f"   ✅ 任务创建成功，Task ID: {task_id}")

                # 测试2: 获取任务状态
                print(f"\n2. 获取任务状态 (Task ID: {task_id}):")
                time.sleep(2)  # 给任务一些时间开始

                status_response = requests.get(
                    f"{base_url}/opencode/tasks/{task_id}", timeout=10
                )
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"   任务状态: {status_data}")

                    task_info = status_data.get("item", {})
                    print(f"   - 状态: {task_info.get('status')}")
                    print(f"   - 用户消息: {task_info.get('user_message')}")
                    print(f"   - 创建时间: {task_info.get('created_at')}")

                    if task_info.get("output_count", 0) > 0:
                        print(f"   - 输出行数: {task_info.get('output_count')}")
                        print(
                            f"   - 输出预览: {task_info.get('output_preview', '')[:100]}..."
                        )
                else:
                    print(f"   ❌ 获取任务状态失败: {status_response.status_code}")

                # 测试3: 列出所有任务
                print("\n3. 列出所有OpenCode任务:")
                list_response = requests.get(
                    f"{base_url}/opencode/tasks?limit=5", timeout=10
                )
                if list_response.status_code == 200:
                    list_data = list_response.json()
                    tasks = list_data.get("items", [])
                    print(f"   找到 {len(tasks)} 个任务:")
                    for i, task in enumerate(tasks[:3]):  # 只显示前3个
                        print(
                            f"   {i + 1}. ID: {task.get('task_id')}, 状态: {task.get('status')}"
                        )
                else:
                    print(f"   ❌ 列出任务失败: {list_response.status_code}")

                # 测试4: 流式输出（可选）
                print(f"\n4. 测试任务流式输出 (Task ID: {task_id}):")
                try:
                    stream_url = f"{base_url}/opencode/tasks/{task_id}/stream"
                    stream_response = requests.get(stream_url, stream=True, timeout=5)
                    if stream_response.status_code == 200:
                        print("   ✅ 流式端点可访问")
                        # 不实际读取流，只是测试端点
                    else:
                        print(f"   ❌ 流式端点访问失败: {stream_response.status_code}")
                except Exception as e:
                    print(f"   ⚠️ 流式测试跳过（可能超时）: {e}")

            else:
                print("   ❌ 任务创建但未返回task_id")
        else:
            print("   ❌ 任务创建失败")
    except Exception as e:
        print(f"   错误: {e}")

    # 测试5: 直接测试OpenCode管理器
    print("\n5. 直接测试OpenCode执行:")
    try:
        import asyncio

        from src.legacy.opencode_integration import opencode_manager

        async def test_direct_opencode():
            print("   创建测试任务...")
            test_task_id = await opencode_manager.create_task(
                user_message="创建一个测试文件 test_opencode.txt",
                feishu_chat_id="oc_test_direct",
            )
            print(f"   测试任务ID: {test_task_id}")

            # 检查任务是否存在
            task = await opencode_manager.get_task(test_task_id)
            if task:
                print(f"   任务获取成功，状态: {task.status}")
                print(f"   用户消息: {task.user_message}")
            else:
                print("   任务获取失败")

            return test_task_id

        # 运行异步测试
        test_task_id = asyncio.run(test_direct_opencode())
        print(f"   ✅ 直接OpenCode测试完成，任务ID: {test_task_id}")

    except Exception as e:
        print(f"   ⚠️ 直接OpenCode测试失败: {e}")

    print("\n" + "=" * 60)
    print("检查服务器日志中的OpenCode相关记录...")
    time.sleep(2)
    try:
        with open("server.log", "r") as f:
            lines = f.readlines()
            print("   最近OpenCode相关日志:")
            opencode_logs = []
            for line in lines[-30:]:
                if "OpenCode" in line or "opencode" in line.lower():
                    opencode_logs.append(line.strip())

            if opencode_logs:
                for log in opencode_logs[-10:]:  # 只显示最后10条
                    print(f"   {log}")
            else:
                print("   未找到OpenCode相关日志")
    except Exception as e:
        print(f"   读取日志错误: {e}")

    print("\n" + "=" * 60)
    print("测试完成")


if __name__ == "__main__":
    test_opencode_integration()
