"""FastAPI server for VibeBridge."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader

from .approval import ApprovalAction, ApprovalStatus
from .config import get_config
from .im.feishu import FeishuMultiBotManager, FeishuBotCredentials
from .providers import build_providers
from .router import ProviderRouter
from .session import get_session_manager
from .tasks import ApprovalEngine, TaskOrchestrator
from .agent_bridge import AgentResultBridge, AgentTaskDispatcher, AutoReviewRouter

from mycompany.core.tracing import trace_span


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
    sessions = get_session_manager()
    approval = ApprovalEngine(cfg.approval) if cfg.approval.enabled else None

    # ── Feishu Multi-Bot Setup ──────────────────────────────────────
    feishu_bots: list[FeishuBotCredentials] = []
    try:
        from mycompany.config.bots import BotRegistry
        registry = BotRegistry()
        for bot_cfg in registry.list_all():
            if bot_cfg.enabled and bot_cfg.app_id:
                # Load secret from SecretsManager
                from mycompany.config.secrets import SecretsManager
                sm = SecretsManager()
                prefix = f"FEISHU_{bot_cfg.agent.replace('-', '_').upper()}"
                secret = sm.get(f"{prefix}_APP_SECRET") or ""
                if secret:
                    feishu_bots.append(FeishuBotCredentials(
                        agent=bot_cfg.agent,
                        app_id=bot_cfg.app_id,
                        app_secret=secret,
                        encrypt_key=bot_cfg.encrypt_key or "",
                        verification_token=bot_cfg.verify_token or "",
                    ))
        print(f"[VibeBridge] Loaded {len(feishu_bots)} Feishu bots from BotRegistry")
    except Exception as e:
        print(f"[VibeBridge] BotRegistry not available: {e}")

    # Fallback to legacy single-bot config
    if not feishu_bots and cfg.feishu.app_id and cfg.feishu.app_secret:
        feishu_bots.append(FeishuBotCredentials(
            agent="default",
            app_id=cfg.feishu.app_id,
            app_secret=cfg.feishu.app_secret,
            encrypt_key=cfg.feishu.encrypt_key,
            verification_token=cfg.feishu.verification_token,
        ))

    im_adapter = FeishuMultiBotManager(feishu_bots)
    orchestrator = TaskOrchestrator(router, im_adapter, sessions, approval)

    # ── Agent Bridge: Redis ↔ Feishu ────────────────────────────────
    redis_client = None
    agent_bridge = None
    agent_dispatcher = None
    try:
        import redis as _redis_lib
        from mycompany.core.config_manager import get_config as _get_mc_config
        rcfg = _get_mc_config().redis
        redis_client = _redis_lib.Redis(
            host=rcfg.host, port=rcfg.port,
            password=rcfg.password, decode_responses=True,
        )
        agent_bridge = AgentResultBridge(redis_client, im_adapter)
        agent_bridge.start()
        agent_dispatcher = AgentTaskDispatcher(redis_client)
        auto_review = AutoReviewRouter(redis_client)
        auto_review.start()
        print("[VibeBridge] AgentBridge + AutoReview connected to Redis")
    except Exception as e:
        print(f"[VibeBridge] AgentBridge not available: {e}")
        auto_review = None

    # ── Autonomous Trigger: 7×24 self-triggered tasks ─────────────
    auto_trigger = None
    try:
        from mycompany.core.autonomous_trigger import AutonomousTrigger
        if redis_client:
            auto_trigger = AutonomousTrigger(redis_client)
            auto_trigger.start()
            print(f"[VibeBridge] AutonomousTrigger started with {len(auto_trigger.list_triggers())} triggers")
    except Exception as e:
        print(f"[VibeBridge] AutonomousTrigger not available: {e}")

    # ── Workflow Engine: multi-agent pipeline orchestration ─────────
    workflow_engine = None
    try:
        from mycompany.core.workflow_engine import WorkflowEngine
        if redis_client:
            workflow_engine = WorkflowEngine(redis_client)
            workflow_engine.start_listener()
            print("[VibeBridge] WorkflowEngine listener started")
    except Exception as e:
        print(f"[VibeBridge] WorkflowEngine not available: {e}")

    app.state.cfg = cfg
    app.state.providers = providers
    app.state.router = router
    app.state.im_adapter = im_adapter
    app.state.orchestrator = orchestrator
    app.state.redis = redis_client
    app.state.agent_bridge = agent_bridge
    app.state.agent_dispatcher = agent_dispatcher
    app.state.auto_review = auto_review
    app.state.auto_trigger = auto_trigger
    app.state.workflow_engine = workflow_engine
    app.state.feishu_bots = feishu_bots

    yield

    print("[VibeBridge] Shutting down...")
    if auto_trigger:
        auto_trigger.stop()
    if agent_bridge:
        agent_bridge.stop()
    if auto_review:
        auto_review.stop()
    if workflow_engine:
        workflow_engine.stop()


# --------------------------------------------------------------------------- #
#  API Key auth for enterprise dashboard endpoints
# --------------------------------------------------------------------------- #

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _load_dashboard_api_key() -> str | None:
    try:
        import os, sys
        mycompany_src = os.environ.get("MYCOMPANY_HOME", os.path.expanduser("~/workspace/MyCompany"))
        sys.path.insert(0, os.path.join(mycompany_src, "src"))
        from mycompany.core.config_manager import ConfigManager
        return ConfigManager.get_secret("system.api_key")
    except Exception:
        return None


async def verify_api_key(api_key: str | None = Depends(api_key_header)) -> None:
    expected = _load_dashboard_api_key()
    if expected and api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


# ── Rate limiting middleware ────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter: 100 req/min per IP."""
    _requests: dict[str, list[float]] = {}
    _limit = 100
    _window = 60.0

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self._window
        reqs = self._requests.get(client, [])
        reqs = [t for t in reqs if t > window_start]
        if len(reqs) >= self._limit:
            return Response("Rate limit exceeded", status_code=429)
        reqs.append(now)
        self._requests[client] = reqs
        return await call_next(request)

