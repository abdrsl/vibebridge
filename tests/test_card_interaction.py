#!/usr/bin/env python3
"""
测试飞书卡片交互
"""

import json
import asyncio
from src.legacy.feishu_card_handler import process_feishu_webhook
from fastapi import BackgroundTasks


class MockBackgroundTasks:
    """模拟BackgroundTasks"""

    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))

    async def run_all(self):
        """运行所有任务"""
        for func, args, kwargs in self.tasks:
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)


async def test_card_interaction():
    """测试卡片交互"""
    print("测试飞书卡片交互")
    print("=" * 60)

    background_tasks = MockBackgroundTasks()

    # 测试1: URL验证
    print("\n1. 测试URL验证")
    challenge_body = {
        "challenge": "test_challenge_123",
        "type": "url_verification",
    }

    result1 = await process_feishu_webhook(challenge_body, background_tasks)
    print(f"   结果: {result1}")
    print(f"   预期: {{'challenge': 'test_challenge_123'}}")

    # 测试2: 普通文本消息
    print("\n2. 测试普通文本消息")
    text_body = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_test_001",
                "chat_id": "chat_test_123",
                "content": json.dumps({"text": "请帮我创建一个HTML页面"}),
            },
            "sender": {
                "sender_id": {
                    "open_id": "user_test_456",
                },
            },
        },
    }

    result2 = await process_feishu_webhook(text_body, background_tasks)
    print(f"   结果: {result2}")

    # 测试3: 卡片动作消息（确认）
    print("\n3. 测试卡片动作消息（确认）")
    card_action_body = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_card_001",
                "chat_id": "chat_test_123",
                "content": json.dumps(
                    {
                        "text": json.dumps(
                            {
                                "action": "confirm",
                                "session_id": "test_session_123",
                            }
                        )
                    }
                ),
            },
            "sender": {
                "sender_id": {
                    "open_id": "user_test_456",
                },
            },
        },
    }

    result3 = await process_feishu_webhook(card_action_body, background_tasks)
    print(f"   结果: {result3}")

    # 测试4: 卡片动作消息（取消）
    print("\n4. 测试卡片动作消息（取消）")
    cancel_action_body = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_card_002",
                "chat_id": "chat_test_123",
                "content": json.dumps(
                    {
                        "text": json.dumps(
                            {
                                "action": "cancel",
                                "session_id": "test_session_123",
                            }
                        )
                    }
                ),
            },
            "sender": {
                "sender_id": {
                    "open_id": "user_test_456",
                },
            },
        },
    }

    result4 = await process_feishu_webhook(cancel_action_body, background_tasks)
    print(f"   结果: {result4}")

    # 测试5: 无效的卡片动作
    print("\n5. 测试无效的卡片动作")
    invalid_action_body = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "message": {
                "message_id": "msg_invalid_001",
                "chat_id": "chat_test_123",
                "content": json.dumps({"text": "这不是有效的JSON"}),
            },
            "sender": {
                "sender_id": {
                    "open_id": "user_test_456",
                },
            },
        },
    }

    result5 = await process_feishu_webhook(invalid_action_body, background_tasks)
    print(f"   结果: {result5}")

    print("\n" + "=" * 60)
    print("卡片交互测试完成")


async def test_real_card_format():
    """测试真实的飞书卡片格式"""
    print("\n测试真实的飞书卡片格式")
    print("=" * 60)

    # 根据飞书文档，卡片交互的实际格式可能是这样的：
    # 1. 用户点击卡片按钮
    # 2. 飞书发送一个特殊的webhook事件
    # 3. 我们需要在5秒内响应特定的格式

    # 模拟飞书卡片交互webhook
    card_webhook = {
        "schema": "2.0",
        "header": {
            "event_id": "fce6f3a0-7b4c-4b3b-8f3a-0c7b4c3b8f3a",
            "event_type": "im.message.receive_v1",
            "create_time": "2025-03-22T04:00:00Z",
            "token": "test_token",
            "app_id": "test_app_id",
            "tenant_key": "test_tenant",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "union_id": "on_123456",
                    "user_id": "user_123",
                    "open_id": "ou_123456",
                },
                "sender_type": "user",
                "tenant_key": "test_tenant",
            },
            "message": {
                "message_id": "om_123456",
                "root_id": None,
                "parent_id": None,
                "create_time": "2025-03-22T04:00:00Z",
                "chat_id": "oc_123456",
                "chat_type": "group",
                "message_type": "interactive",
                "content": json.dumps(
                    {
                        # 卡片交互的内容格式
                        "value": json.dumps(
                            {
                                "action": "confirm",
                                "session_id": "test_session_123",
                            }
                        )
                    }
                ),
                "mentions": [],
            },
        },
    }

    print("模拟飞书卡片交互webhook:")
    print(f"   event_type: {card_webhook['header']['event_type']}")
    print(f"   message_type: {card_webhook['event']['message']['message_type']}")
    print(f"   content: {card_webhook['event']['message']['content']}")

    # 尝试解析内容
    try:
        content = json.loads(card_webhook["event"]["message"]["content"])
        print(f"   解析的content: {content}")

        if "value" in content:
            value = json.loads(content["value"])
            print(f"   解析的value: {value}")
    except Exception as e:
        print(f"   解析错误: {e}")

    print("\n" + "=" * 60)
    print("真实格式测试完成")


def main():
    """主函数"""
    print("飞书卡片交互测试套件")
    print("=" * 60)

    # 运行测试
    asyncio.run(test_card_interaction())
    asyncio.run(test_real_card_format())

    print("\n" + "=" * 60)
    print("所有测试完成！")

    # 分析错误码200340的可能原因
    print("\n📋 错误码200340分析:")
    print("1. 卡片响应格式不正确")
    print("   - 飞书期望特定的响应格式")
    print("   - 成功时应返回空对象 {}")
    print("   - 失败时应返回错误信息")

    print("\n2. 处理超时")
    print("   - 需要在5秒内响应")
    print("   - 复杂操作应使用后台任务")
    print("   - 立即返回空响应，后台处理")

    print("\n3. 权限问题")
    print("   - 机器人没有发送消息的权限")
    print("   - 检查飞书机器人权限配置")

    print("\n4. 卡片配置问题")
    print("   - 卡片按钮的value格式不正确")
    print("   - 卡片action配置错误")

    print("\n✅ 解决方案:")
    print("1. 确保卡片动作处理器返回正确的响应格式")
    print("2. 使用后台任务处理耗时操作")
    print("3. 立即返回空响应 {} 给飞书")
    print("4. 在后台发送结果消息")


if __name__ == "__main__":
    main()
