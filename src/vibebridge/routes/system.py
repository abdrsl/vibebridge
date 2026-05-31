"""System and health endpoints."""

from fastapi import APIRouter, Request

from vibebridge.limiter import limiter
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
    """Health check — provider and system status."""
    import time
    system = get_system()
    status = {
        "ok": True,
        "timestamp": time.time(),
        "multi_agent_system": system.is_running() if system else False,
        "checks": {},
    }
    return status
