"""Feishu webhook endpoints — legacy compat."""

import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request

from vibebridge.legacy.feishu_card_handler import process_feishu_webhook
from vibebridge.limiter import limiter

router = APIRouter()


@router.post("/feishu/webhook")
@limiter.limit("60 per minute")
async def feishu_webhook(request: Request, background_tasks: BackgroundTasks):
    """Unified Feishu webhook — delegates to card handler."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": True, "status": "error", "reason": "Invalid JSON"}

    if "challenge" in body:
        return {"challenge": body["challenge"]}

    return await process_feishu_webhook(body, background_tasks)


@router.post("/feishu/webhook/opencode")
@limiter.limit("60 per minute")
async def feishu_webhook_opencode(request: Request, background_tasks: BackgroundTasks):
    """Legacy OpenCode webhook alias."""
    return await feishu_webhook(request, background_tasks)
