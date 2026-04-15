"""FastAPI server for VibeBridge."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import get_config
from .im.feishu import FeishuAdapter
from .providers import build_providers
from .router import ProviderRouter
from .session import get_session_manager
from .tasks import ApprovalEngine, TaskOrchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[VibeBridge] Starting up...")
    cfg = get_config()
    print(f"[VibeBridge] Config loaded from {cfg.config_dir}")

    providers = build_providers(cfg.agents)
    print(f"[VibeBridge] Providers loaded: {list(providers.keys())}")

    router = ProviderRouter(cfg.agents, providers)
    im_adapter = FeishuAdapter(cfg.feishu)
    sessions = get_session_manager()
    approval = ApprovalEngine(cfg.approval) if cfg.approval.enabled else None

    orchestrator = TaskOrchestrator(router, im_adapter, sessions, approval)

    app.state.cfg = cfg
    app.state.providers = providers
    app.state.router = router
    app.state.im_adapter = im_adapter
    app.state.orchestrator = orchestrator

    yield

    print("[VibeBridge] Shutting down...")


app = FastAPI(
    title="VibeBridge",
    version="0.2.0",
    description="Universal IM gateway for local AI coding agents",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {
        "name": "VibeBridge",
        "version": "0.2.0",
        "status": "ok",
    }


@app.get("/health")
async def health(request: Request):
    orchestrator: TaskOrchestrator = request.app.state.orchestrator
    health = await orchestrator.router.health_table()
    return {
        "ok": True,
        "timestamp": __import__("time").time(),
        "providers": {k: {"healthy": v[0], "message": v[1]} for k, (v) in health.items()},
    }


@app.get("/system/status")
async def system_status(request: Request):
    health = await request.app.state.router.health_table()
    return {
        "providers": {
            k: {"healthy": v[0], "message": v[1]} for k, v in health.items()
        },
        "config_file": str(request.app.state.cfg.config_file),
    }


@app.post("/im/feishu/webhook")
async def feishu_webhook(request: Request):
    """New unified Feishu webhook endpoint."""
    body = await request.json()

    # Handle URL verification challenge
    if "challenge" in body:
        return {"challenge": body["challenge"]}

    orchestrator: TaskOrchestrator = request.app.state.orchestrator
    im_adapter: FeishuAdapter = request.app.state.im_adapter

    try:
        message = await im_adapter.parse_incoming(body)
    except ValueError as e:
        # Common for duplicates or unhandled events
        return {"ok": True, "skipped": True, "reason": str(e)}

    # Group messages must @bot
    if message.chat_type == "group" and not message.is_bot_mentioned:
        return {"ok": True, "skipped": True, "reason": "Bot not mentioned in group"}

    try:
        result = await orchestrator.handle_message(message)
        return {"ok": True, **result}
    except Exception as e:
        print(f"[Webhook] Unhandled error in handle_message: {e}")
        return {
            "ok": True,
            "status": "error",
            "reason": f"Internal error: {e}",
        }


# Backward compatibility: legacy endpoint aliases
@app.post("/feishu/webhook/opencode")
async def feishu_webhook_legacy_opencode(request: Request):
    """Backward-compatible endpoint for existing Feishu console configs."""
    return await feishu_webhook(request)


@app.post("/feishu/webhook")
async def feishu_webhook_legacy(request: Request):
    """Backward-compatible generic endpoint."""
    return await feishu_webhook(request)
