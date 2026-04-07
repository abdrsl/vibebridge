#!/usr/bin/env python3
"""
Demonstration of the complete message flow in OpenCode-Feishu Bridge.
"""

import asyncio
import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from message_bus.bus import Message, MessageType, get_message_bus


class MessageFlowDemo:
    """Demonstrate message flow between agents."""

    def __init__(self):
        self.bus = get_message_bus()
        self.message_count = 0

    async def setup_demo_agents(self):
        """Setup demo agents for the flow."""
        print("🤖 Setting up demo agents...")

        # Register demo agents
        self.bus.register_agent("user_interface")
        self.bus.register_agent("task_processor")
        self.bus.register_agent("llm_service")
        self.bus.register_agent("feishu_notifier")
        self.bus.register_agent("result_store")

        # Setup handlers for each agent
        self.setup_handlers()

        print("✅ Demo agents setup complete")
        print(f"   Registered agents: {self.bus.get_registered_agents()}")

    def setup_handlers(self):
        """Setup message handlers for demo agents."""

        # User Interface Agent - receives user requests
        def user_interface_handler(msg: Message):
            self.message_count += 1
            print(
                f"\n[{self.message_count}] 👤 User Interface received: {msg.message_type}"
            )
            print(f"   From: {msg.sender}")
            print(f"   Request: {msg.payload.get('user_request', '')[:50]}...")

            if msg.message_type == MessageType.TASK_CREATE:
                # Forward to task processor
                task_msg = Message(
                    message_type=MessageType.TASK_CREATE,
                    sender="user_interface",
                    recipient="task_processor",
                    payload={
                        "task_id": f"task_{int(time.time())}",
                        "user_request": msg.payload.get("user_request"),
                        "user_id": msg.payload.get("user_id", "anonymous"),
                        "priority": "normal",
                    },
                )
                asyncio.create_task(self.bus.publish(task_msg))

        self.bus.subscribe(
            MessageType.TASK_CREATE, user_interface_handler, agent_id="user_interface"
        )

        # Task Processor Agent - processes tasks
        def task_processor_handler(msg: Message):
            self.message_count += 1
            print(
                f"\n[{self.message_count}] ⚙️ Task Processor received: {msg.message_type}"
            )
            print(f"   Task ID: {msg.payload.get('task_id')}")

            if msg.message_type == MessageType.TASK_CREATE:
                # Send progress update
                progress_msg = Message(
                    message_type=MessageType.TASK_PROGRESS,
                    sender="task_processor",
                    recipient="feishu_notifier",
                    payload={
                        "task_id": msg.payload.get("task_id"),
                        "progress": "started",
                        "message": "任务已开始处理",
                        "timestamp": time.time(),
                    },
                )
                asyncio.create_task(self.bus.publish(progress_msg))

                # Forward to LLM service
                llm_msg = Message(
                    message_type=MessageType.LLM_REQUEST,
                    sender="task_processor",
                    recipient="llm_service",
                    payload={
                        "task_id": msg.payload.get("task_id"),
                        "prompt": f"请处理以下请求: {msg.payload.get('user_request')}",
                        "context": "用户请求处理",
                        "max_tokens": 500,
                    },
                )
                asyncio.create_task(self.bus.publish(llm_msg))

        self.bus.subscribe(
            MessageType.TASK_CREATE, task_processor_handler, agent_id="task_processor"
        )

        # LLM Service Agent - handles AI requests
        def llm_service_handler(msg: Message):
            self.message_count += 1
            print(
                f"\n[{self.message_count}] 🧠 LLM Service received: {msg.message_type}"
            )
            print(f"   Task ID: {msg.payload.get('task_id')}")
            print(f"   Prompt: {msg.payload.get('prompt', '')[:40]}...")

            if msg.message_type == MessageType.LLM_REQUEST:
                # Simulate LLM processing
                time.sleep(0.5)  # Simulate processing time

                # Send response
                response_msg = Message(
                    message_type=MessageType.LLM_RESPONSE,
                    sender="llm_service",
                    recipient="task_processor",
                    payload={
                        "task_id": msg.payload.get("task_id"),
                        "response": "这是一个模拟的AI响应。在实际系统中，这里会是真正的AI生成内容。",
                        "status": "completed",
                        "tokens_used": 150,
                    },
                )
                asyncio.create_task(self.bus.publish(response_msg))

        self.bus.subscribe(
            MessageType.LLM_REQUEST, llm_service_handler, agent_id="llm_service"
        )

        # Task Processor - handles LLM responses
        def task_processor_llm_handler(msg: Message):
            self.message_count += 1
            print(f"\n[{self.message_count}] ⚙️ Task Processor received LLM response")
            print(f"   Task ID: {msg.payload.get('task_id')}")
            print(f"   Response: {msg.payload.get('response', '')[:50]}...")

            if msg.message_type == MessageType.LLM_RESPONSE:
                # Send result to store
                result_msg = Message(
                    message_type=MessageType.TASK_RESULT,
                    sender="task_processor",
                    recipient="result_store",
                    payload={
                        "task_id": msg.payload.get("task_id"),
                        "result": msg.payload.get("response"),
                        "status": "completed",
                        "processed_by": "llm_service",
                    },
                )
                asyncio.create_task(self.bus.publish(result_msg))

                # Send notification
                notify_msg = Message(
                    message_type=MessageType.SEND_CARD,
                    sender="task_processor",
                    recipient="feishu_notifier",
                    payload={
                        "task_id": msg.payload.get("task_id"),
                        "chat_id": "demo_chat_001",
                        "card": {
                            "header": {"title": "任务完成", "template": "green"},
                            "elements": [
                                {
                                    "tag": "div",
                                    "text": {
                                        "content": f"任务 {msg.payload.get('task_id')} 已完成。",
                                        "tag": "lark_md",
                                    },
                                }
                            ],
                        },
                    },
                )
                asyncio.create_task(self.bus.publish(notify_msg))

        self.bus.subscribe(
            MessageType.LLM_RESPONSE,
            task_processor_llm_handler,
            agent_id="task_processor",
        )

        # Feishu Notifier Agent - sends notifications
        def feishu_notifier_handler(msg: Message):
            self.message_count += 1
            print(
                f"\n[{self.message_count}] 📱 Feishu Notifier received: {msg.message_type}"
            )

            if msg.message_type == MessageType.TASK_PROGRESS:
                print(f"   Progress: {msg.payload.get('progress')}")
                print(f"   Message: {msg.payload.get('message')}")
            elif msg.message_type == MessageType.SEND_CARD:
                print(f"   Sending card to chat: {msg.payload.get('chat_id')}")
                print(
                    f"   Card title: {msg.payload.get('card', {}).get('header', {}).get('title')}"
                )

        self.bus.subscribe(
            MessageType.TASK_PROGRESS,
            feishu_notifier_handler,
            agent_id="feishu_notifier",
        )
        self.bus.subscribe(
            MessageType.SEND_CARD, feishu_notifier_handler, agent_id="feishu_notifier"
        )

        # Result Store Agent - stores results
        def result_store_handler(msg: Message):
            self.message_count += 1
            print(
                f"\n[{self.message_count}] 💾 Result Store received: {msg.message_type}"
            )
            print(f"   Task ID: {msg.payload.get('task_id')}")
            print(f"   Status: {msg.payload.get('status')}")
            print("   Result stored successfully")

        self.bus.subscribe(
            MessageType.TASK_RESULT, result_store_handler, agent_id="result_store"
        )

    async def run_demo_flow(self):
        """Run the complete demo flow."""
        print("\n" + "=" * 60)
        print("🚀 Starting Message Flow Demo")
        print("=" * 60)

        await self.setup_demo_agents()

        print("\n📤 Sending demo user requests...")

        # Demo 1: Simple task
        print("\n--- Demo 1: 简单任务处理 ---")
        user_request_1 = Message(
            message_type=MessageType.TASK_CREATE,
            sender="demo_user_1",
            recipient="user_interface",
            payload={
                "user_request": "帮我写一个Python函数来计算圆的面积",
                "user_id": "user_001",
                "source": "feishu_chat",
            },
        )
        await self.bus.publish(user_request_1)

        # Wait for processing
        await asyncio.sleep(2)

        # Demo 2: Another task
        print("\n--- Demo 2: 另一个任务 ---")
        user_request_2 = Message(
            message_type=MessageType.TASK_CREATE,
            sender="demo_user_2",
            recipient="user_interface",
            payload={
                "user_request": "解释一下什么是RESTful API",
                "user_id": "user_002",
                "source": "web_interface",
            },
        )
        await self.bus.publish(user_request_2)

        # Wait for processing
        await asyncio.sleep(2)

        # Demo 3: Direct message to LLM
        print("\n--- Demo 3: 直接LLM请求 ---")
        direct_llm_request = Message(
            message_type=MessageType.LLM_REQUEST,
            sender="system_admin",
            recipient="llm_service",
            payload={
                "task_id": "direct_llm_001",
                "prompt": "用一句话解释人工智能",
                "context": "简单解释",
                "max_tokens": 100,
            },
        )
        await self.bus.publish(direct_llm_request)

        # Wait for final processing
        await asyncio.sleep(1)

        print("\n" + "=" * 60)
        print("📊 Demo Summary")
        print("=" * 60)
        print(f"Total messages processed: {self.message_count}")
        print(f"Agents involved: {len(self.bus.get_registered_agents())}")
        print("\n消息流程演示完成！")
        print("=" * 60)


