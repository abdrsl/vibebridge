"""
OpenCode-Feishu Bridge - Main FastAPI application with multi-agent architecture.
"""

import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Approval system integration - 审核机器人C (已禁用)
# from src.approval import register_approval_routes
from src.legacy.feishu_card_handler import process_feishu_webhook

# Legacy imports for compatibility (will be migrated to agents)
from src.legacy.feishu_client import (
    build_error_card,
    build_progress_card,
    build_result_card,
    build_start_card,
    feishu_client,
)
from src.legacy.feishu_crypto import (
    FeishuSecurityError,
    decrypt_feishu_payload,
    verify_feishu_webhook,
)
from src.legacy.opencode_integration import TaskStatus, opencode_manager
from src.legacy.secure_config import get_secret
from src.legacy.task_parser import extract_text_from_feishu_payload
from src.legacy.task_store import get_task, list_tasks, save_task, update_task

# Multi-agent system
from src.system import get_system, start_multi_agent_system, stop_multi_agent_system

APPROVAL_SYSTEM_ENABLED = False  # 已禁用
# print("✅ Approval system (机器人C) loaded")  # 已禁用

# WebSocket 长连接支持
FEISHU_WEBSOCKET_AVAILABLE = False
start_feishu_websocket = None

try:
    from src.feishu_websocket import start_feishu_websocket

    FEISHU_WEBSOCKET_AVAILABLE = True
