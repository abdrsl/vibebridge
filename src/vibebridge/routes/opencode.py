"""OpenCode task endpoints."""
import json
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from vibebridge.legacy.feishu_client import (
    build_error_card,
    build_progress_card,
    build_result_card,
    build_start_card,
    feishu_client,
)
from vibebridge.legacy.opencode_integration import TaskStatus, opencode_manager
from vibebridge.limiter import limiter
from vibebridge.system import get_system

router = APIRouter()


class OpenCodeTaskCreate(BaseModel):
    message: str
    feishu_chat_id: str | None = None
    feishu_message_id: str | None = None
    notify_on_complete: bool = True


@router.post("/opencode/tasks")
@limiter.limit("10 per minute")
async def create_opencode_task(
    request: Request, payload: OpenCodeTaskCreate, background_tasks: BackgroundTasks
):
    """Create an OpenCode task."""
    # Use multi-agent system if available
    system = get_system()
    if system and system.is_running():
        opencode_agent = system.get_agent("opencode")
        if opencode_agent and opencode_agent.is_running():
            # TODO: Use agent-based task creation
            pass

    # Fallback to legacy implementation
    task_id = await opencode_manager.create_task(
        user_message=payload.message,
        feishu_chat_id=payload.feishu_chat_id or __import__("os").getenv("FEISHU_DEFAULT_CHAT_ID"),
        feishu_message_id=payload.feishu_message_id,
    )

    background_tasks.add_task(run_opencode_with_feishu, task_id, payload.notify_on_complete)

    return {
        "ok": True,
        "task_id": task_id,
        "status": "pending",
        "message": "Task created, processing in background",
    }


async def run_opencode_with_feishu(task_id: str, notify: bool = True):
    """Run OpenCode task with Feishu notifications."""
    print(f"[OpenCode] Starting task {task_id}, notify={notify}")
    task = await opencode_manager.get_task(task_id)
    if not task:
        print(f"[OpenCode] Task {task_id} not found")
        return

    print(f"[OpenCode] Task found, feishu_chat_id={task.feishu_chat_id}")

    try:
        if notify and task.feishu_chat_id:
            print(f"[OpenCode] Sending start card to {task.feishu_chat_id}")
            start_card = build_start_card(task_id, task.user_message)
            result = await feishu_client.send_interactive_card(task.feishu_chat_id, start_card)
            print(f"[OpenCode] Start card result: {result}")

        # Collect events
        final_result = None
        error_result = None
        tool_count = 0
        latest_output = ""
        last_progress_time = 0
        PROGRESS_INTERVAL = 5  # seconds

        async for event in opencode_manager.run_opencode(task_id):
            event_type = event.get("type", "")
            content = event.get("content", "")
            print(f"[OpenCode] Event: {event_type} - {content[:50]}...")

            if event_type == "tool_use":
                tool_count += 1
                latest_output = content[:200] if content else "正在执行操作..."
            elif event_type == "text":
                latest_output = content[:200] if content else "正在生成文本..."
            elif event_type == "status":
                latest_output = content[:200] if content else "正在启动..."
            elif event_type == "done":
                final_result = content
            elif event_type == "error":
                error_result = content

            # Send progress updates if enough time has passed
            current_time = time.time()
            if (
                notify
                and task.feishu_chat_id
                and event_type in ("tool_use", "text", "status")
                and current_time - last_progress_time > PROGRESS_INTERVAL
            ):
                # Fallback if latest_output empty
                display_output = latest_output if latest_output else "OpenCode 正在处理..."
                progress_card = build_progress_card(task_id, "running", display_output, tool_count)
                result = await feishu_client.send_interactive_card(
                    task.feishu_chat_id, progress_card
                )
                print(f"[OpenCode] Progress card sent: {result}")
                last_progress_time = current_time

        # Send result after completion
        if notify and task.feishu_chat_id:
            print(
                f"[OpenCode] Sending result to Feishu, final_result={final_result is not None}, error_result={error_result is not None}"
            )
            if final_result:
                print(f"[OpenCode] Building result card with content length: {len(final_result)}")
                final_card = build_result_card(
                    task_id, task.user_message, task.output_lines, final_result
                )
                result = await feishu_client.send_interactive_card(task.feishu_chat_id, final_card)
                print(f"[OpenCode] Result card sent: {result}")
            elif error_result:
                print(f"[OpenCode] Building error card with error: {error_result}")
                card = build_error_card(task_id, error_result)
                result = await feishu_client.send_interactive_card(task.feishu_chat_id, card)
                print(f"[OpenCode] Error card sent: {result}")
            else:
                print("[OpenCode] No result or error to send")

    except Exception as e:
        print(f"[OpenCode] Error: {e}")
        import traceback

        traceback.print_exc()


@router.get("/opencode/tasks")
@limiter.limit("60 per minute")
async def list_opencode_tasks(request: Request, limit: int = Query(default=20, le=100)):
    """List OpenCode tasks."""
    tasks = await opencode_manager.list_tasks(limit=limit)
    return {"ok": True, "items": tasks}


@router.get("/opencode/tasks/{task_id}")
@limiter.limit("60 per minute")
async def get_opencode_task(request: Request, task_id: str):
    """Get OpenCode task details."""
    task = await opencode_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "ok": True,
        "item": {
            "task_id": task.task_id,
            "status": task.status.value,
            "user_message": task.user_message,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "output_count": len(task.output_lines),
            "output_preview": "\n".join(task.output_lines[-10:]) if task.output_lines else None,
            "final_result": task.final_result,
            "error": task.error,
            "feishu_chat_id": task.feishu_chat_id,
        },
    }


@router.get("/opencode/tasks/{task_id}/stream")
@limiter.limit("30 per minute")
async def stream_opencode_task(request: Request, task_id: str):
    """Stream OpenCode task events."""
    task = await opencode_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        async for event in opencode_manager.run_opencode(task_id):
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] == "done":
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/opencode/tasks/{task_id}/abort")
@limiter.limit("10 per minute")
async def abort_opencode_task(request: Request, task_id: str):
    """Abort an OpenCode task."""
    task = await opencode_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.process and task.process.poll() is None:
        task.process.terminate()
        await opencode_manager.update_task(
            task_id, status=TaskStatus.FAILED, error="Task aborted by user"
        )
        return {"ok": True, "message": "Task aborted"}

    return {"ok": True, "message": "Task was not running"}
