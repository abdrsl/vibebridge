#!/usr/bin/env python3
"""
完整场景测试：模拟用户请求HTML个人网页
"""

import asyncio
import json
import os
from pathlib import Path
from app.session_manager import get_session_manager, SessionStatus
from app.feishu_webhook_handler import handle_feishu_webhook
from app.file_sender import send_html_to_feishu
from app.temp_file_manager import temp_file_manager
from app.simple_skill_manager import execute_skill


class MockBackgroundTasks:
    """模拟BackgroundTasks"""

    def __init__(self):
        self.tasks = []
        self.messages_sent = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))

    async def run_all(self):
        """运行所有任务"""
        for func, args, kwargs in self.tasks:
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                self.messages_sent.append(
                    {
                        "func": func.__name__
                        if hasattr(func, "__name__")
                        else str(func),
                        "args": args,
                        "kwargs": kwargs,
                        "result": result,
                    }
                )
            except Exception as e:
                self.messages_sent.append(
                    {
                        "func": func.__name__
                        if hasattr(func, "__name__")
                        else str(func),
                        "args": args,
                        "kwargs": kwargs,
                        "error": str(e),
                    }
                )


async def simulate_user_request():
    """模拟用户请求HTML个人网页的完整场景"""
    print("模拟用户请求HTML个人网页的完整场景")
    print("=" * 60)

    background_tasks = MockBackgroundTasks()

    # 场景1: 用户第一次请求
    print("\n1. 用户第一次请求: '@_user_1 请你做一个漂亮的html个人网页发过来'")

    # 模拟飞书webhook请求
    webhook_body = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_user_001",
                "chat_id": "chat_personal_web",
                "content": json.dumps(
                    {"text": "@_user_1 请你做一个漂亮的html个人网页发过来"}
                ),
            },
            "sender": {
                "sender_id": {
                    "open_id": "user_12345",
                },
            },
        },
    }

    # 处理webhook
    result = await handle_feishu_webhook(webhook_body, background_tasks)
    print(f"   Webhook处理结果: {result}")

    # 运行后台任务（发送确认卡片）
    await background_tasks.run_all()
    print(f"   发送了 {len(background_tasks.messages_sent)} 个后台任务")

    # 检查session状态
    session_manager = get_session_manager()
    sessions = await session_manager.list_sessions(
        chat_id="chat_personal_web",
        user_id="user_12345",
    )

    if sessions:
        session_id = sessions[0]["session_id"]
        print(f"   创建的session: {session_id}")
        print(f"   Session状态: {sessions[0]['status']}")

        # 场景2: 用户确认执行
        print("\n2. 用户确认执行（点击确认按钮）")

        # 模拟卡片动作
        action_result = await handle_feishu_webhook(
            {
                "schema": "2.0",
                "header": {
                    "event_type": "im.message.receive_v1",
                },
                "event": {
                    "message": {
                        "message_id": "msg_action_001",
                        "chat_id": "chat_personal_web",
                        "content": json.dumps(
                            {
                                "text": json.dumps(
                                    {
                                        "action": "confirm",
                                        "session_id": session_id,
                                    }
                                )
                            }
                        ),
                    },
                    "sender": {
                        "sender_id": {
                            "open_id": "user_12345",
                        },
                    },
                },
            },
            background_tasks,
        )

        print(f"   动作处理结果: {action_result}")

        # 运行后台任务（开始OpenCode任务）
        await background_tasks.run_all()
        print(f"   发送了 {len(background_tasks.messages_sent)} 个后台任务（累计）")

        # 场景3: 模拟OpenCode任务完成（创建HTML文件）
        print("\n3. OpenCode任务完成，创建HTML文件")

        # 创建测试HTML文件
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>个人网页 - 测试</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #4361ee, #3a0ca3); color: white; padding: 40px; border-radius: 10px; }
                h1 { margin: 0; }
                .content { margin: 30px 0; }
                .section { margin-bottom: 20px; padding: 20px; background: #f5f7ff; border-radius: 8px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>个人网页</h1>
                <p>通过OpenCode自动生成</p>
            </div>
            <div class="content">
                <div class="section">
                    <h2>关于我</h2>
                    <p>这是一个测试个人网页，演示OpenCode的文件创建和发送功能。</p>
                </div>
                <div class="section">
                    <h2>技能</h2>
                    <ul>
                        <li>HTML/CSS/JavaScript</li>
                        <li>Python开发</li>
                        <li>AI集成</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """

        # 使用技能发送HTML文件
        print("\n4. 使用技能系统发送HTML文件到飞书")

        skill_result = execute_skill(
            "send_html",
            {
                "content": html_content,
                "filename": "personal_website.html",
                "file_type": "html",
            },
        )

        print(f"   技能执行结果: {skill_result}")

        # 场景4: 用户再次请求（继续session）
        print("\n5. 用户再次请求: '再帮我添加一个联系方式页面'")

        # 更新session状态为完成（模拟任务完成）
        await session_manager.update_session(
            session_id,
            status=SessionStatus.COMPLETED,
        )

        # 模拟新的用户消息
        webhook_body2 = {
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
            },
            "event": {
                "message": {
                    "message_id": "msg_user_002",
                    "chat_id": "chat_personal_web",
                    "content": json.dumps({"text": "再帮我添加一个联系方式页面"}),
                },
                "sender": {
                    "sender_id": {
                        "open_id": "user_12345",
                    },
                },
            },
        }

        result2 = await handle_feishu_webhook(webhook_body2, background_tasks)
        print(f"   Webhook处理结果: {result2}")

        # 运行后台任务（发送继续卡片）
        await background_tasks.run_all()
        print(f"   发送了 {len(background_tasks.messages_sent)} 个后台任务（累计）")

        # 场景5: 用户选择继续
        print("\n6. 用户选择继续当前session")

        action_result2 = await handle_feishu_webhook(
            {
                "schema": "2.0",
                "header": {
                    "event_type": "im.message.receive_v1",
                },
                "event": {
                    "message": {
                        "message_id": "msg_action_002",
                        "chat_id": "chat_personal_web",
                        "content": json.dumps(
                            {
                                "text": json.dumps(
                                    {
                                        "action": "continue",
                                        "session_id": session_id,
                                    }
                                )
                            }
                        ),
                    },
                    "sender": {
                        "sender_id": {
                            "open_id": "user_12345",
                        },
                    },
                },
            },
            background_tasks,
        )

        print(f"   动作处理结果: {action_result2}")

        # 运行后台任务（开始新的OpenCode任务）
        await background_tasks.run_all()
        print(f"   发送了 {len(background_tasks.messages_sent)} 个后台任务（累计）")

    else:
        print("   错误: 没有创建session")

    print("\n" + "=" * 60)
    print("场景模拟完成")


async def test_file_send_integration():
    """测试文件发送与session的集成"""
    print("\n测试文件发送与session的集成")
    print("=" * 60)

    # 创建测试session
    session_manager = get_session_manager()
    session = await session_manager.get_or_create_session(
        chat_id="test_integration",
        user_id="test_user",
    )

    print(f"1. 创建测试session: {session.session_id}")

    # 模拟OpenCode任务创建HTML文件
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>集成测试</title>
        <style>
            body { font-family: sans-serif; padding: 20px; }
            .success { color: green; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>文件发送集成测试</h1>
        <p class="success">✅ 文件创建成功</p>
        <p>Session ID: {{session_id}}</p>
        <p>时间: {{timestamp}}</p>
    </body>
    </html>
    """

    # 替换模板变量
    from datetime import datetime

    html_content = html_content.replace("{{session_id}}", session.session_id)
    html_content = html_content.replace(
        "{{timestamp}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    print("\n2. 创建HTML内容")
    print(f"   内容长度: {len(html_content)} 字符")

    # 使用技能发送文件
    print("\n3. 使用技能发送文件")

    skill_result = execute_skill(
        "send_html",
        {
            "content": html_content,
            "filename": "integration_test.html",
            "file_type": "html",
        },
    )

    print(f"   技能结果: {skill_result}")

    if skill_result.get("success"):
        print("   ✅ 文件发送成功")

        # 更新session状态
        await session_manager.update_session(
            session.session_id,
            status=SessionStatus.COMPLETED,
            metadata={
                "last_file_sent": "integration_test.html",
                "file_size": len(html_content),
            },
        )

        print("   ✅ Session状态更新为COMPLETED")

        # 检查session状态
        updated = await session_manager.get_session(session.session_id)
        if updated:
            print(f"   Session状态: {updated.status}")
            print(f"   元数据: {updated.metadata}")

    print("\n" + "=" * 60)
    print("集成测试完成")


def main():
    """主函数"""
    print("OpenCode完整场景测试")
    print("=" * 60)

    # 运行测试
    asyncio.run(simulate_user_request())
    asyncio.run(test_file_send_integration())

    print("\n" + "=" * 60)
    print("所有测试完成！")

    # 总结实现的功能
    print("\n✅ 已实现的功能总结:")
    print("\n1. Session管理系统")
    print("   - 为每个飞书对话维护独立的session")
    print("   - 支持PENDING, CONFIRMED, RUNNING, COMPLETED等状态")
    print("   - 自动过期清理（1小时）")
    print("   - 消息历史记录")

    print("\n2. 用户确认机制")
    print("   - 新任务需要用户明确确认")
    print("   - 交互式卡片界面")
    print("   - 支持确认、取消、继续等操作")

    print("\n3. 会话连续性")
    print("   - 任务完成后可以继续同一session")
    print("   - 支持开始新session")
    print("   - 状态查询和管理")

    print("\n4. 文件发送集成")
    print("   - 通过技能系统发送文件")
    print("   - 支持HTML、文本、JSON等多种格式")
    print("   - 自动临时文件管理")
    print("   - 与session状态同步")

    print("\n5. 完整工作流程")
    print("   用户请求 → 创建session → 发送确认卡片 →")
    print("   用户确认 → 开始OpenCode任务 → 创建文件 →")
    print("   发送文件 → 更新session状态 → 等待用户继续")

    print("\n📋 对于用户请求'@_user_1 请你做一个漂亮的html个人网页发过来':")
    print("1. 系统会创建session并发送确认卡片")
    print("2. 用户确认后，OpenCode开始创建HTML文件")
    print("3. 文件创建完成后，通过技能系统发送到飞书")
    print("4. Session状态更新，用户可以继续请求其他操作")
    print("5. 所有操作都在同一session上下文中，保持连续性")


if __name__ == "__main__":
    main()
