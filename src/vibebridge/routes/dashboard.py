"""Dashboard API endpoints — legacy compat layer.

The primary dashboard is now served from vibebridge.server.
This module is retained for backward compatibility with vibebridge.main.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/api/agents")
def api_agents():
    """Return agent status via supervisorctl if SUPERVISOR_CONF is set."""
    import os, subprocess
    supervisor_conf = os.environ.get("SUPERVISOR_CONF", "")
    if not supervisor_conf:
        return {"agents": [], "error": "SUPERVISOR_CONF not configured"}
    try:
        result = subprocess.run(
            ["supervisorctl", "-c", supervisor_conf, "status"],
            capture_output=True, text=True, timeout=10,
        )
        agents = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                agents.append({"name": parts[0], "status": parts[1], "info": parts[2] if len(parts) > 2 else ""})
        return {"agents": agents, "total": len(agents)}
    except Exception as e:
        return {"agents": [], "error": str(e)}


@router.get("/api/metrics")
def api_metrics():
    return {"metrics": [], "info": "Metrics available via vibebridge.server dashboard"}


@router.post("/api/chat")
def api_chat(body: dict):
    """Chat endpoint override — use vibebridge.server for full functionality."""
    raise HTTPException(status_code=503, detail="Chat API: use vibebridge.server entry point")


@router.get("/api/config")
def api_config():
    return {"info": "Config API: use vibebridge.server entry point"}


@router.get("/api/sessions")
def api_sessions():
    return {"sessions": [], "info": "Sessions API: use vibebridge.server entry point"}


@router.get("/compact")
def compact_dashboard():
    """Redirect to unified WebUI."""
    return RedirectResponse(url="/")


# Catch-all for other legacy API routes
router.get("/api/{path:path}")
def api_fallback(path: str):
    raise HTTPException(status_code=503, detail=f"API /api/{path}: use vibebridge.server entry point")
