"""
MyCompany Internal VibeBridge — minimal Feishu webhook + health endpoint.
Delegates to MyCompany's internal vibebridge code for business logic.
No WebSocket, no complex lifespan — just HTTP webhook handling.
"""
import json
import os
import sys
import time

# Use MyCompany's internal code
_mycompany_src = os.path.join(
    os.environ.get("MYCOMPANY_HOME", os.path.expanduser("~/workspace/MyCompany")),
    "src",
)
if _mycompany_src not in sys.path:
    sys.path.insert(0, _mycompany_src)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lazy-load MyCompany internals
    try:
        from vibebridge.config import get_config
        from vibebridge.providers import build_providers
        from vibebridge.router import ProviderRouter
        from vibebridge.session import get_session_manager
        from vibebridge.tasks import ApprovalEngine, TaskOrchestrator
        from vibebridge.im.feishu import FeishuMultiBotManager, FeishuBotCredentials

        cfg = get_config()
        providers = build_providers(cfg.agents)
        router = ProviderRouter(cfg.agents, providers)
        sessions = get_session_manager()
        approval = ApprovalEngine(cfg.approval) if cfg.approval.enabled else None

        # Load Feishu bots from MyCompany BotRegistry
        feishu_bots = []
        try:
            from mycompany.config.bots import BotRegistry
            from mycompany.config.secrets import SecretsManager
            registry = BotRegistry()
            sm = SecretsManager()
            for bot_cfg in registry.list_all():
                if bot_cfg.enabled and bot_cfg.app_id:
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
        except Exception:
            pass

        # Fallback to config
        if not feishu_bots and cfg.feishu.app_id:
            feishu_bots.append(FeishuBotCredentials(
                agent="default",
                app_id=cfg.feishu.app_id,
                app_secret=cfg.feishu.app_secret,
                encrypt_key=cfg.feishu.encrypt_key,
                verification_token=cfg.feishu.verification_token,
            ))

        im_adapter = FeishuMultiBotManager(feishu_bots)
        orchestrator = TaskOrchestrator(router, im_adapter, sessions, approval)

        # Redis + AgentBridge
        redis_client = None
        try:
            import redis as _r
            from mycompany.core.config_manager import get_config as _get_mc
            rcfg = _get_mc().redis
            redis_client = _r.Redis(
                host=rcfg.host, port=rcfg.port,
                password=rcfg.password, decode_responses=True,
            )
            from vibebridge.agent_bridge import AgentResultBridge
            bridge = AgentResultBridge(redis_client, im_adapter)
            bridge.start()
        except Exception:
            pass

        app.state.orchestrator = orchestrator
        app.state.im_adapter = im_adapter
        app.state.redis = redis_client
        app.state.feishu_bots = feishu_bots
        print("[MyCompany-VB] Ready", flush=True)
    except Exception as e:
        print(f"[MyCompany-VB] Warning: {e}", flush=True)

    yield
    print("[MyCompany-VB] Shutdown", flush=True)


app = FastAPI(title="MyCompany-VibeBridge", version="1.0", lifespan=lifespan)


@app.get("/health")
async def health(request: Request):
    redis_ok = False
    try:
        rd = getattr(request.app.state, "redis", None)
        if rd:
            redis_ok = rd.ping()
    except Exception:
        pass
    return {
        "ok": True,
        "timestamp": time.time(),
        "multi_agent_system": True,
        "checks": {
            "redis": "ok" if redis_ok else "fail",
            "disk_gb": round(
                os.statvfs("/").f_bavail * os.statvfs("/").f_frsize / (1024**3), 1
            ),
        },
    }


@app.post("/feishu/webhook/opencode")
async def feishu_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": True, "error": "invalid json"}, status_code=400)

    # URL verification
    if "challenge" in body:
        return {"challenge": body["challenge"]}

    # Forward to orchestrator
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator:
        try:
            result = await orchestrator.handle_feishu_event(body)
            return result or {"ok": True}
        except Exception:
            pass

    return {"ok": True}


@app.post("/feishu/webhook")
async def feishu_webhook_legacy(request: Request):
    return await feishu_webhook(request)


@app.post("/im/feishu/webhook")
async def feishu_webhook_v2(request: Request):
    return await feishu_webhook(request)


@app.get("/system/status")
async def system_status(request: Request):
    return {"ok": True, "agents": "check CLI"}
