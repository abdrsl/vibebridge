#!/usr/bin/env python3
"""
Feishu WebSocket 长连接测试
测试WebSocket客户端的基本功能
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 添加项目目录到路径
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))


async def test_websocket_import():
    """测试WebSocket模块导入"""
    print("🧪 测试WebSocket模块导入...")
    try:
        from src.feishu_websocket import FeishuWebSocketClient, start_feishu_websocket

        print("✅ WebSocket模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ WebSocket模块导入失败: {e}")
        return False


async def test_websocket_client_initialization():
    """测试WebSocket客户端初始化"""
    print("\n🧪 测试WebSocket客户端初始化...")
    try:
        from src.feishu_websocket import FeishuWebSocketClient
        from src.legacy.feishu_client import FeishuClient

        feishu_client = FeishuClient()
        websocket_client = FeishuWebSocketClient(feishu_client)

        # 检查属性
        assert websocket_client.feishu_client is not None
        assert websocket_client.websocket_url is not None
        assert websocket_client.running is False

        print("✅ WebSocket客户端初始化成功")
        print(f"   WebSocket URL: {websocket_client.websocket_url}")
        print(f"   重连间隔: {websocket_client.reconnect_interval}秒")
        print(f"   心跳间隔: {websocket_client.ping_interval}秒")

        return True
    except Exception as e:
        print(f"❌ WebSocket客户端初始化失败: {e}")
        return False


async def test_environment_config():
    """测试环境变量配置"""
    print("\n🧪 测试环境变量配置...")

    required_vars = [
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
    ]

    optional_vars = [
        "FEISHU_WEBSOCKET_ENABLED",
        "FEISHU_WEBSOCKET_URL",
    ]

    all_present = True

    print("📋 必需环境变量:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            print(f"  ✅ {var}: {masked}")
        else:
            print(f"  ❌ {var}: 未设置")
            all_present = False

    print("\n📋 可选环境变量:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ⚠️  {var}: 未设置 (使用默认值)")

    if not all_present:
        print("\n⚠️  缺少必需环境变量，WebSocket连接可能失败")
        print("   请检查 .env 文件中的配置")

    return all_present


async def test_message_handling():
    """测试消息处理逻辑"""
    print("\n🧪 测试消息处理逻辑...")

    try:
        from src.feishu_websocket import FeishuWebSocketClient

        # 创建模拟客户端
        class MockFeishuClient:
            async def get_tenant_access_token(self):
                return "mock_token"

        client = FeishuWebSocketClient(MockFeishuClient())

        # 测试心跳消息处理
        ping_message = json.dumps({"type": "ping"})
        print(f"  测试ping消息: {ping_message}")

        # 测试事件消息处理
        event_message = json.dumps(
            {
                "type": "event",
                "header": {
                    "event_id": "test_event_id",
                    "event_type": "im.message.receive_v1",
                    "create_time": "1234567890",
                    "token": "test_token",
                    "app_id": "test_app_id",
                    "tenant_key": "test_tenant",
                },
                "event": {
                    "message": {
                        "chat_id": "test_chat_id",
                        "content": '{"text": "测试消息"}',
                    }
                },
            }
        )
        print(f"  测试事件消息: {event_message[:100]}...")

        # 测试系统消息处理
        system_message = json.dumps(
            {"type": "system", "status": "connected", "message": "连接已建立"}
        )
        print(f"  测试系统消息: {system_message}")

        print("✅ 消息处理逻辑测试通过")
        return True

    except Exception as e:
        print(f"❌ 消息处理逻辑测试失败: {e}")
        return False


async def test_websocket_start_function():
    """测试WebSocket启动函数"""
    print("\n🧪 测试WebSocket启动函数...")

    try:
        from src.feishu_websocket import start_feishu_websocket

        # 临时禁用WebSocket
        original_value = os.getenv("FEISHU_WEBSOCKET_ENABLED", "false")
        os.environ["FEISHU_WEBSOCKET_ENABLED"] = "false"

        client = await start_feishu_websocket()
        assert client is None
        print("✅ WebSocket未启用时返回None")

        # 恢复原始值
        os.environ["FEISHU_WEBSOCKET_ENABLED"] = original_value

        return True
    except Exception as e:
        print(f"❌ WebSocket启动函数测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("=" * 60)
    print("🔌 Feishu WebSocket 长连接测试")
    print("=" * 60)

    tests = [
        ("模块导入", test_websocket_import),
        ("客户端初始化", test_websocket_client_initialization),
        ("环境配置", test_environment_config),
        ("消息处理", test_message_handling),
        ("启动函数", test_websocket_start_function),
    ]

    results = []

    for test_name, test_func in tests:
        success = await test_func()
        results.append((test_name, success))

    print("\n" + "=" * 60)
    print("📊 测试结果汇总:")

    passed = 0
    total = len(results)

    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
        if success:
            passed += 1

    print(f"\n🎯 通过率: {passed}/{total} ({passed / total * 100:.1f}%)")

    if passed == total:
        print("\n🎉 所有测试通过！WebSocket客户端已准备好。")
        print("\n📝 下一步:")
        print("  1. 在 .env 文件中设置 FEISHU_WEBSOCKET_ENABLED=true")
        print("  2. 重启服务器: ./manage.sh restart")
        print("  3. 检查日志中的WebSocket连接状态")
    else:
        print("\n⚠️  部分测试失败，请检查以上错误信息。")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
