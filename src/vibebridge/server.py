"""FastAPI server for VibeBridge."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from .approval import ApprovalAction, ApprovalStatus
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

    try:
        providers = build_providers(cfg.agents)
        print(f"[VibeBridge] Providers loaded: {list(providers.keys())}")
    except Exception as e:
        print(f"[VibeBridge] WARNING: Some providers failed to load: {e}")
        providers = {}

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
    version="1.1.0",
    description="Universal IM gateway for local AI coding agents",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {
        "name": "VibeBridge",
        "version": "1.1.0",
        "status": "ok",
    }


@app.get("/health")
async def health(request: Request):
    orchestrator: TaskOrchestrator = request.app.state.orchestrator
    # Each provider health check gets its own 10s timeout so a single hanging provider
    # doesn't block the entire /health endpoint.
    try:
        health = await asyncio.wait_for(
            orchestrator.router.health_table(),
            timeout=15.0,
        )
    except Exception as e:
        return {
            "ok": False,
            "timestamp": __import__("time").time(),
            "error": str(e),
            "providers": {},
        }
    return {
        "ok": True,
        "timestamp": __import__("time").time(),
        "providers": {k: {"healthy": v[0], "message": v[1]} for k, (v) in health.items()},
    }


@app.get("/system/status")
async def system_status(request: Request):
    try:
        health = await asyncio.wait_for(
            request.app.state.router.health_table(),
            timeout=15.0,
        )
    except Exception as e:
        return {
            "error": str(e),
            "config_file": str(request.app.state.cfg.config_file),
        }
    return {
        "providers": {
            k: {"healthy": v[0], "message": v[1]} for k, v in health.items()
        },
        "config_file": str(request.app.state.cfg.config_file),
    }


@app.post("/im/feishu/webhook")
async def feishu_webhook(request: Request):
    """New unified Feishu webhook endpoint."""
    try:
        body = await request.json()
    except Exception as e:
        return {
            "ok": True,
            "status": "error",
            "reason": f"Invalid JSON body: {e}",
        }

    # Handle URL verification challenge
    if "challenge" in body:
        return {"challenge": body["challenge"]}

    orchestrator: TaskOrchestrator = request.app.state.orchestrator
    im_adapter: FeishuAdapter = request.app.state.im_adapter

    # 检查是否是卡片交互事件
    schema = body.get("schema", "")
    event_type = ""
    
    if schema == "2.0":
        header = body.get("header", {})
        event_type = header.get("event_type", "")
        event = body.get("event", {})
    else:
        event = body.get("event", {})
        event_type = body.get("event_type", "")
    
    # 处理卡片动作触发事件
    if event_type == "card.action.trigger":
        return await handle_card_action_trigger(event, orchestrator)
    
    # 处理IM消息
    try:
        message = await im_adapter.parse_incoming(body)
    except ValueError as e:
        # Common for duplicates or unhandled events
        return {"ok": True, "skipped": True, "reason": str(e)}
    except Exception as e:
        return {"ok": True, "skipped": True, "reason": f"Parse error: {e}"}

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


async def handle_card_action_trigger(event: dict, orchestrator: TaskOrchestrator) -> dict:
    """处理卡片动作触发事件"""
    import json
    
    print(f"[Card] Processing card action trigger: {json.dumps(event, ensure_ascii=False)[:300]}...")
    
    # 获取动作信息
    action = event.get("action", {})
    action_value = action.get("value", "{}")
    operator = event.get("operator", {})
    context = event.get("context", {})
    
    # 解析动作数据
    action_data = None
    value_str = action_value if isinstance(action_value, str) else str(action_value)
    
    # 尝试解析JSON
    try:
        action_data = json.loads(value_str)
    except json.JSONDecodeError:
        # 尝试清理字符串
        try:
            cleaned = value_str.strip()
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1].replace('\\"', '"')
                action_data = json.loads(cleaned)
        except Exception:
            pass
    
    if not action_data or not isinstance(action_data, dict):
        print(f"[Card] Failed to parse action data: {value_str[:200]}")
        return {"ok": True, "action": "processed", "response": {}}
    
    print(f"[Card] Parsed action data: {action_data}")
    
    # 检查是否是审批动作
    action_type = action_data.get("action")
    if action_type in ("approve", "reject"):
        return await handle_approval_card_action(action_data, operator, context, orchestrator)
    
    # 其他卡片动作暂时返回成功
    return {"ok": True, "action": "processed", "response": {}}


async def handle_approval_card_action(
    action_data: dict,
    operator: dict,
    context: dict,
    orchestrator: TaskOrchestrator,
) -> dict:
    """处理审批卡片动作"""
    action_type = action_data.get("action")
    request_id = action_data.get("request_id")
    approval_type = action_data.get("type")
    
    if not request_id or not approval_type:
        print(f"[Card] Missing request_id or type in approval action: {action_data}")
        return {"ok": True, "action": "processed", "response": {}}
    
    # 获取操作者ID
    operator_id = operator.get("open_id", "") or operator.get("user_id", "unknown")
    
    # 映射动作类型
    if action_type == "approve":
        if approval_type == "allow-once":
            approval_action = ApprovalAction.ALLOW_ONCE
        elif approval_type == "allow-always":
            approval_action = ApprovalAction.ALLOW_ALWAYS
        else:
            print(f"[Card] Unknown approval type: {approval_type}")
            return {"ok": True, "action": "processed", "response": {}}
    elif action_type == "reject":
        approval_action = ApprovalAction.DENY
    else:
        print(f"[Card] Unknown action type: {action_type}")
        return {"ok": True, "action": "processed", "response": {}}
    
    # 处理审批动作
    success, request = await orchestrator.approval_manager.process_approval_action(
        request_id, approval_action, operator_id
    )
    
    if success:
        print(f"[Card] Approval action processed successfully: {action_type} {approval_type}")
        
        # 如果审批通过，检查是否有待处理的任务
        if approval_action != ApprovalAction.DENY:
            await orchestrator._process_approved_task(request_id)
        
        # 返回成功响应给飞书
        return {"ok": True, "action": "processed", "response": {}}
    else:
        print(f"[Card] Failed to process approval action: {request_id}")
        return {"ok": True, "action": "processed", "response": {}}


# Backward compatibility: legacy endpoint aliases
@app.post("/feishu/webhook/opencode")
async def feishu_webhook_legacy_opencode(request: Request):
    """Backward-compatible endpoint for existing Feishu console configs."""
    return await feishu_webhook(request)


@app.post("/feishu/webhook")
async def feishu_webhook_legacy(request: Request):
    """Backward-compatible generic endpoint."""
    return await feishu_webhook(request)
