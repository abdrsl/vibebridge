"""Legacy task and config endpoints."""
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from vibebridge.legacy.secure_config import get_secret
from vibebridge.legacy.task_store import get_task, list_tasks, update_task
from vibebridge.limiter import limiter

router = APIRouter()


class TaskUpdate(BaseModel):
    status: str | None = None
    owner: str | None = None
    notes: str | None = None


@router.get("/config-check")
@limiter.limit("30 per minute")
def config_check(request: Request):
    """Configuration check endpoint."""
    return {
        "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL"),
        "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL"),
        "DEEPSEEK_API_KEY_present": bool(get_secret("DEEPSEEK_API_KEY")),
    }


@router.get("/tasks")
@limiter.limit("60 per minute")
def api_list_tasks(request: Request, limit: int = 20):
    """List tasks."""
    return {
        "ok": True,
        "items": list_tasks(limit=limit),
    }


@router.get("/tasks/{task_id}")
@limiter.limit("60 per minute")
def api_get_task(request: Request, task_id: str):
    """Get task details."""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    return {
        "ok": True,
        "item": task,
    }


@router.patch("/tasks/{task_id}")
@limiter.limit("30 per minute")
def patch_task(request: Request, task_id: str, payload: TaskUpdate):
    """Update a task."""
    updates = payload.model_dump(exclude_none=True)

    updated = update_task(task_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "ok": True,
        "task": updated,
    }
