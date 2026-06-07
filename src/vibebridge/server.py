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
from .ws_client import FeishuWebSocketClient


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

    # Load bots from config (YAML or env)
    for bot_cfg in cfg.feishu.bots:
        if bot_cfg.enabled and bot_cfg.app_id:
            secret = bot_cfg.app_secret
            if secret:
                feishu_bots.append(FeishuBotCredentials(
                    agent=bot_cfg.agent,
                    app_id=bot_cfg.app_id,
                    app_secret=secret,
                    encrypt_key=bot_cfg.encrypt_key or "",
                    verification_token=bot_cfg.verification_token or "",
                ))
    print(f"[VibeBridge] Loaded {len(feishu_bots)} Feishu bots from config")

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
    auto_review = None
    if cfg.redis.enabled:
        try:
            import redis as _redis_lib
            redis_client = _redis_lib.Redis(
                host=cfg.redis.host, port=cfg.redis.port,
                password=cfg.redis.password or None,
                decode_responses=True,
            )
            agent_bridge = AgentResultBridge(redis_client, im_adapter)
            agent_bridge.start()
            agent_dispatcher = AgentTaskDispatcher(redis_client)
            auto_review = AutoReviewRouter(redis_client)
            auto_review.start()
            print("[VibeBridge] AgentBridge + AutoReview connected to Redis")
        except Exception as e:
            print(f"[VibeBridge] AgentBridge not available: {e}")
    else:
        print("[VibeBridge] Redis disabled — AgentBridge not started")

    app.state.cfg = cfg
    app.state.providers = providers
    app.state.router = router
    app.state.im_adapter = im_adapter
    app.state.orchestrator = orchestrator
    app.state.redis = redis_client
    app.state.agent_bridge = agent_bridge
    app.state.agent_dispatcher = agent_dispatcher
    app.state.auto_review = auto_review
    app.state.feishu_bots = feishu_bots

    # ── Feishu WebSocket Long Connection ──────────────────────────
    ws_clients = []
    ws_mode = cfg.feishu.mode or "webhook"
    if ws_mode == "websocket":
        for bot_creds in feishu_bots:
            try:
                import os as _os
                _port = _os.environ.get("VIBEBRIDGE_PORT", "8000")
                ws = FeishuWebSocketClient(
                    app_id=bot_creds.app_id,
                    app_secret=bot_creds.app_secret,
                    webhook_url=f"http://127.0.0.1:{_port}/feishu/webhook",
                )
                await ws.start()
                ws_clients.append(ws)
                print(f"[VibeBridge] WebSocket started for {bot_creds.agent}")
            except Exception as e:
                print(f"[VibeBridge] WebSocket failed for {bot_creds.agent}: {e}")
        if ws_clients:
            print(f"[VibeBridge] {len(ws_clients)} WebSocket client(s) connected")
    else:
        print("[VibeBridge] Webhook mode — no WebSocket clients started")

    yield

    print("[VibeBridge] Shutting down...")
    for ws in ws_clients:
        try:
            await ws.stop()
        except Exception:
            pass
    if agent_bridge:
        agent_bridge.stop()
    if auto_review:
        auto_review.stop()


# --------------------------------------------------------------------------- #
#  API Key auth for dashboard endpoints
# --------------------------------------------------------------------------- #

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _load_dashboard_api_key() -> str | None:
    """Load dashboard API key from environment or config."""
    import os
    return os.getenv("VIBEBRIDGE_API_KEY") or os.getenv("DASHBOARD_API_KEY")


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
    version="1.2.0",
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
        "version": "1.2.0",
        "status": "ok",
    }


@app.get("/live")
async def liveness():
    """Kubernetes liveness probe — always returns 200 if process is running."""
    return {"status": "alive", "timestamp": __import__("time").time()}