except ImportError:
    print("[WebSocket] 模块未找到，WebSocket功能不可用")

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with multi-agent system."""
    print("App starting...")
    print("[System] Starting multi-agent system...")
    try:
        await start_multi_agent_system()
    except Exception as e:
        print(f"[System] Error starting multi-agent system: {e}")
        # Continue without multi-agent system

    # 启动Feishu WebSocket客户端（如果启用）
    websocket_client = None
    if FEISHU_WEBSOCKET_AVAILABLE and start_feishu_websocket:
        try:
            websocket_client = await start_feishu_websocket()
            if websocket_client:
                print("[WebSocket] Feishu WebSocket客户端已启动")
            else:
                print("[WebSocket] Feishu WebSocket客户端未启用或启动失败")
        except Exception as e:
            print(f"[WebSocket] 启动Feishu WebSocket客户端时出错: {e}")
    elif FEISHU_WEBSOCKET_AVAILABLE:
        print("[WebSocket] WebSocket模块已加载但start_feishu_websocket函数不可用")

    yield

    # 关闭Feishu WebSocket客户端
    if websocket_client:
        try:
            await websocket_client.stop()
            print("[WebSocket] Feishu WebSocket客户端已停止")
        except Exception as e:
            print(f"[WebSocket] 停止Feishu WebSocket客户端时出错: {e}")

    print("App shutting down...")
    try:
        await stop_multi_agent_system()
    except Exception as e:
        print(f"[System] Error stopping multi-agent system: {e}")


app = FastAPI(
    title="OpenCode-Feishu Bridge - Multi-Agent System",
    version="1.0.0",
    description="Open-source AI coding agent service with Feishu integration",
    lifespan=lifespan,
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files — serve dashboard assets (animated.html, 3d-office-v2.html, etc.)
from fastapi.staticfiles import StaticFiles as _StaticFiles
_dashboard_dir = os.environ.get("MYCOMPANY_DASHBOARD_DIR", "/home/akliedrak/workspace/dashboard")
if os.path.isdir(_dashboard_dir):
    app.mount("/dashboard/static", _StaticFiles(directory=_dashboard_dir, html=True), name="dashboard_static")
    app.mount("/dashboard", _StaticFiles(directory=_dashboard_dir, html=True), name="dashboard")


@app.get("/")
@limiter.exempt
def root():
    """Root endpoint."""
    return {
        "name": "OpenCode-Feishu Bridge",
        "version": "1.0.0",
        "status": "ok",
        "architecture": "multi-agent",
        "agents": 6,
    }


@app.get("/health")
@limiter.exempt
def health():
    """Health check endpoint."""
    system = get_system()
    return {
        "ok": True,
        "timestamp": time.time(),
        "multi_agent_system": system.is_running() if system else False,
    }


@app.get("/system/status")
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


# Legacy endpoints for backward compatibility
@app.get("/config-check")
@limiter.limit("30 per minute")
def config_check(request: Request):
    """Configuration check endpoint."""
    return {
        "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL"),
        "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL"),
        "DEEPSEEK_API_KEY_present": bool(get_secret("DEEPSEEK_API_KEY")),
    }


@app.get("/tasks")
@limiter.limit("60 per minute")
def api_list_tasks(request: Request, limit: int = 20):
    """List tasks."""
    return {
        "ok": True,
        "items": list_tasks(limit=limit),
    }


@app.get("/tasks/{task_id}")
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


class TaskUpdate(BaseModel):
    status: str | None = None
    owner: str | None = None
    notes: str | None = None


@app.patch("/tasks/{task_id}")
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


@app.post("/feishu/webhook")
@limiter.limit("30 per minute")
async def feishu_webhook(request: Request, body: dict[str, Any]):
    """Legacy Feishu webhook endpoint (DeepSeek LLM)."""
    # Handle Feishu URL verification
    challenge = body.get("challenge")
    if challenge:
        print(f"[Webhook] Handling URL verification challenge: {challenge}")
        return {"challenge": challenge}

    # Verify Feishu webhook signature
    try:
        verify_feishu_webhook(body)
    except FeishuSecurityError as e:
        print(f"[Webhook] Security validation failed: {e}")
        raise HTTPException(status_code=403, detail="Invalid signature")
    except Exception as e:
        print(f"[Webhook] Warning: Signature verification error: {e}")
        # Continue, might be test request

    # Decrypt Feishu encrypted message
    try:
        body = decrypt_feishu_payload(body)
    except Exception as e:
        print(f"[Webhook] Decrypt error: {e}")
        # Continue, might be unencrypted message

    # Parse task
    task = extract_text_from_feishu_payload(body)
    text = task.get("raw_text", "").strip()

    # Use multi-agent system if available
    system = get_system()
    if system and system.is_running():
        # TODO: Route to LLM agent
        llm_result = "Multi-agent system processing (TODO)"
    else:
        # Fallback to legacy LLM
        from src.legacy.llm import ask_deepseek_for_design_advice

        try:
            llm_result = ask_deepseek_for_design_advice(text)
        except Exception as e:
            llm_result = f"LLM error: {e}"

    task["status"] = "completed"

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
        feishu_chat_id=payload.feishu_chat_id or os.getenv("FEISHU_DEFAULT_CHAT_ID"),
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


@app.get("/opencode/tasks")
@limiter.limit("60 per minute")
async def list_opencode_tasks(request: Request, limit: int = Query(default=20, le=100)):
    """List OpenCode tasks."""
    tasks = await opencode_manager.list_tasks(limit=limit)
    return {"ok": True, "items": tasks}


@app.get("/opencode/tasks/{task_id}")
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


@app.get("/opencode/tasks/{task_id}/stream")
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


@app.post("/opencode/tasks/{task_id}/abort")
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


@app.get("/feishu/config-check")
@limiter.limit("30 per minute")
def feishu_config_check(request: Request):
    """Feishu configuration check."""
    return {
        "FEISHU_APP_ID_present": bool(os.getenv("FEISHU_APP_ID")),
        "FEISHU_APP_SECRET_present": bool(get_secret("FEISHU_APP_SECRET")),
    }


@app.post("/feishu/webhook/opencode")
@limiter.limit("30 per minute")
async def feishu_webhook_opencode(
    request: Request, body: dict[str, Any], background_tasks: BackgroundTasks
):
    """Feishu webhook endpoint for OpenCode integration."""
    # Handle Feishu URL verification
    challenge = body.get("challenge")
    if challenge:
        print(f"[Webhook] Handling URL verification challenge: {challenge}")
        return {"challenge": challenge}

    # Verify Feishu webhook signature
    try:
        verify_feishu_webhook(body)
    except FeishuSecurityError as e:
        print(f"[Webhook] Security validation failed: {e}")
        raise HTTPException(status_code=403, detail="Invalid signature")
    except Exception as e:
        print(f"[Webhook] Warning: Signature verification error: {e}")
        # Continue, might be test request

    # Decrypt Feishu encrypted message
    try:
        body = decrypt_feishu_payload(body)
    except Exception as e:
        print(f"[Webhook] Decrypt error: {e}")
        # Continue, might be unencrypted message

    # Use new card interaction processor
    return await process_feishu_webhook(body, background_tasks)


@app.post("/internal/notify")
@limiter.limit("60 per minute")
async def internal_notify(request: Request, body: dict[str, Any] = None):
    """Receive notifications from OpenClaw gateway."""
    # Log the notification for debugging
    print(f"[Notify] Received notification: {body}")
    # Return 200 OK to acknowledge receipt
    return {"ok": True, "received": True}


# ============================================
# OpenClaw 审批系统集成（自动生成）
# ============================================

# 导入审批插件
import sys

sys.path.insert(0, str(Path(__file__).parent))

# 执行插件代码 - 暂时跳过
try:
    # exec(open(Path(__file__).parent.parent / "approval_plugin.py").read())
    # print("✅ OpenClaw 审批系统已集成")
    print("✅ OpenClaw 审批系统已跳过")
except Exception as e:
    print(f"⚠️  OpenClaw 审批系统集成失败: {e}")
    print("⚠️  继续运行（审批功能不可用）")


# ============================================
# Approval System Routes (机器人C)
# ============================================
# try:
#     register_approval_routes(app)
#     print("✅ Approval routes registered (机器人C)")
# except Exception as e:
#     print(f"⚠️ Approval routes registration failed: {e}")


# ============================================
# MyCompany Dashboard API
# ============================================

@app.get("/api/agents")
def api_agents():
    """Return agent status."""
    try:
        import subprocess
        result = subprocess.run(
            ["supervisorctl", "-c", "/home/akliedrak/workspace/MyCompany/.config/supervisor/mycompany.conf", "status"],
            capture_output=True, text=True, timeout=10,
        )
        agents = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                agents.append({"name": parts[0], "status": parts[1], "info": parts[2] if len(parts) > 2 else ""})
        return {"agents": agents}
    except Exception as e:
        return {"agents": [], "error": str(e)}


@app.get("/api/metrics")
def api_metrics():
    """Return token usage metrics."""
    try:
        import sqlite3
        from datetime import datetime
        db = "/home/akliedrak/workspace/MyCompany/.system/metrics.db"
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT agent, COUNT(*) as tasks, SUM(input_tokens) as input, SUM(output_tokens) as output, SUM(duration_seconds) as duration FROM metrics WHERE timestamp LIKE ? GROUP BY agent",
            (f"{today}%",),
        ).fetchall()
        conn.close()
        return {"metrics": [dict(r) for r in rows], "date": today}
    except Exception as e:
        return {"metrics": [], "error": str(e)}


@app.get("/compact")
def compact_dashboard():
    """Compact real-time dashboard (inline). Full dashboard at /dashboard/animated.html."""
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MyCompany Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',monospace;background:#0d1117;color:#c9d1d9;padding:20px}
h1{color:#58a6ff;margin-bottom:4px;font-size:20px}
.sub{color:#8b949e;margin-bottom:16px;font-size:13px}
.links{margin-bottom:20px;display:flex;gap:12px}
.links a{color:#58a6ff;text-decoration:none;font-size:13px;padding:6px 14px;background:#161b22;border:1px solid #30363d;border-radius:6px}
.links a:hover{background:#21262d;border-color:#58a6ff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}
.card h3{font-size:14px;margin-bottom:10px;display:flex;justify-content:space-between}
.card h3 .name{color:#c9d1d9}
.status-running{color:#3fb950}
.status-stopped{color:#f85149}
.row{display:flex;justify-content:space-between;padding:3px 0;font-size:13px}
.row .label{color:#8b949e}
.row .value{color:#c9d1d9}
.bar{height:4px;border-radius:2px;margin-top:8px;background:#21262d}
.bar-fill{height:100%;border-radius:2px;transition:width .5s}
.bar-fill.green{background:#3fb950}
.bar-fill.yellow{background:#d2991d}
.bar-fill.red{background:#f85149}
.error{color:#f85149;font-size:12px;padding:8px}
.summary{grid-column:1/-1;display:flex;gap:20px}
.summary .stat{text-align:center}
.summary .stat .num{font-size:28px;font-weight:bold}
.summary .stat .lbl{font-size:12px;color:#8b949e}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:center">
<h1>MyCompany</h1>
<div class="links">
  <a href="/compact">Compact</a>
  <a href="/dashboard/animated.html" target="_blank">Animated</a>
  <a href="/dashboard/3d-office-v2.html" target="_blank">3D Office</a>
  <a href="/api/agents" target="_blank">API</a>
</div>
</div>
<p class="sub">Live status &bull; Refresh 5s &bull; <span id="clock">--</span></p>

<div class="summary" id="summary"></div>
<div class="grid" id="agents"></div>

<script>
function timeAgo(ts){if(!ts)return"never";const s=(Date.now()-new Date(ts).getTime())/1000;if(s<60)return Math.floor(s)+"s";if(s<3600)return Math.floor(s/60)+"m";return Math.floor(s/3600)+"h"}
function fmt(n){return n>=1000?(n/1000).toFixed(1)+"k":String(n)}

async function load(){
  document.getElementById("clock").textContent=new Date().toLocaleTimeString();
  try{
    const[a,m,d]=await Promise.all([
      fetch("/api/agents").then(r=>r.json()),
      fetch("/api/metrics").then(r=>r.json()),
      fetch("/_dlq_stats").then(r=>r.json()).catch(()=>({total:0,pending:0}))
    ]);
    const agents=a.agents||[],metrics=m.metrics||[];
    const mm={};metrics.forEach(x=>{mm[x.agent]=x});

    const online=agents.filter(x=>x.status==="RUNNING").length;
    const totalTasks=metrics.reduce((s,x)=>s+(x.tasks||0),0);
    const dlq=d.pending||0;

    document.getElementById("summary").innerHTML=
      `<div class="stat"><div class="num" style="color:#3fb950">${online}</div><div class="lbl">Online</div></div>
       <div class="stat"><div class="num">${agents.length}</div><div class="lbl">Total</div></div>
       <div class="stat"><div class="num">${totalTasks}</div><div class="lbl">Tasks</div></div>
       <div class="stat"><div class="num" style="color:${dlq>0?'#f85149':'#8b949e'}">${dlq}</div><div class="lbl">DLQ</div></div>`;

    document.getElementById("agents").innerHTML=agents.map(a=>{
      const isRunning=a.status==="RUNNING";
      const m=mm[a.name.replace(/-agent$/,"")]||{};
      const tasks=m.tasks||0,inp=m.input||0,out=m.output||0,dur=m.duration||0;
      return `<div class="card">
        <h3><span class="name">${a.name}</span><span class="${isRunning?'status-running':'status-stopped'}">${a.status}</span></h3>
        <div class="row"><span class="label">Tasks</span><span class="value">${tasks}</span></div>
        <div class="row"><span class="label">Tokens In</span><span class="value">${fmt(inp)}</span></div>
        <div class="row"><span class="label">Tokens Out</span><span class="value">${fmt(out)}</span></div>
        <div class="row"><span class="label">Duration</span><span class="value">${Number(dur).toFixed(0)}s</span></div>
        <div class="bar"><div class="bar-fill ${isRunning?'green':'red'}" style="width:${Math.min(tasks*20,100)}%"></div></div>
      </div>`;
    }).join("");
  }catch(e){
    document.getElementById("agents").innerHTML=`<div class="card"><p class="error">Connection error: ${e.message}</p></div>`;
  }
}
load();setInterval(load,5000);
</script>
</body>
</html>'''
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


@app.get("/api/tasks")
def api_tasks_list(limit: int = 50):
    """Return task list from the MyCompany system."""
    try:
        import redis
        r = redis.Redis(
            host=os.environ.get("MYCOMPANY_REDIS_HOST", "localhost"),
            port=int(os.environ.get("MYCOMPANY_REDIS_PORT", "6379")),
            password=os.environ.get("MYCOMPANY_REDIS_PASSWORD", "mycompany2026"),
            decode_responses=True,
            socket_connect_timeout=3,
        )
        tasks = []
        for agent_chan in r.pubsub_channels():
            if agent_chan.startswith(b"task.") or agent_chan.startswith(b"outbox."):
                tasks.append({"channel": agent_chan.decode()})
        return {"tasks": tasks[:limit]}
    except Exception as e:
        return {"tasks": [], "error": str(e)}


@app.get("/_dlq_stats")
def dlq_stats():
    """Return dead letter queue stats from MyCompany DB."""
    try:
        import sqlite3
        from pathlib import Path
        db_path = os.environ.get("MYCOMPANY_HOME", os.path.expanduser("~/workspace/MyCompany")) + "/.system/dead_letter.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) as c FROM dead_letters").fetchone()["c"]
        pending = conn.execute("SELECT COUNT(*) as c FROM dead_letters WHERE status='pending'").fetchone()["c"]
        conn.close()
        return {"total": total, "pending": pending}
    except Exception:
        return {"total": 0, "pending": 0}


# ============================================
# Server Startup
# ============================================
if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
