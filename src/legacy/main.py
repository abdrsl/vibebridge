import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from .llm import ask_deepseek_for_design_advice
from .task_parser import extract_text_from_feishu_payload
from .task_store import save_task, list_tasks, get_task, update_task
from .opencode_integration import opencode_manager, TaskStatus
from .feishu_client import (
    feishu_client,
    build_start_card,
    build_progress_card,
    build_result_card,
    build_error_card,
    build_help_card,
)
from .feishu_crypto import (
    decrypt_feishu_payload,
    FeishuSecurityError,
    verify_feishu_webhook,
)
from .secure_config import get_secret
from .feishu_webhook_handler import handle_feishu_webhook
from .feishu_card_handler import process_feishu_webhook
from src.system import start_multi_agent_system, stop_multi_agent_system

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("App starting...")
    print("[System] Starting multi-agent system...")
    try:
        await start_multi_agent_system()
    except Exception as e:
        print(f"[System] Error starting multi-agent system: {e}")
        # Continue without multi-agent system
    yield
    print("App shutting down...")
    try:
        await stop_multi_agent_system()
    except Exception as e:
        print(f"[System] Error stopping multi-agent system: {e}")


app = FastAPI(
    title="Embrace AI Product Lab",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [
    item.strip()
    for item in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@limiter.exempt
def root():
    return {
        "name": "Embrace AI Product Lab",
        "status": "ok",
    }


@app.get("/health")
@limiter.exempt
def health():
    return {"ok": True}


@app.get("/config-check")
@limiter.limit("30 per minute")
def config_check(request: Request):
    return {
        "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL"),
        "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL"),
        "DEEPSEEK_API_KEY_present": bool(get_secret("DEEPSEEK_API_KEY")),
    }


@app.get("/tasks")
@limiter.limit("60 per minute")
def api_list_tasks(request: Request, limit: int = 20):
    return {
        "ok": True,
        "items": list_tasks(limit=limit),
    }


@app.get("/tasks/{task_id}")
@limiter.limit("60 per minute")
def api_get_task(request: Request, task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    return {
        "ok": True,
        "item": task,
    }


class TaskUpdate(BaseModel):
    status: str | None = None
    owner: str | None = None
    notes: str | None = None


@app.patch("/tasks/{task_id}")
@limiter.limit("30 per minute")
def patch_task(request: Request, task_id: str, payload: TaskUpdate):
    updates = payload.model_dump(exclude_none=True)

    updated = update_task(task_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "ok": True,
        "task": updated,
    }


@app.post("/feishu/webhook")
@limiter.limit("30 per minute")
async def feishu_webhook(request: Request, body: dict[str, Any]):
    # 处理飞书 URL 验证请求（必须在签名验证之前）
    challenge = body.get("challenge")
    if challenge:
        print(f"[Webhook] Handling URL verification challenge: {challenge}")
        return {"challenge": challenge}

    # 验证飞书 webhook 签名
    try:
        verify_feishu_webhook(body)
    except FeishuSecurityError as e:
        print(f"[Webhook] Security validation failed: {e}")
        raise HTTPException(status_code=403, detail="Invalid signature")
    except Exception as e:
        print(f"[Webhook] Warning: Signature verification error: {e}")
        # 继续处理，可能是测试请求或配置问题

    # 解密飞书加密消息（如果配置了加密）
    try:
        body = decrypt_feishu_payload(body)
    except Exception as e:
        print(f"[Webhook] Decrypt error: {e}")
        # 继续处理，可能是未加密的消息

    # 解析任务
    task = extract_text_from_feishu_payload(body)
    text = task.get("raw_text", "").strip()
    status = task.get("status", "queued")
    llm_result = None

    if status != "ignored":
        try:
            llm_result = ask_deepseek_for_design_advice(text)
            status = "completed"
        except Exception as e:
            llm_result = f"LLM error: {e}"
            status = "failed"

    task["status"] = status

    result = {
        "ok": True,
        "source": "feishu",
        "parsed_text": text,
        "task": task,
        "llm_result": llm_result,
    }

    saved = save_task(result)
    result["saved"] = saved

    return result


class OpenCodeTaskCreate(BaseModel):
    message: str
    feishu_chat_id: str | None = None
    feishu_message_id: str | None = None
    notify_on_complete: bool = True


@app.post("/opencode/tasks")
@limiter.limit("10 per minute")
async def create_opencode_task(
    request: Request, payload: OpenCodeTaskCreate, background_tasks: BackgroundTasks
):
    task_id = await opencode_manager.create_task(
        user_message=payload.message,
        feishu_chat_id=payload.feishu_chat_id or os.getenv("FEISHU_DEFAULT_CHAT_ID"),
        feishu_message_id=payload.feishu_message_id,
    )

    background_tasks.add_task(
        run_opencode_with_feishu, task_id, payload.notify_on_complete
    )

    return {
        "ok": True,
        "task_id": task_id,
        "status": "pending",
        "message": "任务已创建，正在后台处理",
    }


async def run_opencode_with_feishu(task_id: str, notify: bool = True):
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
            result = await feishu_client.send_interactive_card(
                task.feishu_chat_id, start_card
            )
            print(f"[OpenCode] Start card result: {result}")

        # 只收集事件，不实时发送
        final_result = None
        error_result = None

        async for event in opencode_manager.run_opencode(task_id):
            event_type = event.get("type", "")
            content = event.get("content", "")
            print(f"[OpenCode] Event: {event_type} - {content[:50]}...")

            if event_type == "done":
                final_result = content
            elif event_type == "error":
                error_result = content

        # 任务完成后发送结果
        if notify and task.feishu_chat_id:
            print(
                f"[OpenCode] Sending result to Feishu, final_result={final_result is not None}, error_result={error_result is not None}"
            )
            if final_result:
                print(
                    f"[OpenCode] Building result card with content length: {len(final_result)}"
                )
                final_card = build_result_card(
                    task_id, task.user_message, task.output_lines, final_result
                )
                result = await feishu_client.send_interactive_card(
                    task.feishu_chat_id, final_card
                )
                print(f"[OpenCode] Result card sent: {result}")
            elif error_result:
                print(f"[OpenCode] Building error card with error: {error_result}")
                card = build_error_card(task_id, error_result)
                result = await feishu_client.send_interactive_card(
                    task.feishu_chat_id, card
                )
                print(f"[OpenCode] Error card sent: {result}")
            else:
                print(f"[OpenCode] No result or error to send")

    except Exception as e:
        print(f"[OpenCode] Error: {e}")
        import traceback

        traceback.print_exc()


@app.get("/opencode/tasks")
@limiter.limit("60 per minute")
async def list_opencode_tasks(request: Request, limit: int = Query(default=20, le=100)):
    tasks = await opencode_manager.list_tasks(limit=limit)
    return {"ok": True, "items": tasks}


@app.get("/opencode/tasks/{task_id}")
@limiter.limit("60 per minute")
async def get_opencode_task(request: Request, task_id: str):
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
            "output_preview": "\n".join(task.output_lines[-10:])
            if task.output_lines
            else None,
            "final_result": task.final_result,
            "error": task.error,
            "feishu_chat_id": task.feishu_chat_id,
        },
    }