async def demo_real_system_integration():
    """Demo integration with the real multi-agent system."""
    print("\n" + "=" * 60)
    print("🤖 Real System Integration Demo")
    print("=" * 60)

    try:
        from system import get_system

        system = get_system()
        if not system or not system.is_running():
            print("❌ Multi-agent system is not running")
            print("   Start the server first: python3 main.py")
            return

        print("✅ Multi-agent system is running")
        print(f"   Agents: {system.agent_count}")

        # Get message bus from system
        bus = system.message_bus

        # Send a test message to the real system
        print("\n📤 Sending test message to real agents...")

        test_message = Message(
            message_type=MessageType.CUSTOM,
            sender="demo_script",
            payload={
                "demo": "real_system_integration",
                "message": "这是一条发送到真实多智能体系统的测试消息",
                "timestamp": time.time(),
            },
        )

        # Subscribe to see the message
        def demo_handler(msg: Message):
            print(f"📨 Demo handler received: {msg.message_type} from {msg.sender}")
            print(f"   Payload: {msg.payload}")

        bus.subscribe(MessageType.CUSTOM, demo_handler)

        await bus.publish(test_message)

        # Wait a bit
        await asyncio.sleep(0.5)

        print("\n✅ Real system integration demo completed!")

    except ImportError as e:
        print(f"❌ Failed to import system: {e}")
    except Exception as e:
        print(f"❌ Error in real system demo: {e}")


async def main():
    """Run all demos."""
    print("OpenCode-Feishu Bridge - 消息系统演示")
    print("版本: 1.0.0")
    print("日期: 2026-04-06")
    print()

    # Create demo instance
    demo = MessageFlowDemo()

    # Run demos
    await demo.run_demo_flow()
    await demo_real_system_integration()

    print("\n🎉 所有演示完成！")
    print("\n总结:")
    print("- 消息总线系统工作正常")
    print("- 多智能体系统已集成")
    print("- 消息路由和处理器功能完整")
    print("- 系统可以通过HTTP API和内部消息总线进行通信")


if __name__ == "__main__":
    asyncio.run(main())
