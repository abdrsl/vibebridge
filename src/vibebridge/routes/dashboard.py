"""Dashboard API endpoints — all /api/* routes."""
import json
import os
import sqlite3
import subprocess
import time

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from vibebridge._compat import (
    ensure_mycompany_path,
    get_metrics_db,
    get_mycompany_home,
    get_supervisor_conf,
)
from vibebridge.conversation_store import (
    add_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    rename_conversation,
    update_conversation_title_from_message,
)
from vibebridge.gateway import pop_task_mapping, route_webui
from vibebridge.limiter import limiter
from vibebridge.redis_pool import get_redis

router = APIRouter()

PRICING = {
    "moonshot": {"input": 4.0, "output": 12.0},   # yuan per 1M
    "deepseek": {"input": 2.0, "output": 8.0},
    "gpt-4o":   {"input": 18.0, "output": 72.0},
}


def _pricing_key(name: str) -> str:
    name_lower = (name or "").lower()
    for key in PRICING:
        if key in name_lower:
            return key
    if "kimi" in name_lower:
        return "moonshot"
    return "deepseek"


def _get_project_budget() -> float:
    """Sum daily budgets from agent-models.yaml as a proxy project budget."""
    try:
        import yaml
        cp = os.path.expanduser("~/.config/mycompany/agent-models.yaml")
        if os.path.exists(cp):
            with open(cp) as f:
                data = yaml.safe_load(f) or {}
            return sum(cfg.get("budget_daily_yuan", 0) for cfg in data.values())
    except Exception as exc:
        from logging import getLogger
        getLogger(__name__).debug("Failed to load project budget config: %s", exc)
    return 500.0


# ═══════════════════════════════════════════════════ AGENTS

@router.get("/api/agents")
def api_agents():
    """Return agent status (clean names, no mycompany: prefix)."""
    try:
        result = subprocess.run(
            ["supervisorctl", "-c", get_supervisor_conf(), "status"],
            capture_output=True, text=True, timeout=10,
        )
        agents = []
        # Exclude non-agent services
        non_agents = {"workflow-listener", "vibebridge", "openclaw", "feishu"}
        for line in result.stdout.strip().split("\n"):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                name = parts[0].replace("mycompany:", "")  # strip prefix
                if name in non_agents:
                    continue
                agents.append({"name": name, "status": parts[1], "info": parts[2] if len(parts) > 2 else ""})
        return {"agents": agents, "total": len(agents)}
    except Exception as e:
        return {"agents": [], "error": str(e)}


