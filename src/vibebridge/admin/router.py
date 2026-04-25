"""Admin panel routes for VibeBridge."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import router, templates


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Main admin dashboard."""
    # Collect system stats
    stats = _collect_stats(request)
    return templates.TemplateResponse("dashboard.html", {"request": request, "stats": stats})


@router.get("/bots", response_class=HTMLResponse)
async def admin_bots(request: Request):
    """Feishu bot management page."""
    bots = []
    try:
        from mycompany.config.bots import BotRegistry
        registry = BotRegistry()
        for b in registry.list_all():
            bots.append({
                "agent": b.agent,
                "bot_name": b.bot_name,
                "enabled": b.enabled,
                "app_id": b.app_id,
                "keywords": b.keywords,
            })
    except Exception as exc:
        bots = [{"agent": "error", "bot_name": str(exc), "enabled": False}]

    return templates.TemplateResponse("bots.html", {"request": request, "bots": bots})


@router.post("/bots/{agent}/toggle")
async def admin_bot_toggle(request: Request, agent: str):
    """Toggle bot enabled/disabled."""
    try:
        from mycompany.config.bots import BotRegistry
        registry = BotRegistry()
        cfg = registry.get(agent)
        if cfg:
            cfg.enabled = not cfg.enabled
            registry.save(cfg)
            return {"ok": True, "agent": agent, "enabled": cfg.enabled}
        return {"ok": False, "error": "Bot not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/agents", response_class=HTMLResponse)
async def admin_agents(request: Request):
    """Agent control panel."""
    agents = []
    try:
        import redis as redis_lib
        from mycompany.core.config_manager import get_config as _get_cfg
        rcfg = _get_cfg().redis
        r = redis_lib.Redis(
            host=rcfg.host, port=rcfg.port,
            password=rcfg.password, decode_responses=True,
        )
        for name in [
            "pm-agent", "software-agent", "hardware-agent", "test-agent",
            "reviewer-agent", "it-ops-agent", "ceo-agent", "structure-agent",
            "admin-agent", "hr-agent",
        ]:
            status_raw = r.get(f"status:{name}")
            status = json.loads(status_raw) if status_raw else {}
            agents.append({
                "name": name,
                "running": status.get("running", False),
                "current_task": status.get("current_task", "-"),
                "queue_size": status.get("queue_size", 0),
                "metrics": status.get("metrics", {}),
            })
    except Exception as exc:
        agents = [{"name": "error", "running": False, "error": str(exc)}]

    return templates.TemplateResponse("agents.html", {"request": request, "agents": agents})


@router.get("/keys", response_class=HTMLResponse)
async def admin_keys(request: Request):
    """API Key management page."""
    keys = []
    try:
        from mycompany.config.secrets import SecretsManager
        sm = SecretsManager()
        for key in sm.list():
            val = sm.get(key)
            masked = val[:6] + "..." + val[-4:] if val and len(val) > 12 else "****"
            keys.append({"name": key, "masked": masked})
    except Exception as exc:
        keys = [{"name": "error", "masked": str(exc)}]

    return templates.TemplateResponse("keys.html", {"request": request, "keys": keys})


@router.get("/tasks", response_class=HTMLResponse)
async def admin_tasks(request: Request):
    """Task queue overview."""
    tasks = []
    try:
        import redis as redis_lib
        from mycompany.core.config_manager import get_config as _get_cfg
        rcfg = _get_cfg().redis
        r = redis_lib.Redis(
            host=rcfg.host, port=rcfg.port,
            password=rcfg.password, decode_responses=True,
        )
        # Scan for recent task keys
        for key in r.scan_iter(match="task:*", count=100):
            key_str = key.decode() if isinstance(key, bytes) else key
            tasks.append({"channel": key_str, "type": "pubsub"})
    except Exception as exc:
        tasks = [{"channel": "error", "type": str(exc)}]

    return templates.TemplateResponse("tasks.html", {"request": request, "tasks": tasks})


@router.get("/api/status")
async def admin_api_status(request: Request):
    """JSON API for dashboard live updates."""
    return JSONResponse(_collect_stats(request))


def _collect_stats(request: Request) -> dict[str, Any]:
    """Gather system statistics for the dashboard."""
    stats: dict[str, Any] = {
        "vibebridge_version": "2.1.0",
        "feishu_bots": 0,
        "agents_online": 0,
        "redis_connected": False,
        "providers": [],
    }

    # Feishu bots
    try:
        feishu_bots = getattr(request.app.state, "feishu_bots", [])
        stats["feishu_bots"] = len(feishu_bots)
    except Exception:
        pass

    # Providers
    try:
        router = getattr(request.app.state, "router", None)
        if router and hasattr(router, "health_table"):
            import asyncio
            health = asyncio.run(router.health_table())
            stats["providers"] = [{"name": k, "healthy": v[0]} for k, v in health.items()]
    except Exception:
        pass

    # Redis
    try:
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client:
            stats["redis_connected"] = redis_client.ping()
    except Exception:
        pass

    # Agent count from supervisor
    try:
        import subprocess
        result = subprocess.run(
            ["pgrep", "-f", "python.*mycompany.*agents"],
            capture_output=True, text=True, timeout=5,
        )
        stats["agents_online"] = len([l for l in result.stdout.strip().split("\n") if l.strip()])
    except Exception:
        pass

    return stats
