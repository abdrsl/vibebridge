"""System and health endpoints."""
import os
import time

from fastapi import APIRouter, Request

from vibebridge._compat import get_mycompany_home, get_supervisor_conf
from vibebridge.limiter import limiter
from vibebridge.redis_pool import get_redis
from vibebridge.system import get_system

router = APIRouter()


@router.get("/")
def root_page():
    """Unified Web UI — single page with all controls."""
    from vibebridge.template_loader import serve_webui
    return serve_webui()


@router.get("/health")
@limiter.exempt
def health():
    """Enhanced health check — full system status."""
    import subprocess as sp
    system = get_system()
    status = {
        "ok": True,
        "timestamp": time.time(),
        "multi_agent_system": system.is_running() if system else False,
        "checks": {},
    }
    # Check Redis
    try:
        rd = get_redis()
        status["checks"]["redis"] = "ok" if rd.ping() else "fail"
    except Exception as e:
        status["checks"]["redis"] = f"fail({str(e)[:30]})"
    # Check agents
    try:
        ra = sp.run(
            ["supervisorctl", "-c", get_supervisor_conf(), "status"],
            capture_output=True, text=True, timeout=5,
        )
        running = ra.stdout.count("RUNNING")
        total = max(ra.stdout.count("\n"), 1)
        status["checks"]["agents"] = f"{running}/{total}"
        if running < 8:
            status["ok"] = False
    except Exception:
        status["checks"]["agents"] = "unknown"
    # Check disk
    stat = os.statvfs(get_mycompany_home())
    free_gb = stat.f_bavail * stat.f_frsize / (1024**3)
    status["checks"]["disk_gb"] = round(free_gb, 1)
    if free_gb < 1:
        status["ok"] = False
    # Check memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        status["checks"]["memory_percent"] = mem.percent
        status["checks"]["memory_gb"] = round(mem.available / (1024**3), 1)
    except Exception as exc:
        from logging import getLogger
        getLogger(__name__).debug("Memory check failed: %s", exc)
    return status


@router.get("/system/status")
@limiter.limit("30 per minute")
def system_status(request: Request):
    """Get multi-agent system status."""
    system = get_system()
    if not system:
        return {"ok": False, "error": "System not initialized"}

    agents = []
    for agent_id, agent in system.agents.items():
        agents.append(
            {
                "id": agent_id,
                "name": agent.name,
                "running": agent.is_running(),
                "capabilities": [cap.name for cap in agent.get_capabilities()],
            }
        )

    return {
        "ok": True,
        "running": system.is_running(),
        "agents": agents,
        "agent_count": len(system.agents),
    }