@app.get("/ready")
async def readiness(request: Request):
    """Kubernetes readiness probe — checks Redis connectivity if enabled."""
    cfg: "Config" = request.app.state.cfg  # noqa: F821
    if not cfg.redis.enabled:
        return {"status": "ready", "redis": "disabled"}
    try:
        import redis as _redis_lib
        r = _redis_lib.Redis(
            host=cfg.redis.host, port=cfg.redis.port,
            password=cfg.redis.password or None,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        r.ping()
        return {"status": "ready", "redis": True}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Not ready: {exc}")


@app.get("/health")
async def health(request: Request):
    """Health check — non-blocking provider status."""
    providers = getattr(request.app.state, "providers", {})
    result = {
        "ok": True,
        "timestamp": __import__("time").time(),
        "providers": {
            name: {"healthy": True, "message": "registered"}
            for name in providers.keys()
        },
    }
    return result


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


# ── Workflow Endpoints (optional, requires plugin) ──────────────────

@app.post("/workflow/start")
async def workflow_start(request: Request):
    """Start a new multi-agent workflow (requires workflow plugin)."""
    raise HTTPException(status_code=503, detail="WorkflowEngine not available — install plugin")


@app.get("/workflow/{workflow_id}")
async def workflow_get_status(workflow_id: str, request: Request):
    """Get workflow status by ID (requires workflow plugin)."""
    raise HTTPException(status_code=503, detail="WorkflowEngine not available — install plugin")


@app.get("/workflows")
async def workflow_list_active(request: Request):
    """List active workflows (requires workflow plugin)."""
    raise HTTPException(status_code=503, detail="WorkflowEngine not available — install plugin")


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
            sender=message.sender_id or "",
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
    
    action = event.get("action", {})
    action_value = action.get("value", "{}")
    operator = event.get("operator", {})
    context = event.get("context", {})
    
    action_data = None
    value_str = action_value if isinstance(action_value, str) else str(action_value)
    
    try:
        action_data = json.loads(value_str)
    except json.JSONDecodeError:
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
    
    action_type = action_data.get("action")
    if action_type in ("approve", "reject"):
        return await handle_approval_card_action(action_data, operator, context, orchestrator)
    
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
    
    operator_id = operator.get("open_id", "") or operator.get("user_id", "unknown")
    
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
    
    success, request = await orchestrator.approval_manager.process_approval_action(
        request_id, approval_action, operator_id
    )
    
    if success:
        print(f"[Card] Approval action processed successfully: {action_type} {approval_type}")
        
        if approval_action != ApprovalAction.DENY:
            await orchestrator._process_approved_task(request_id)
        
        return {"ok": True, "action": "processed", "response": {}}
    else:
        print(f"[Card] Failed to process approval action: {request_id}")
        return {"ok": True, "action": "processed", "response": {}}


@app.post("/internal/notify")
async def internal_notify(request: Request):
    """Receive notifications from internal services."""
    try:
        body = await request.json()
        print(f"[Notify] Received notification: {body}")
    except Exception as e:
        print(f"[Notify] Error parsing notification: {e}")
        body = None
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
# Dashboard API (generic, no external dependency)
# ============================================

@app.get("/api/agents", dependencies=[Depends(verify_api_key)])
def api_agents(request: Request):
    """Return agent status (generic — reports connected Feishu bots)."""
    feishu_bots = getattr(request.app.state, "feishu_bots", [])
    agents = [{"name": b.agent, "app_id_prefix": b.app_id[:8] + "..." if b.app_id else "N/A"} for b in feishu_bots]
    return {"agents": agents, "total": len(agents)}


@app.get("/api/metrics", dependencies=[Depends(verify_api_key)])
def api_metrics(request: Request):
    """Return system metrics (health status of providers)."""
    providers = getattr(request.app.state, "providers", {})
    import asyncio
    async def _get_health():
        results = {}
        for name, p in providers.items():
            try:
                ok, msg = await p.health_check()
                results[name] = {"healthy": ok, "message": msg}
            except Exception as e:
                results[name] = {"healthy": False, "message": str(e)}
        return results
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    health = loop.run_until_complete(_get_health())
    return {"providers": health, "timestamp": __import__("time").time()}


@app.get("/metrics")
def prometheus_metrics(request: Request):
    """Prometheus metrics endpoint (basic health)."""
    import time as _time
    lines = [
        "# HELP vibebridge_up VibeBridge is running",
        "# TYPE vibebridge_up gauge",
        "vibebridge_up 1",
        f"# HELP vibebridge_info VibeBridge info",
        "# TYPE vibebridge_info gauge",
        f'vibebridge_info{{version="1.2.0"}} 1',
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/dashboard", dependencies=[Depends(verify_api_key)])
def dashboard():
    """VibeBridge Dashboard — lightweight system overview."""
    html = '''<!DOCTYPE html>
<html>
<head>
  <title>VibeBridge Dashboard</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 16px; background: #f5f5f5; -webkit-font-smoothing: antialiased; }
    h1 { color: #1a1a2e; font-size: 1.5rem; margin: 0 0 16px 0; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
    @media (min-width: 768px) { .grid { grid-template-columns: 1fr 1fr; } h1 { font-size: 2rem; } }
    .card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .card h3 { margin-top: 0; color: #333; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; font-size: 1rem; }
    .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; margin: 2px; }
    .badge-healthy { background: #d4edda; color: #155724; }
    .badge-unhealthy { background: #f8d7da; color: #721c24; }
    pre { background: #f8f9fa; padding: 10px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
    .refresh-btn { background: #1a1a2e; color: white; border: none; padding: 8px 16px; border-radius: 20px; font-size: 13px; cursor: pointer; }
  </style>
</head>
<body>
<h1>🔌 VibeBridge Dashboard <button class="refresh-btn" onclick="load()">🔄 Refresh</button></h1>

<div class="grid">
  <div class="card">
    <h3>🤖 Feishu Bots</h3>
    <div id="agents">Loading...</div>
  </div>
  <div class="card">
    <h3>📊 Provider Health</h3>
    <div id="metrics">Loading...</div>
  </div>
</div>

<script>
async function load() {
  try {
    const agents = await fetch("/api/agents").then(r => r.json());
    const agentHtml = (agents.agents || []).map(a =>
      `<span class="badge badge-healthy">${a.name}</span> `
    ).join('') || '<em>No bots configured</em>';
    document.getElementById("agents").innerHTML = agentHtml;
  } catch(e) { document.getElementById("agents").innerHTML = '<span style="color:red">Error</span>'; }

  try {
    const metrics = await fetch("/api/metrics").then(r => r.json());
    const providers = metrics.providers || {};
    const html = Object.entries(providers).map(([k,v]) =>
      `<span class="badge badge-${v.healthy ? 'healthy' : 'unhealthy'}">${k}: ${v.healthy ? 'OK' : v.message}</span><br>`
    ).join('') || '<em>No providers</em>';
    document.getElementById("metrics").innerHTML = html;
  } catch(e) { document.getElementById("metrics").innerHTML = '<span style="color:red">Error</span>'; }
}
load();
setInterval(load, 10000);
</script>
</body>
</html>'''
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
