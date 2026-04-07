#!/usr/bin/env python3
"""
Test script for message bus system.
"""

import asyncio
import logging
import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from message_bus.bus import Message, MessageType, get_message_bus

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def test_message_bus():
    """Test the message bus functionality."""
    print("🚀 Starting message bus test...")

    # Get message bus
    bus = get_message_bus()

    # Test 1: Register agents
    print("\n📝 Test 1: Registering agents...")
    bus.register_agent("test_agent_1")
    bus.register_agent("test_agent_2")

    registered = bus.get_registered_agents()
    print(f"Registered agents: {registered}")

    # Test 2: Subscribe and publish messages
    print("\n📨 Test 2: Subscribing and publishing messages...")

    def global_handler(message: Message):
        print(
            f"[Global Handler] Received {message.message_type} from {message.sender}: {message.payload}"
        )

    def agent_handler(message: Message):
        print(
            f"[Agent Handler] Agent {message.recipient} received {message.message_type} from {message.sender}: {message.payload}"
        )

    # Subscribe global handler
    bus.subscribe(MessageType.CUSTOM, global_handler)

    # Subscribe agent-specific handler
    bus.subscribe(MessageType.CUSTOM, agent_handler, agent_id="test_agent_1")

    # Create and publish messages
    print("\n📤 Publishing messages...")

    # Broadcast message
    message1 = Message(
        message_type=MessageType.CUSTOM,
        sender="test_sender",
        payload={"action": "test_broadcast", "data": "Hello everyone!"},
    )
    await bus.publish(message1)

    # Direct message to specific agent
    message2 = Message(
        message_type=MessageType.CUSTOM,
        sender="test_sender",
        recipient="test_agent_1",
        payload={"action": "test_direct", "data": "Hello agent 1!"},
    )
    await bus.publish(message2)

    # Message to non-existent agent (should not be delivered)
    message3 = Message(
        message_type=MessageType.CUSTOM,
        sender="test_sender",
        recipient="non_existent_agent",
        payload={"action": "test_missing", "data": "This should not be delivered"},
    )
    await bus.publish(message3)

    # Test 3: Different message types
    print("\n🎯 Test 3: Testing different message types...")

    def task_handler(message: Message):
        print(f"[Task Handler] Task {message.message_type}: {message.payload}")

    bus.subscribe(MessageType.TASK_CREATE, task_handler)

    task_message = Message(
        message_type=MessageType.TASK_CREATE,
        sender="user_123",
        payload={
            "task_id": "task_001",
            "description": "Test task creation",
            "priority": "high",
        },
    )
    await bus.publish(task_message)

    # Test 4: System messages
    print("\n⚙️ Test 4: Testing system messages...")

    def registration_handler(message: Message):
        print(f"[Registration Handler] Agent registered: {message.payload}")

    bus.subscribe(MessageType.REGISTER, registration_handler)

    register_message = Message(
        message_type=MessageType.REGISTER,
        sender="new_agent",
        payload={
            "agent_id": "agent_001",
            "agent_name": "Test Agent",
            "capabilities": ["process", "analyze", "report"],
        },
    )
    await bus.publish(register_message)

    # Test 5: Performance test
    print("\n⚡ Test 5: Performance test (sending 10 messages)...")

    start_time = time.time()

    async def send_messages():
        for i in range(10):
            msg = Message(
                message_type=MessageType.CUSTOM,
                sender=f"perf_sender_{i}",
                payload={"index": i, "timestamp": time.time()},
            )
            await bus.publish(msg)
            await asyncio.sleep(0.01)  # Small delay

    await send_messages()

    end_time = time.time()
    print(f"Sent 10 messages in {end_time - start_time:.3f} seconds")

    # Test 6: Error handling
    print("\n⚠️ Test 6: Testing error handling...")

    def error_handler(message: Message):
        raise ValueError("Intentional error in handler")

    bus.subscribe(MessageType.CUSTOM, error_handler)

    error_message = Message(
        message_type=MessageType.CUSTOM,
        sender="error_test",
        payload={"test": "error handling"},
    )

    try:
        await bus.publish(error_message)
        print("Error handled gracefully")
    except Exception as e:
        print(f"Error caught: {e}")

    print("\n✅ All tests completed!")