app = FastAPI(
    title="VibeBridge",
    version="1.1.0",
    description="Universal IM gateway for local AI coding agents",
    lifespan=lifespan,
)
app.add_middleware(RateLimitMiddleware)

# Admin panel
from vibebridge.admin.router import router as admin_router
app.include_router(admin_router)


@app.get("/")
def root():
    return {
        "name": "VibeBridge",
        "version": "1.1.0",
        "status": "ok",
    }


@app.get("/live")
async def liveness():
    """Kubernetes liveness probe — always returns 200 if process is running."""
    return {"status": "alive", "timestamp": __import__("time").time()}


@app.get("/ready")
async def readiness():
    """Kubernetes readiness probe — checks Redis connectivity."""
    try:
        import sys, os
        mycompany_src = os.environ.get("MYCOMPANY_HOME", os.path.expanduser("~/workspace/MyCompany"))
        sys.path.insert(0, os.path.join(mycompany_src, "src"))
        from mycompany.core.config_manager import get_config
        import redis as _redis_lib
        rcfg = get_config().redis
        r = _redis_lib.Redis(
            host=rcfg.host, port=rcfg.port,
            password=rcfg.password, decode_responses=True,
            socket_connect_timeout=2,
        )
        r.ping()
        return {"status": "ready", "redis": True}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Not ready: {exc}")


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


# ── Workflow Endpoints ──────────────────────────────────────────────

