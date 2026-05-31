"""Admin panel routes for VibeBridge."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(prefix="/admin")


def _render_page(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — VibeBridge</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#f0f2f5;color:#1a1a2e;padding:20px}}
h1{{font-size:1.5rem;margin-bottom:16px}}
.card{{background:#fff;border-radius:12px;padding:16px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.badge{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;margin:2px}}
.badge-ok{{background:#d4edda;color:#155724}}
.badge-err{{background:#f8d7da;color:#721c24}}
</style></head>
<body>
<h1>🔌 VibeBridge Admin</h1>
{body_html}
</body></html>"""


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Main admin dashboard."""
    stats = _collect_stats(request)
    html = _render_page("Dashboard", f"""
<div class="card"><h3>📊 Overview</h3>
<p>Version: <b>{stats['vibebridge_version']}</b></p>
<p>Feishu Bots: <b>{stats['feishu_bots']}</b></p>
<p>Redis: <span class="badge badge-{'ok' if stats['redis_connected'] else 'err'}">{'Connected' if stats['redis_connected'] else 'Disconnected'}</span></p>
</div>
<div class="card"><h3>🤖 Providers</h3>
{''.join(f'<span class="badge badge-{"ok" if p["healthy"] else "err"}">{p["name"]}</span> ' for p in stats.get('providers', [])) or '<em>No providers</em>'}
</div>
""")
    return HTMLResponse(content=html)


@router.get("/api/status")
async def admin_api_status(request: Request):
    """JSON API for dashboard live updates."""
    return JSONResponse(_collect_stats(request))


def _collect_stats(request: Request) -> dict[str, Any]:
    """Gather system statistics for the dashboard."""
    stats: dict[str, Any] = {
        "vibebridge_version": "1.2.0",
        "feishu_bots": 0,
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
        app_router = getattr(request.app.state, "router", None)
        if app_router and hasattr(app_router, "health_table"):
            import asyncio
            health = asyncio.run(app_router.health_table())
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

    return stats
