"""Internal notification endpoints."""
from typing import Any

from fastapi import APIRouter, Request

from vibebridge.limiter import limiter

router = APIRouter()


@router.post("/internal/notify")
@limiter.limit("60 per minute")
async def internal_notify(request: Request, body: dict[str, Any] = None):
    """Receive notifications from internal services."""
    # Log the notification for debugging
    print(f"[Notify] Received notification: {body}")
    # Return 200 OK to acknowledge receipt
    return {"ok": True, "received": True}
