"""
OpenClaw/OpenCode 审批系统集成模块
用于集成到 opencode-feishu-bridge 的 main.py

使用方式:
    from approval_integration import setup_approval_system

    # 在 main.py 中调用
    setup_approval_system(app, config)
"""

import os
import sys
from pathlib import Path

import yaml

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from approval_manager import (
        ApprovalManager,
        ApprovalWebHandler,
        ApprovalWebSocketHandler,
    )
except ImportError:
    print("⚠️  approval_manager.py 未找到，请确保它在同一目录")
    ApprovalManager = None


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""

    # 支持环境变量覆盖
    config = {
        "approval_server": {
            "host": os.getenv("APPROVAL_HOST", "0.0.0.0"),
            "port": int(os.getenv("APPROVAL_PORT", "8000")),
            "ws_endpoint": "/ws/approval",
            "api_prefix": "/api/approval",
            "webhook_endpoint": "/webhook/feishu",
        },
        "feishu_bot_a": {
            "webhook_url": os.getenv("FEISHU_BOT_A_WEBHOOK", ""),
            "secret": os.getenv("FEISHU_BOT_A_SECRET", ""),
            "enabled": bool(os.getenv("FEISHU_BOT_A_WEBHOOK")),
        },
        "logging": {"level": os.getenv("LOG_LEVEL", "INFO")},
    }

    # 从文件加载
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    # 合并配置
                    config.update(file_config)
        except Exception as e:
            print(f"⚠️  加载配置文件失败: {e}")

    return config


def setup_approval_system(app, config: dict = None) -> ApprovalManager:
    """
    设置审批系统

    Args:
        app: aiohttp Application 实例
        config: 配置字典，如果为None则自动加载

    Returns:
        ApprovalManager 实例
    """

    if ApprovalManager is None:
        print("❌ approval_manager 模块未加载，跳过审批系统设置")
        return None

    # 加载配置
    if config is None:
        config = load_config()

    # 获取飞书配置
    feishu_config = config.get("feishu_bot_a", {})
    webhook_url = feishu_config.get("webhook_url", "")
    secret = feishu_config.get("secret", "")

    if not webhook_url:
        print("⚠️  未配置飞书 Webhook URL，审批通知将使用终端模式")

    # 创建审批管理器
    approval_manager = ApprovalManager(webhook_url, secret)

    # 创建处理器
    web_handler = ApprovalWebHandler(approval_manager)
    ws_handler = ApprovalWebSocketHandler(approval_manager)

    # 获取端点配置
    server_config = config.get("approval_server", {})
    ws_endpoint = server_config.get("ws_endpoint", "/ws/approval")
    api_prefix = server_config.get("api_prefix", "/api/approval")
    webhook_endpoint = server_config.get("webhook_endpoint", "/webhook/feishu")

    # 添加路由
    # HTTP API
    app.router.add_post(f"{api_prefix}/create", web_handler.handle_create_approval)
    app.router.add_get(f"{api_prefix}/pending", web_handler.handle_list_pending)
    app.router.add_get(f"{api_prefix}/{{approval_id}}", web_handler.handle_get_approval)

    # 飞书 Webhook
    app.router.add_post(webhook_endpoint, web_handler.handle_feishu_webhook)

    # WebSocket
    app.router.add_get(ws_endpoint, ws_handler.handle)

    print("✅ 审批系统已启动:")
    print(f"   - WebSocket: {ws_endpoint}")
    print(f"   - HTTP API: {api_prefix}")
    print(f"   - Webhook: {webhook_endpoint}")

    return approval_manager


def create_simple_app():
    """创建简单的 aiohttp 应用（用于测试）"""

    from aiohttp import web

    app = web.Application()
    setup_approval_system(app)

    return app


# 如果直接运行此文件，启动测试服务器
if __name__ == "__main__":
    from aiohttp import web

    print("🚀 启动审批系统测试服务器...")

    app = create_simple_app()

    if app is None:
        print("❌ 启动失败")
        sys.exit(1)

    # 启动服务器
    web.run_app(app, host="0.0.0.0", port=8000)