@router.post("/api/agents")
def api_agents_start():
    """Start all agents via supervisorctl."""
    try:
        result = subprocess.run(
            ["supervisorctl", "-c", get_supervisor_conf(), "start", "mycompany:*"],
            capture_output=True, text=True, timeout=30,
        )
        return {"ok": True, "stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════ METRICS

@router.get("/api/metrics")
def api_metrics():
    """Return token usage metrics."""
    try:
        from datetime import datetime
        db = get_metrics_db()
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


@router.get("/api/metrics/v2")
def api_metrics_v2():
    """Enterprise token dashboard — per-agent, per-model, with cost."""
    ensure_mycompany_path()
    try:
        from mycompany.core.metrics import MetricsCollector
        from datetime import datetime
        collector = MetricsCollector()
        today = datetime.now().strftime("%Y-%m-%d")
        daily = collector.query_daily(today)
        total = collector.query_daily_total(today)
        models = collector.query_model_breakdown(today)
        weekly = collector.query_weekly_summary()
        ranking = collector.query_agent_ranking(7)
        # Budget alerts
        alerts = []
        for row in daily:
            cost = row.get("cost_yuan", 0) or 0
            pct = cost / 50.0 * 100 if 50 > 0 else 0
            if pct > 80:
                alerts.append({"agent": row["agent"], "level": "warning" if pct < 95 else "critical", "cost": round(cost,2), "pct": round(pct,1)})
        return {"date": today, "today": {"total_tasks": total.get("tasks",0) or 0, "total_input": total.get("inp",0) or 0, "total_output": total.get("outp",0) or 0, "total_cost_yuan": round(total.get("cost",0) or 0, 2), "active_agents": total.get("agents",0) or 0}, "per_agent": daily, "per_model": models, "weekly": weekly, "ranking_7d": ranking, "budget_alerts": alerts, "pricing": "Moonshot 4/12 | DeepSeek 2/8 | GPT-4o 18/72 ( /1M tokens in/out)"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/metrics/history")
def api_metrics_history(days: int = 7):
    try:
        ensure_mycompany_path()
        from mycompany.core.metrics import MetricsCollector
        collector = MetricsCollector()
        return {"history": collector.query_history(days), "ranking": collector.query_agent_ranking(days)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/metrics/agent-day")
def api_metrics_agent_day(days: int = 7):
    """Agent-Day matrix view like OpenAI usage dashboard."""
    try:
        ensure_mycompany_path()
        from mycompany.core.metrics import get_collector
        collector = get_collector()
        return collector.query_agent_day_matrix(days)
    except Exception as e:
        return {"error": str(e), "agents": [], "dates": [], "matrix": {}, "totals": {}}


@router.get("/api/metrics/hourly")
def api_metrics_hourly(date: str = None):
    """Hourly breakdown for a specific date."""
    try:
        ensure_mycompany_path()
        from mycompany.core.metrics import get_collector
        collector = get_collector()
        return {"date": date or "today", "hourly": collector.query_hourly(date)}
    except Exception as e:
        return {"error": str(e), "date": date, "hourly": []}


@router.get("/api/metrics/predictions")
def api_metrics_predictions(days: int = 7):
    """Cost predictions based on historical trends."""
    try:
        ensure_mycompany_path()
        from mycompany.core.metrics import get_collector
        collector = get_collector()
        return collector.predict_cost(days)
    except Exception as e:
        return {"error": str(e), "predictions": [], "confidence": "low"}


@router.get("/api/metrics/budget/{agent}")
def api_get_budget(agent: str):
    """Get budget settings for an agent."""
    try:
        ensure_mycompany_path()
        from mycompany.core.metrics import get_collector
        return get_collector().get_budget(agent)
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/metrics/budget/{agent}")
def api_set_budget(agent: str, body: dict):
    """Set budget for an agent."""
    try:
        ensure_mycompany_path()
        from mycompany.core.metrics import get_collector
        get_collector().set_budget(
            agent,
            daily=body.get("daily_budget_yuan"),
            weekly=body.get("weekly_budget_yuan"),
            monthly=body.get("monthly_budget_yuan")
        )
        return {"ok": True, "agent": agent}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/metrics/stream")
def api_metrics_stream():
    """Server-Sent Events for real-time token usage updates."""
    import asyncio
    ensure_mycompany_path()
    from mycompany.core.metrics import get_collector
    
    async def event_generator():
        collector = get_collector()
        last_data = None
        while True:
            try:
                from datetime import datetime
                today = datetime.now().strftime("%Y-%m-%d")
                today_total = collector.query_daily_total(today)
                data = {
                    "timestamp": datetime.now().isoformat(),
                    "today": {
                        "cost": today_total.get("cost", 0),
                        "tasks": today_total.get("tasks", 0),
                        "agents": today_total.get("agents", 0),
                        "input": today_total.get("inp", 0),
                        "output": today_total.get("outp", 0),
                    }
                }
                if data != last_data:
                    yield f"data: {json.dumps(data)}\n\n"
                    last_data = data
            except Exception as e:
                yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
            await asyncio.sleep(5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


# ═══════════════════════════════════════════════════ CHAT / COMPACT

@router.get("/compact")
def compact_dashboard():
    """Redirect to unified WebUI."""
    return RedirectResponse(url="/")


@router.post("/api/chat")
def api_chat(body: dict):
    """Send chat to agent, wait for response."""
    agent = body.get("agent", "pm-agent")
    msg = body.get("message", "")
    if not msg:
        return {"ok": False, "error": "message required"}
    import time as _t
    tid = f"webui-{int(_t.time()*1000)}"
    task = {"type":"task","task_id":tid,"from":"webui","to":agent,"description":msg,"priority":0}
    try:
        rd = get_redis()
        rd.publish(f"task.{agent}", json.dumps(task,ensure_ascii=False))
        pubsub = rd.pubsub()
        pubsub.subscribe(f"outbox.{agent}")
        deadline = _t.time() + 40
        while _t.time() < deadline:
            m = pubsub.get_message(timeout=2.0)
            if m and m.get("type") == "message":
                d = json.loads(m["data"])
                if d.get("task_id") == tid:
                    pubsub.close()
                    s = d.get("status", "?")
                    r = d.get("result", {})
                    if s == "failed":
                        return {"ok": True, "agent": agent, "status": "failed",
                                "reply": f"❌ {d.get('error', 'unknown')[:300]}"}
                    reply = str(r.get("response", r.get("summary", r.get("review",
                            r.get("plan", r.get("design", str(r)[:500]))))))
                    return {"ok": True, "agent": agent, "status": s, "reply": reply[:2000]}
        pubsub.close()
        return {"ok":True,"agent":agent,"status":"pending","reply":"Agent thinking..."}
    except Exception as e:
        return {"ok":False,"error":str(e)[:200]}


# ═══════════════════════════════════════════════════ SESSIONS

@router.get("/api/sessions")
@limiter.limit("60 per minute")
def api_list_sessions(request: Request, agent: str | None = None, session_type: str | None = None):
    """List chat sessions, optionally filtered by agent and session_type."""
    return {"ok": True, "sessions": list_conversations(agent, session_type)}


@router.post("/api/sessions")
@limiter.limit("30 per minute")
def api_create_session(request: Request, body: dict):
    """Create a new chat session for an agent."""
    agent = body.get("agent", "")
    title = body.get("title")
    if not agent:
        raise HTTPException(status_code=400, detail="agent required")
    cid = create_conversation(agent, title)
    return {"ok": True, "session_id": cid, "agent": agent, "title": title or "New Session"}


@router.get("/api/sessions/{session_id}")
@limiter.limit("60 per minute")
def api_get_session(request: Request, session_id: str):
    """Get session details with full message history."""
    conv = get_conversation(session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True, "session": conv}


@router.patch("/api/sessions/{session_id}")
@limiter.limit("30 per minute")
def api_rename_session(request: Request, session_id: str, body: dict):
    """Rename a session."""
    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    if rename_conversation(session_id, title):
        return {"ok": True, "title": title}
    raise HTTPException(status_code=404, detail="session not found")


@router.delete("/api/sessions/{session_id}")
@limiter.limit("30 per minute")
def api_delete_session(request: Request, session_id: str):
    """Delete a session and all its messages."""
    if delete_conversation(session_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="session not found")


@router.post("/api/sessions/{session_id}/messages")
@limiter.limit("30 per minute")
def api_send_message(request: Request, session_id: str, body: dict):
    """Send a message in a session and return the agent's reply."""
    conv = get_conversation(session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="session not found")

    agent = conv["agent_name"]
    msg = body.get("message", "").strip()
    model = body.get("model", "")
    if not msg:
        raise HTTPException(status_code=400, detail="message required")

    # Route via Gateway (stores message + registers task mapping)
    chat_id = conv.get("chat_id", "")
    routed = route_webui(agent, msg, session_id, model, chat_id)
    tid = routed["task_id"]
    task = routed["task"]
    update_conversation_title_from_message(session_id)

    try:
        import time as _t
        rd = get_redis()
        rd.publish(f"task.{agent}", json.dumps(task, ensure_ascii=False))
        pubsub = rd.pubsub()
        pubsub.subscribe(f"outbox.{agent}")
        deadline = _t.time() + 40
        while _t.time() < deadline:
            m = pubsub.get_message(timeout=2.0)
            if m and m.get("type") == "message":
                d = json.loads(m["data"])
                if d.get("task_id") == tid:
                    pubsub.close()
                    s = d.get("status", "?")
                    r = d.get("result", {})
                    # Mark task as handled by API to prevent duplicate storage by outbox listener
                    mapping = pop_task_mapping(tid)
                    if not mapping:
                        # Already handled by outbox listener — just return reply without storing
                        if s == "failed":
                            reply = f"❌ {d.get('error', 'unknown')[:300]}"
                            return {"ok": True, "agent": agent, "status": "failed", "reply": reply}
                        reply = str(r.get("response", r.get("summary", r.get("review",
                                r.get("plan", r.get("design", str(r)[:500]))))))
                        return {"ok": True, "agent": agent, "status": s, "reply": reply[:2000]}
                    if s == "failed":
                        reply = f"❌ {d.get('error', 'unknown')[:300]}"
                        add_message(session_id, "assistant", reply, {"task_id": tid, "status": "failed", "source": "agent"})
                        return {"ok": True, "agent": agent, "status": "failed", "reply": reply}
                    reply = str(r.get("response", r.get("summary", r.get("review",
                            r.get("plan", r.get("design", str(r)[:500]))))))
                    add_message(session_id, "assistant", reply, {
                        "task_id": tid,
                        "status": s,
                        "model": model,
                        "source": "agent",
                    })
                    return {"ok": True, "agent": agent, "status": s, "reply": reply[:2000]}
        pubsub.close()
        # Agent is still thinking; store a placeholder
        add_message(session_id, "assistant", "⏳ Agent is thinking...", {"task_id": tid, "status": "pending"})
        return {"ok": True, "agent": agent, "status": "pending", "reply": "Agent thinking..."}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@router.get("/api/sessions/group")
@limiter.limit("60 per minute")
def api_get_group_session(request: Request, chat_id: str):
    """Get the group session for a Feishu chat, with full message history."""
    try:
        from vibebridge.conversation_store import list_conversations, get_conversation
        sessions = list_conversations(session_type="group", status="active")
        for sess in sessions:
            if sess.get("chat_id") == chat_id:
                return {"ok": True, "session": get_conversation(sess["id"])}
        return {"ok": False, "error": "Group session not found", "chat_id": chat_id}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@router.get("/api/sessions/private")
@limiter.limit("60 per minute")
def api_get_private_session(request: Request, agent_a: str, agent_b: str):
    """Get the private collaboration session between two agents."""
    try:
        from vibebridge.conversation_store import find_private_session, get_conversation
        sess = find_private_session(agent_a, agent_b)
        if sess:
            return {"ok": True, "session": get_conversation(sess["id"])}
        return {"ok": False, "error": "Private session not found", "agent_a": agent_a, "agent_b": agent_b}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@router.get("/api/sessions/project")
@limiter.limit("30 per minute")
def api_get_project_sessions(request: Request, project_id: str):
    """List all sessions (group + private + main) tagged with a project_id in their messages."""
    try:
        from vibebridge.conversation_store import _DB_PATH, get_conversation
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT DISTINCT conversation_id FROM messages WHERE metadata LIKE ?",
            (f'%"project_id": "{project_id}"%',),
        ).fetchall()
        sessions = []
        for row in rows:
            conv = get_conversation(row["conversation_id"])
            if conv:
                sessions.append({"id": conv["id"], "title": conv.get("title"), "session_type": conv.get("session_type"), "status": conv.get("status")})
        conn.close()
        return {"ok": True, "project_id": project_id, "sessions": sessions}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ═══════════════════════════════════════════════════ CONFIG

@router.get("/api/config")
def api_config():
    try:
        ensure_mycompany_path()
        from mycompany.config.secrets import SecretsManager
        from mycompany.config.bots import BotRegistry
        sm = SecretsManager()
        secrets = [{"name":s,"masked":((sm.get(s)or"****")[:8]+"...")} for s in sm.list()]
        bots = [{"agent":b.agent,"bot_name":b.bot_name,"enabled":b.enabled,"chat_id":b.chat_id or "","group_chat_id":b.group_chat_id or "","p2p_chat_id":b.p2p_chat_id or ""} for b in BotRegistry().list_all()]
        return {"secrets":secrets,"bots":bots}
    except Exception as e:
        return {"error":str(e)}


@router.post("/api/config/secrets")
def api_config_secrets(body: dict):
    k, v = body.get("key",""), body.get("value","")
    if not k or not v:
        return {"ok": False}
    ensure_mycompany_path()
    from mycompany.config.secrets import SecretsManager
    SecretsManager().set(k, v)
    return {"ok": True}


@router.post("/api/config/bots")
def api_config_bots(body: dict):
    a = body.get("agent","")
    aid = body.get("app_id","")
    sec = body.get("app_secret","")
    if not a:
        return {"ok": False}
    ensure_mycompany_path()
    from mycompany.config.bots import BotRegistry, BotConfig
    from mycompany.config.secrets import SecretsManager
    sm = SecretsManager()
    r = BotRegistry()
    e = r.get(a)
    c = BotConfig(agent=a, bot_name=body.get("bot_name",f"{a} Bot"),
                  chat_id=body.get("chat_id",""), group_chat_id=body.get("group_chat_id",""),
                  p2p_chat_id=body.get("p2p_chat_id",""),
                  keywords=e.keywords if e else [], enabled=body.get("enabled",True))
    if aid:
        sm.set(f"FEISHU_{a.replace('-','_').upper()}_APP_ID", aid)
    if sec:
        sm.set(f"FEISHU_{a.replace('-','_').upper()}_APP_SECRET", sec)
    r.save(c)
    return {"ok": True}


@router.post("/api/config/agent-model")
def api_config_agent_model(body: dict):
    a = body.get("agent","")
    p = body.get("primary","moonshot/kimi-k2.5")
    f = body.get("fallback","deepseek/deepseek-chat")
    b = body.get("budget",50)
    if not a:
        return {"ok": False}
    import yaml
    ensure_mycompany_path()
    cp = os.path.expanduser("~/.config/mycompany/agent-models.yaml")
    if os.path.exists(cp):
        with open(cp) as fh:
            data = yaml.safe_load(fh) or {}
    else:
        data = {}
    data[a] = {"primary":p,"fallback":f,"budget_daily_yuan":b}
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp,"w") as fh:
        yaml.dump(data, fh, allow_unicode=True)
    return {"ok":True,"saved":a}


@router.get("/api/config/agent-models")
def api_get_agent_models():
    import yaml
    cp = os.path.expanduser("~/.config/mycompany/agent-models.yaml")
    if os.path.exists(cp):
        with open(cp) as f:
            return {"models": yaml.safe_load(f) or {}}
    return {"models": {}}


@router.get("/api/openclaw/status")
def api_openclaw_status():
    """MyCompany now runs fully independent of OpenClaw."""
    return {"ok":True,"independent":True,"message":"MyCompany runs independently. API keys from env/SecretsManager."}


# ═══════════════════════════════════════════════════ PROJECTS

@router.get("/api/projects")
@router.post("/api/projects")
def api_projects(body: dict = None):
    """List or create projects."""
    home = os.environ.get("MYCOMPANY_HOME", os.path.expanduser("~/workspace/MyCompany"))
    proj_dir = os.path.join(home, "Projects")
    if body and "name" in body:
        name = body["name"]
        depts = body.get("departments","SW,HW,TEST")
        d = os.path.join(proj_dir, name)
        os.makedirs(d, exist_ok=True)
        # Create dept workspaces
        dm = {"SW":"Software-Engineer","HW":"Hardware-Engineer","TEST":"Test-Engineer","PM":"PM"}
        ws = os.path.join(home, "Workspace")
        for dept in depts.split(","):
            folder = dm.get(dept.strip().upper(), dept.strip())
            os.makedirs(os.path.join(ws, folder, name, "src"), exist_ok=True)
            os.makedirs(os.path.join(ws, folder, name, "docs"), exist_ok=True)
        subprocess.run(["git","-C",d,"init"],capture_output=True)
        return {"ok":True,"name":name}
    # List
    projects = []
    if os.path.isdir(proj_dir):
        for f in sorted(os.listdir(proj_dir)):
            p = os.path.join(proj_dir, f)
            if os.path.isdir(p) and not f.startswith("."):
                projects.append({"name":f,"files":len(os.listdir(p))})
    return {"projects":projects}


@router.get("/api/projects/{project_id}/costs")
def api_project_costs(project_id: str):
    """Return total tokens, total cost (CNY), and per-agent breakdown for a project."""
    agents_dict = {}
    spent_yuan = 0.0
    try:
        db_path = os.path.expanduser("~/.config/mycompany/metrics.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT agent, source, input_tokens, output_tokens FROM metrics WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        conn.close()

        for r in rows:
            agent = r["agent"] or "unknown"
            source = r["source"] or ""
            inp = r["input_tokens"] or 0
            out = r["output_tokens"] or 0

            key = _pricing_key(source)
            if key == "deepseek":
                key = _pricing_key(agent)
            price = PRICING.get(key, PRICING["deepseek"])
            cost = (inp / 1_000_000) * price["input"] + (out / 1_000_000) * price["output"]

            if agent not in agents_dict:
                agents_dict[agent] = {
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost_yuan": 0.0,
                }
            agents_dict[agent]["tokens_in"] += inp
            agents_dict[agent]["tokens_out"] += out
            agents_dict[agent]["cost_yuan"] += cost
            spent_yuan += cost
    except Exception as exc:
        # metrics.db may not exist or schema missing — return placeholder schema
        from logging import getLogger
        getLogger(__name__).debug("Project cost query failed (metrics.db may be missing): %s", exc)

    budget_yuan = _get_project_budget()

    if not agents_dict:
        agents_dict = {
            "software-agent": {"tokens_in": 0, "tokens_out": 0, "cost_yuan": 0.0},
            "pm-agent": {"tokens_in": 0, "tokens_out": 0, "cost_yuan": 0.0},
            "test-agent": {"tokens_in": 0, "tokens_out": 0, "cost_yuan": 0.0},
        }

    return {
        "project_id": project_id,
        "budget_yuan": round(budget_yuan, 2),
        "spent_yuan": round(spent_yuan, 2),
        "agents": agents_dict,
    }


@router.get("/api/projects/{project_id}/status")
def api_project_status(project_id: str):
    """Return workflow status from Redis (checks workflow:* keys)."""
    try:
        rd = get_redis()
        workflows = []
        for key in rd.scan_iter(match="workflow:*", count=100):
            key_type = rd.type(key)
            if key_type == "hash":
                data = rd.hgetall(key)
                workflows.append({"key": key, "type": "hash", "data": data})
            elif key_type == "string":
                val = rd.get(key)
                workflows.append({"key": key, "type": "string", "value": val})
            elif key_type == "list":
                length = rd.llen(key)
                workflows.append({"key": key, "type": "list", "length": length})
            else:
                workflows.append({"key": key, "type": key_type})
        return {
            "project_id": project_id,
            "active": len(workflows) > 0,
            "workflows": workflows,
        }
    except Exception as e:
        return {
            "project_id": project_id,
            "active": False,
            "workflows": [],
            "error": str(e),
        }


@router.get("/api/projects/{project_name}/progress")
def api_project_progress(project_name: str):
    """Return SpecKit progress for a project."""
    ensure_mycompany_path()
    try:
        from mycompany.core.speckit_engine import get_speckit_engine
        proj_path = os.path.join(get_mycompany_home(), "Projects", project_name)
        engine = get_speckit_engine(proj_path)
        tasks = engine._tasks.get("tasks", [])
        
        total = len(tasks)
        dispatched = sum(1 for t in tasks if t.get("status") == "dispatched")
        in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        
        return {
            "project": project_name,
            "tasks": tasks,
            "summary": {
                "total": total, "pending": pending, "dispatched": dispatched,
                "in_progress": in_progress, "completed": completed,
                "progress_pct": round((completed / total * 100) if total > 0 else 0),
            }
        }
    except Exception as e:
        return {"error": str(e), "project": project_name, "tasks": [], "summary": {}}


# ═══════════════════════════════════════════════════ WORKFLOWS & WEBHOOKS

@router.post("/api/webhook/n8n/{workflow_name}")
def api_n8n_webhook(workflow_name: str, body: dict[str, Any]):
    """n8n-compatible webhook endpoint for workflow automation.
    
    n8n can POST to this endpoint to trigger MyCompany workflows.
    Example n8n HTTP Request node:
      Method: POST
      URL: http://localhost:8000/api/webhook/n8n/ceo_idea_pipeline
      Body: {"idea": "...", "chat_id": "oc_xxx", "agents": ["software","hardware"]}
    """
    import time as _t
    import json as _j
    ensure_mycompany_path()
    
    try:
        rd = get_redis()
        
        # Spawn workflow
        task_id = f"n8n-{workflow_name}-{int(_t.time()*1000)}"
        idea = body.get("idea", body.get("description", str(body)[:500]))
        agents = body.get("agents", [])
        chat_id = body.get("chat_id", "")
        
        # Dispatch to mentioned agents
        for agent in agents:
            rd.publish(f"task.{agent}", _j.dumps({
                "type":"task","task_id":f"{task_id}-{agent}",
                "from":"n8n","to":agent,"description":idea,
                "chat_id":chat_id,"priority":0,"timestamp":_t.time()
            }, ensure_ascii=False))
        
        # Start workflow engine
        try:
            from mycompany.core.workflow_engine import WorkflowEngine
            engine = WorkflowEngine(rd)
            workflow_id = engine.start(workflow_name, {
                "project_id": body.get("project_id", task_id),
                "idea": idea,
                "agents": agents,
            })
            return {"ok": True, "task_id": task_id, "workflow_id": workflow_id,
                    "agents_dispatched": len(agents)}
        except Exception:
            return {"ok": True, "task_id": task_id, "agents_dispatched": len(agents)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@router.get("/api/workflows")
def api_workflows():
    """Return active workflow status for WebUI Dashboard."""
    try:
        import json as _j
        rd = get_redis()
        
        workflows = []
        for key in rd.scan_iter(match="workflow:*", count=50):
            val = rd.get(key)
            if val:
                try:
                    wf = _j.loads(val)
                    wf["key"] = key
                    workflows.append(wf)
                except (json.JSONDecodeError, KeyError):
                    pass
        
        # Sort by created_at desc
        workflows.sort(key=lambda w: w.get("created_at", 0), reverse=True)
        
        return {
            "workflows": workflows[:20],
            "total": len(workflows),
            "active": sum(1 for w in workflows if w.get("status") == "in_progress"),
            "completed": sum(1 for w in workflows if w.get("status") == "completed"),
        }
    except Exception as e:
        return {"error": str(e), "workflows": []}


@router.get("/api/webhook/health")
def api_webhook_health():
    """Health check for n8n/power-automate webhook monitoring."""
    return {"ok": True, "service": "mycompany-webhook", "timestamp": time.time()}