@app.get("/opencode/tasks/{task_id}/stream")
@limiter.limit("30 per minute")
async def stream_opencode_task(request: Request, task_id: str):
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


@app.post("/opencode/tasks/{task_id}/abort")
@limiter.limit("10 per minute")
async def abort_opencode_task(request: Request, task_id: str):
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


@app.get("/feishu/config-check")
@limiter.limit("30 per minute")
def feishu_config_check(request: Request):
    return {
        "FEISHU_APP_ID_present": bool(os.getenv("FEISHU_APP_ID")),
        "FEISHU_APP_SECRET_present": bool(get_secret("FEISHU_APP_SECRET")),
    }


@app.post("/feishu/webhook/opencode")
@limiter.limit("30 per minute")
async def feishu_webhook_opencode(
    request: Request, body: dict[str, Any], background_tasks: BackgroundTasks
):
    # 处理飞书 URL 验证请求（必须在签名验证之前）
    # v1 格式: {"type": "url_verification", "challenge": "xxx"}
    # v2 格式: {"schema": "2.0", "header": {"event_type": "..."}, "event": {}, "challenge": "xxx"}
    challenge = body.get("challenge")
    if challenge:
        print(f"[Webhook] Handling URL verification challenge: {challenge}")
        # 飞书要求直接返回 challenge 字段
        return {"challenge": challenge}

    # 验证飞书 webhook 签名
    try:
        verify_feishu_webhook(body)
    except FeishuSecurityError as e:
        print(f"[Webhook] Security validation failed: {e}")
        # 返回 403 拒绝请求
        raise HTTPException(status_code=403, detail="Invalid signature")
    except Exception as e:
        print(f"[Webhook] Warning: Signature verification error: {e}")
        # 继续处理，可能是测试请求或配置问题

    # 解密飞书加密消息（如果配置了加密）
    try:
        body = decrypt_feishu_payload(body)
    except Exception as e:
        print(f"[Webhook] Decrypt error: {e}")
        # 继续处理，可能是未加密的消息

    # 只打印关键信息，避免打印大体积的加密数据
    if "encrypt" in body:
        print(
            f"[Webhook] Received encrypted payload, length: {len(body.get('encrypt', ''))}"
        )
    else:
        print(f"[Webhook] Received: {body}")

    # 使用新的卡片交互处理器
    return await process_feishu_webhook(body, background_tasks)