@app.post("/workflow/start")
@trace_span("api.workflow.start")
async def workflow_start(request: Request):
    """Start a new multi-agent workflow."""
    body = await request.json()
    template = body.get("template")
    context = body.get("context", {})
    engine = getattr(request.app.state, "workflow_engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="WorkflowEngine not available")
    try:
        wf_id = engine.start(template, context)
        return {"ok": True, "workflow_id": wf_id, "template": template}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/workflow/{workflow_id}")
@trace_span("api.workflow.get_status")
async def workflow_get_status(workflow_id: str, request: Request):
    """Get workflow status by ID."""
    engine = getattr(request.app.state, "workflow_engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="WorkflowEngine not available")
    status = engine.get_status(workflow_id)
    if not status:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"ok": True, "workflow": status}


@app.get("/workflows")
@trace_span("api.workflow.list")
async def workflow_list_active(request: Request):
    """List active (non-completed) workflows."""
    engine = getattr(request.app.state, "workflow_engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="WorkflowEngine not available")
    return {"ok": True, "workflows": engine.list_active(limit=50)}


@app.post("/im/feishu/webhook")
@trace_span("api.feishu.webhook")
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
    im_adapter: FeishuMultiBotManager = request.app.state.im_adapter

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

    # ── Agent routing: @Agent → Redis task.{agent} ─────────────────
    dispatcher: AgentTaskDispatcher | None = getattr(request.app.state, "agent_dispatcher", None)
    if dispatcher and message.text:
        dispatched_agent = await dispatcher.dispatch(
            text=message.text,
            chat_id=message.chat_id or "",
            sender=message.sender or "",
            message_id=message.message_id or "",
            bot_id=message.bot_id,
        )
        if dispatched_agent:
            return {
                "ok": True,
                "status": "dispatched",
                "agent": dispatched_agent,
                "reason": f"任务已分配给 {dispatched_agent}，处理中...",
            }

    # Fallback to direct provider routing (legacy mode)
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


@app.post("/internal/notify")
async def internal_notify(request: Request):
    """Receive notifications from OpenClaw gateway."""
    try:
        body = await request.json()
        print(f"[Notify] Received notification: {body}")
    except Exception as e:
        print(f"[Notify] Error parsing notification: {e}")
        body = None
    # Return 200 OK to acknowledge receipt
    return {"ok": True, "received": True}


# Backward compatibility: legacy endpoint aliases
@app.post("/feishu/webhook/opencode")
async def feishu_webhook_legacy_opencode(request: Request):
    """Backward-compatible endpoint for existing Feishu console configs."""
    return await feishu_webhook(request)


@app.post("/feishu/webhook")
async def feishu_webhook_legacy(request: Request):
    """Backward-compatible generic endpoint."""
    return await feishu_webhook(request)


# ============================================
# MyCompany Dashboard API (protected)
# ============================================

@app.get("/api/agents", dependencies=[Depends(verify_api_key)])
def api_agents():
    """Return agent status from supervisord."""
    try:
        import subprocess
        result = subprocess.run(
            ["supervisorctl", "-c", "/home/akliedrak/workspace/MyCompany/.config/supervisor/mycompany.conf", "status"],
            capture_output=True, text=True, timeout=10,
        )
        agents = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(None, 2)
            if len(parts) >= 2:
                agents.append({
                    "name": parts[0],
                    "status": parts[1],
                    "info": parts[2] if len(parts) > 2 else "",
                })
        return {"agents": agents}
    except Exception as e:
        return {"agents": [], "error": str(e)}


@app.get("/api/metrics", dependencies=[Depends(verify_api_key)])
def api_metrics():
    """Return token usage metrics for today."""
    try:
        import sqlite3
        from datetime import datetime
        db = "/home/akliedrak/workspace/MyCompany/.system/metrics.db"
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT agent, COUNT(*) as tasks, SUM(input_tokens) as input, "
            "SUM(output_tokens) as output, SUM(duration_seconds) as duration "
            "FROM metrics WHERE timestamp LIKE ? GROUP BY agent",
            (f"{today}%",),
        ).fetchall()
        conn.close()
        return {"metrics": [dict(r) for r in rows], "date": today}
    except Exception as e:
        return {"metrics": [], "error": str(e)}


@app.get("/api/tasks", dependencies=[Depends(verify_api_key)])
def api_tasks():
    """Return recent tasks from metrics DB."""
    try:
        import sqlite3
        db = "/home/akliedrak/workspace/MyCompany/.system/metrics.db"
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT agent, task_id, model, input_tokens, output_tokens, "
            "duration_seconds, status, timestamp FROM metrics "
            "ORDER BY timestamp DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return {"tasks": [dict(r) for r in rows]}
    except Exception as e:
        return {"tasks": [], "error": str(e)}


@app.get("/api/dead-letters", dependencies=[Depends(verify_api_key)])
def api_dead_letters():
    """Return dead letter queue statistics and pending items."""
    try:
        import sys
        sys.path.insert(0, "/home/akliedrak/workspace/MyCompany/src")
        from mycompany.core.dead_letter import DeadLetterQueue
        dlq = DeadLetterQueue()
        return {"stats": dlq.get_stats(), "pending": dlq.list_pending(limit=20)}
    except Exception as e:
        return {"stats": {}, "pending": [], "error": str(e)}


@app.get("/api/circuit-breakers", dependencies=[Depends(verify_api_key)])
def api_circuit_breakers():
    """Return circuit breaker states."""
    try:
        import sys
        sys.path.insert(0, "/home/akliedrak/workspace/MyCompany/src")
        from mycompany.core.circuit_breaker import all_breaker_stats
        return {"breakers": all_breaker_stats()}
    except Exception as e:
        return {"breakers": {}, "error": str(e)}


@app.get("/api/audit", dependencies=[Depends(verify_api_key)])
def api_audit(event_type: str | None = None, agent: str | None = None, limit: int = 50):
    """Query audit log entries."""
    try:
        import sys
        sys.path.insert(0, "/home/akliedrak/workspace/MyCompany/src")
        from mycompany.core.audit import AuditLogger
        entries = AuditLogger().query(event_type=event_type, agent=agent, limit=limit)
        return {"entries": entries}
    except Exception as e:
        return {"entries": [], "error": str(e)}


@app.get("/metrics")
def prometheus_metrics():
    """Prometheus metrics endpoint for scraping.

    Aggregates metrics from all agent processes via the shared SQLite DB.
    """
    try:
        import sys, os
        mycompany_src = os.environ.get("MYCOMPANY_HOME", os.path.expanduser("~/workspace/MyCompany"))
        sys.path.insert(0, os.path.join(mycompany_src, "src"))
        from mycompany.utils.metrics_export import render_metrics_from_db
        return Response(content=render_metrics_from_db(), media_type="text/plain; version=0.0.4")
    except Exception as e:
        return Response(content=f"# Error generating metrics\n# {e}\n", media_type="text/plain")


@app.get("/dashboard", dependencies=[Depends(verify_api_key)])
def dashboard():
    """Enterprise dashboard with all system metrics."""
    html = '''<!DOCTYPE html>
<html>
<head>
  <title>MyCompany Enterprise Dashboard</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 16px; background: #f5f5f5; -webkit-font-smoothing: antialiased; }
    h1 { color: #1a1a2e; font-size: 1.5rem; margin: 0 0 16px 0; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
    @media (min-width: 768px) {
      .grid { grid-template-columns: 1fr 1fr; }
      h1 { font-size: 2rem; }
    }
    .card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .card h3 { margin-top: 0; color: #333; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; font-size: 1rem; }
    .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; margin: 2px; }
    .badge-running { background: #d4edda; color: #155724; }
    .badge-stopped { background: #f8d7da; color: #721c24; }
    .badge-open { background: #f8d7da; color: #721c24; }
    .badge-closed { background: #d4edda; color: #155724; }
    pre { background: #f8f9fa; padding: 10px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid #e0e0e0; }
    th { color: #666; font-weight: 600; }
    .alert { background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 10px 0; border-radius: 4px; font-size: 13px; }
    .footer { text-align: center; color: #999; font-size: 12px; margin-top: 24px; padding: 16px; }
    .refresh-btn { background: #1a1a2e; color: white; border: none; padding: 8px 16px; border-radius: 20px; font-size: 13px; cursor: pointer; }
    @media (max-width: 480px) {
      .card { padding: 12px; }
      table { font-size: 11px; }
      th, td { padding: 6px 4px; }
    }
  </style>
</head>
<body>
<h1>🏢 MyCompany Enterprise Dashboard <button class="refresh-btn" onclick="load()">🔄 Refresh</button></h1>

<div class="grid">
  <div class="card">
    <h3>🤖 Agent Status</h3>
    <div id="agents">Loading...</div>
  </div>
  <div class="card">
    <h3>⚡ Circuit Breakers</h3>
    <div id="breakers">Loading...</div>
  </div>
  <div class="card">
    <h3>📊 Token Usage (Today)</h3>
    <div id="metrics">Loading...</div>
  </div>
  <div class="card">
    <h3>💀 Dead Letter Queue</h3>
    <div id="dlq">Loading...</div>
  </div>
  <div class="card" style="grid-column: 1 / -1;">
    <h3>📋 Recent Tasks</h3>
    <div id="tasks">Loading...</div>
  </div>
  <div class="card" style="grid-column: 1 / -1;">
    <h3>🔍 Recent Audit Events</h3>
    <div id="audit">Loading...</div>
  </div>
</div>

<script>
async function load() {
  try {
    const agents = await fetch("/api/agents").then(r => r.json());
    const agentHtml = (agents.agents || []).map(a =>
      `<span class="badge badge-${a.status === 'RUNNING' ? 'running' : 'stopped'}">${a.name}</span> `
    ).join('');
    document.getElementById("agents").innerHTML = agentHtml || '<em>No agents</em>';
  } catch(e) { document.getElementById("agents").innerHTML = '<span style="color:red">Error</span>'; }

  try {
    const breakers = await fetch("/api/circuit-breakers").then(r => r.json());
    const b = breakers.breakers || {};
    const breakerHtml = Object.entries(b).map(([k,v]) =>
      `<span class="badge badge-${v.state === 'closed' ? 'closed' : 'open'}">${k}: ${v.state}</span> `
    ).join('') || '<em>All healthy</em>';
    document.getElementById("breakers").innerHTML = breakerHtml;
  } catch(e) { document.getElementById("breakers").innerHTML = '<span style="color:red">Error</span>'; }

  try {
    const metrics = await fetch("/api/metrics").then(r => r.json());
    document.getElementById("metrics").innerHTML = "<pre>" + JSON.stringify(metrics, null, 2) + "</pre>";
  } catch(e) { document.getElementById("metrics").innerHTML = '<span style="color:red">Error</span>'; }

  try {
    const dlq = await fetch("/api/dead-letters").then(r => r.json());
    const stats = dlq.stats || {};
    let html = `<p>Total: ${stats.total||0} | Pending: <b>${stats.pending||0}</b> | Retried: ${stats.retried||0} | Abandoned: ${stats.abandoned||0}</p>`;
    if (stats.pending > 0) html += '<div class="alert">⚠️ ' + stats.pending + ' tasks need attention</div>';
    document.getElementById("dlq").innerHTML = html;
  } catch(e) { document.getElementById("dlq").innerHTML = '<span style="color:red">Error</span>'; }

  try {
    const tasks = await fetch("/api/tasks").then(r => r.json());
    const rows = (tasks.tasks || []).map(t =>
      `<tr><td>${t.agent}</td><td>${t.task_id}</td><td>${t.model||'-'}</td><td>${t.status}</td><td>${t.timestamp}</td></tr>`
    ).join('');
    document.getElementById("tasks").innerHTML = rows ?
      `<table><tr><th>Agent</th><th>Task ID</th><th>Model</th><th>Status</th><th>Time</th></tr>${rows}</table>` :
      '<em>No tasks recorded</em>';
  } catch(e) { document.getElementById("tasks").innerHTML = '<span style="color:red">Error</span>'; }

  try {
    const audit = await fetch("/api/audit?limit=20").then(r => r.json());
    const rows = (audit.entries || []).map(e =>
      `<tr><td>${e.ts}</td><td>${e.evt}</td><td>${e.agent||e.user||'-'}</td><td>${JSON.stringify(e).slice(0,120)}...</td></tr>`
    ).join('');
    document.getElementById("audit").innerHTML = rows ?
      `<table><tr><th>Time</th><th>Event</th><th>Actor</th><th>Details</th></tr>${rows}</table>` :
      '<em>No audit events</em>';
  } catch(e) { document.getElementById("audit").innerHTML = '<span style="color:red">Error</span>'; }
}
load();
setInterval(load, 5000);
</script>
</body>
</html>'''
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
