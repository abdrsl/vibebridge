"""
OpenCode-Feishu Bridge - Main FastAPI application with multi-agent architecture.
"""
import logging
import os
import sys

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles as _StaticFiles

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from vibebridge.admin.router import router as admin_router
from vibebridge.config import get_config
from vibebridge.limiter import limiter
from vibebridge.system import start_multi_agent_system, stop_multi_agent_system

# Route modules
from vibebridge.routes import dashboard, feishu, internal, legacy, opencode, system

logger = logging.getLogger(__name__)

APPROVAL_SYSTEM_ENABLED = False  # 已禁用

# WebSocket 长连接支持
FEISHU_WEBSOCKET_AVAILABLE = False
start_feishu_websocket = None

try:
    from vibebridge.feishu_websocket import FeishuWebSocketClient

    FEISHU_WEBSOCKET_AVAILABLE = True
except ImportError:
    print("[WebSocket] 模块未找到，WebSocket功能不可用")
    FeishuWebSocketClient = None

# 显式加载 .env，确保无论从哪里启动都能找到
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with multi-agent system."""
    print("App starting...")
    print("[System] Starting multi-agent system...")
    try:
        await start_multi_agent_system()
    except Exception as e:
        print(f"[System] Error starting multi-agent system: {e}")
        # Continue without multi-agent system

    # 启动Feishu WebSocket客户端（每个bot一个连接）
    websocket_clients = []
    ws_enabled = os.environ.get("FEISHU_WEBSOCKET_ENABLED", "true").lower() in ("true", "1", "yes")
    if ws_enabled and FEISHU_WEBSOCKET_AVAILABLE and FeishuWebSocketClient:
        # Start WebSocket for bots configured via YAML or env
        try:
            cfg = get_config()
            for bot_cfg in cfg.feishu.bots:
                if bot_cfg.enabled and bot_cfg.app_id and bot_cfg.app_secret:
                    client = FeishuWebSocketClient(
                        app_id=bot_cfg.app_id,
                        app_secret=bot_cfg.app_secret
                    )
                    await client.start()
                    websocket_clients.append(client)
                    print(f"[WebSocket] ✅ {bot_cfg.agent} started (using {bot_cfg.app_id[:8]}...)")
            if not websocket_clients:
                # Fallback to legacy single-bot config
                if cfg.feishu.app_id and cfg.feishu.app_secret:
                    client = FeishuWebSocketClient(
                        app_id=cfg.feishu.app_id,
                        app_secret=cfg.feishu.app_secret
                    )
                    await client.start()
                    websocket_clients.append(client)
                    print(f"[WebSocket] ✅ default bot started")
                else:
                    print("[WebSocket] ⚠️ No valid bot credentials in config")
        except Exception as e:
            print(f"[WebSocket] ⚠️ Failed: {e} — falling back to webhook mode")
    else:
        print("[WebSocket] Using webhook mode (messages via HTTP webhook)")

    # Start unified outbox listener (bidirectional sync: SQLite + Feishu)
    from vibebridge.outbox_listener import OutboxListener

    outbox_listener = OutboxListener()
    outbox_listener.start()

    yield

    outbox_listener.stop()
    for client in websocket_clients:
        try:
            await client.stop()
            print("[WebSocket] Feishu WebSocket客户端已停止")
        except Exception as e:
            print(f"[WebSocket] 停止Feishu WebSocket客户端时出错: {e}")

    print("App shutting down...")
    try:
        await stop_multi_agent_system()
    except Exception as e:
        print(f"[System] Error stopping multi-agent system: {e}")


app = FastAPI(
    title="OpenCode-Feishu Bridge - Multi-Agent System",
    version="1.1.0",
    description="Open-source AI coding agent service with Feishu integration",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
origins = [
    item.strip()
    for item in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Admin panel
app.include_router(admin_router)

# Static files — serve dashboard assets if DASHBOARD_DIR is set
_dashboard_dir = os.environ.get("VIBEBRIDGE_DASHBOARD_DIR", os.environ.get("DASHBOARD_DIR", ""))
if os.path.isdir(_dashboard_dir):
    app.mount("/dashboard/static", _StaticFiles(directory=_dashboard_dir, html=True), name="dashboard_static")
    app.mount("/dashboard", _StaticFiles(directory=_dashboard_dir, html=True), name="dashboard")

# Register route modules
app.include_router(system.router)
app.include_router(legacy.router)
app.include_router(feishu.router)
app.include_router(opencode.router)
app.include_router(internal.router)
app.include_router(dashboard.router)

# Approval system loaded via vibebridge.server. No external dependencies.


# ============================================
# Approval System Routes (机器人C)
# ============================================
# try:
#     from vibebridge.approval import register_approval_routes
#     register_approval_routes(app)
#     print("✅ Approval routes registered (机器人C)")
# except Exception as e:
#     print(f"⚠️ Approval routes registration failed: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
