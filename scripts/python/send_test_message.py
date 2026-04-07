#!/usr/bin/env python3
"""
Send a test message through the system.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from message_bus.bus import Message, MessageType, get_message_bus


async def send_simple_test():
    """Send a simple test message."""
    print("📤 Sending test message...")

    bus = get_message_bus()

    # Create a test message
    test_message = Message(
        message_type=MessageType.CUSTOM,
        sender="test_user",
        payload={
            "text": "这是一条测试消息",
            "action": "test",
            "timestamp": "2026-04-06",
        },
    )

    # Subscribe to see the message
    def message_handler(msg: Message):
        print(f"📨 Received message: {msg.message_type}")
        print(f"   From: {msg.sender}")
        print(f"   To: {msg.recipient or 'broadcast'}")
        print(f"   Payload: {msg.payload}")
        print(f"   ID: {msg.message_id}")
        print()

    bus.subscribe(MessageType.CUSTOM, message_handler)

    # Send the message
    await bus.publish(test_message)

    print("✅ Test message sent successfully!")


async def send_task_message():
    """Send a task creation message."""
    print("\n📋 Sending task creation message...")

    bus = get_message_bus()

    task_message = Message(
        message_type=MessageType.TASK_CREATE,
        sender="user_001",
        recipient="opencode",  # Send to OpenCode agent
        payload={
            "task_id": "test_task_001",
            "description": "创建一个简单的Python脚本",
            "user_message": "写一个Python脚本来计算斐波那契数列",
            "priority": "normal",
        },
    )

    def task_handler(msg: Message):
        print(f"📋 Task message received: {msg.message_type}")
        print(f"   Task ID: {msg.payload.get('task_id')}")
        print(f"   Description: {msg.payload.get('description')}")
        print()

    bus.subscribe(MessageType.TASK_CREATE, task_handler)

    await bus.publish(task_message)
    print("✅ Task message sent!")


async def send_feishu_message():
    """Send a Feishu message."""
    print("\n📱 Sending Feishu message...")

    bus = get_message_bus()

    feishu_message = Message(
        message_type=MessageType.SEND_CARD,
        sender="system",
        recipient="feishu",  # Send to Feishu agent
        payload={
            "chat_id": "test_chat_001",
            "card": {
                "header": {"title": "测试消息", "template": "blue"},
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "content": "这是一条来自OpenCode-Feishu Bridge的测试消息。",
                            "tag": "lark_md",
                        },
                    }
                ],
            },
        },
    )

    def feishu_handler(msg: Message):
        print(f"📱 Feishu message received: {msg.message_type}")
        print(f"   Chat ID: {msg.payload.get('chat_id')}")
        print(
            f"   Card title: {msg.payload.get('card', {}).get('header', {}).get('title')}"
        )
        print()

    bus.subscribe(MessageType.SEND_CARD, feishu_handler)

    await bus.publish(feishu_message)
    print("✅ Feishu message sent!")


async def test_message_routing():
    """Test message routing to specific agents."""
    print("\n🔄 Testing message routing...")

    bus = get_message_bus()

    # Register test agents
    bus.register_agent("agent_a")
    bus.register_agent("agent_b")

    # Create agent-specific handlers
    def agent_a_handler(msg: Message):
        print(
            f"👤 Agent A received: {msg.message_type} - {msg.payload.get('data', '')}"
        )

    def agent_b_handler(msg: Message):
        print(
            f"👤 Agent B received: {msg.message_type} - {msg.payload.get('data', '')}"
        )

    # Subscribe agents to specific messages
    bus.subscribe(MessageType.CUSTOM, agent_a_handler, agent_id="agent_a")
    bus.subscribe(MessageType.CUSTOM, agent_b_handler, agent_id="agent_b")

    # Send messages
    print("Sending to Agent A...")
    msg_to_a = Message(
        message_type=MessageType.CUSTOM,
        sender="test",
        recipient="agent_a",
        payload={"data": "Message for Agent A only"},
    )
    await bus.publish(msg_to_a)

    print("Sending to Agent B...")
    msg_to_b = Message(
        message_type=MessageType.CUSTOM,
        sender="test",
        recipient="agent_b",
        payload={"data": "Message for Agent B only"},
    )
    await bus.publish(msg_to_b)

    print("Broadcasting to all...")
    broadcast_msg = Message(
        message_type=MessageType.CUSTOM,
        sender="test",
        payload={"data": "Broadcast message for everyone"},
    )
    await bus.publish(broadcast_msg)

    print("✅ Message routing test completed!")


async def main():
    """Run all message tests."""
    print("=" * 60)
    print("OpenCode-Feishu Bridge - Message Sending Test")
    print("=" * 60)

    await send_simple_test()
    await send_task_message()
    await send_feishu_message()
    await test_message_routing()

    print("\n" + "=" * 60)
    print("所有测试消息已发送完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