async def test_multi_agent_system():
    """Test the multi-agent system."""
    print("\n🤖 Testing multi-agent system...")

    try:
        from system import (
            start_multi_agent_system,
            stop_multi_agent_system,
        )

        print("Starting multi-agent system...")
        system = await start_multi_agent_system()

        # Wait for system to start
        await asyncio.sleep(1)

        if system and system.is_running():
            print(f"✅ Multi-agent system is running with {len(system.agents)} agents")

            # List agents
            agents = system.list_agents()
            print("\n📋 Registered agents:")
            for agent in agents:
                print(f"  - {agent['name']} ({agent['id']}): {agent['running']}")

            # Test message bus through system
            bus = get_message_bus()
            print(
                f"\n📡 Message bus has {len(bus.get_registered_agents())} registered agents"
            )

            # Send a test message
            test_msg = Message(
                message_type=MessageType.CUSTOM,
                sender="test_script",
                payload={"test": "multi_agent_system", "status": "working"},
            )
            await bus.publish(test_msg)

            # Wait a bit for message processing
            await asyncio.sleep(0.5)

            # Stop system
            print("\nStopping multi-agent system...")
            await stop_multi_agent_system()
            print("✅ Multi-agent system stopped")
        else:
            print("❌ Failed to start multi-agent system")

    except Exception as e:
        print(f"❌ Error testing multi-agent system: {e}")
        import traceback

        traceback.print_exc()


async def test_feishu_integration():
    """Test Feishu integration."""
    print("\n📱 Testing Feishu integration...")

    try:
        # Check if Feishu client can be imported
        from legacy.feishu_client import feishu_client

        print("✅ Feishu client imported successfully")

        # Test configuration
        import os

        from legacy.secure_config import get_secret

        feishu_app_id = os.getenv("FEISHU_APP_ID")
        feishu_app_secret = get_secret("FEISHU_APP_SECRET")

        print(f"FEISHU_APP_ID: {'✅ Present' if feishu_app_id else '❌ Missing'}")
        print(
            f"FEISHU_APP_SECRET: {'✅ Present' if feishu_app_secret else '❌ Missing'}"
        )

        if feishu_app_id and feishu_app_secret:
            print("✅ Feishu configuration looks good")
        else:
            print("⚠️  Feishu configuration incomplete - some features may not work")

    except ImportError as e:
        print(f"❌ Failed to import Feishu client: {e}")
    except Exception as e:
        print(f"❌ Error testing Feishu integration: {e}")


async def test_opencode_integration():
    """Test OpenCode integration."""
    print("\n💻 Testing OpenCode integration...")

    try:
        from legacy.opencode_integration import opencode_manager

        print("✅ OpenCode manager imported successfully")

        # Test creating a simple task
        print("Creating test task...")
        task_id = await opencode_manager.create_task(
            user_message="Test message from integration test", feishu_chat_id=None
        )

        print(f"✅ Created task with ID: {task_id}")

        # Get task info
        task = await opencode_manager.get_task(task_id)
        if task:
            print(f"Task status: {task.status.value}")
            print(f"User message: {task.user_message[:50]}...")
        else:
            print("❌ Failed to retrieve task")

    except ImportError as e:
        print(f"❌ Failed to import OpenCode manager: {e}")
    except Exception as e:
        print(f"❌ Error testing OpenCode integration: {e}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("OpenCode-Feishu Bridge - Message System Test")
    print("=" * 60)

    # Run tests
    await test_message_bus()
    await test_multi_agent_system()
    await test_feishu_integration()
    await test_opencode_integration()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
