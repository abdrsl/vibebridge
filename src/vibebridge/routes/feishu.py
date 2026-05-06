"""Feishu webhook and card interaction endpoints."""
import json
import os
import re
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from vibebridge._compat import ensure_mycompany_path
from vibebridge.gateway import is_actual_task, route_feishu_group, route_feishu_p2p
from vibebridge.legacy.feishu_card_handler import process_feishu_webhook
from vibebridge.legacy.feishu_crypto import (
    FeishuSecurityError,
    decrypt_feishu_payload,
    verify_feishu_webhook,
)
from vibebridge.legacy.secure_config import get_secret
from vibebridge.legacy.task_parser import extract_text_from_feishu_payload
from vibebridge.limiter import limiter
from vibebridge.redis_pool import get_redis

router = APIRouter()

BOT_NAME_MAPPING = {
    "ceo": "ceo-agent", "ceo agent": "ceo-agent",
    "admin": "admin-agent", "admin assistant": "admin-agent",
    "pm": "pm-agent", "project manager": "pm-agent", "project-manager": "pm-agent",
    "software engineer": "software-agent", "software": "software-agent",
    "hardware": "hardware-agent", "hardware engineer": "hardware-agent",
    "structure": "structure-agent", "structure engineer": "structure-agent",
    "test": "test-agent", "test engineer": "test-agent",
    "reviewer": "reviewer-agent", "acceptance": "reviewer-agent",
    "it-ops": "it-ops-agent", "it ops": "it-ops-agent", "it": "it-ops-agent",
    "hr": "hr-agent",
}


@router.get("/feishu/config-check")
@limiter.limit("30 per minute")
def feishu_config_check(request: Request):
    """Feishu configuration check."""
    return {
        "FEISHU_APP_ID_present": bool(os.getenv("FEISHU_APP_ID")),
        "FEISHU_APP_SECRET_present": bool(get_secret("FEISHU_APP_SECRET")),
    }


@router.post("/feishu/webhook")
@limiter.limit("30 per minute")
async def feishu_webhook(request: Request, body: dict[str, Any]):
    """Legacy Feishu webhook endpoint (DeepSeek LLM)."""
    # Handle Feishu URL verification
    challenge = body.get("challenge")
    if challenge:
        print(f"[Webhook] Handling URL verification challenge: {challenge}")
        return {"challenge": challenge}

    # Dedup: skip duplicate messages within 5 minutes
    try:
        chat_id = body.get("event", {}).get("message", {}).get("chat_id", "")
        text = body.get("event", {}).get("message", {}).get("content", "")
        try:
            text = json.loads(text).get("text", text)
        except (json.JSONDecodeError, TypeError):
            pass

        msg_hash = hash(chat_id + text[:200])
        if not hasattr(feishu_webhook, '_recent'):
            feishu_webhook._recent = {}
        now = time.time()
        if msg_hash in feishu_webhook._recent and now - feishu_webhook._recent[msg_hash] < 300:
            print(f"[Webhook] Skipped duplicate (hash={msg_hash})")
            return {"ok": True, "skipped": True, "reason": "duplicate"}
        feishu_webhook._recent[msg_hash] = now
        # Clean old entries
        feishu_webhook._recent = {h:t for h,t in feishu_webhook._recent.items() if now - t < 600}
    except Exception as exc:
        from logging import getLogger
        getLogger(__name__).debug("Webhook dedup check failed: %s", exc)

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

    if not text:
        return {"ok": False, "error": "Empty message", "task": task}

    # ── Filter out bot-to-bot messages to prevent echo loops ──
    sender_type = (
        body.get("event", {}).get("sender", {}).get("sender_type", "")
        or body.get("sender", {}).get("sender_type", "")
    )
    sender_id = (
        body.get("event", {}).get("sender", {}).get("sender_id", {}).get("app_id", "")
        or body.get("sender", {}).get("sender_id", {}).get("app_id", "")
    )
    # Skip messages from bots (app type sender) to avoid agent replies triggering new tasks
    if sender_type == "app":
        print(f"[Webhook] Skipping bot-to-bot message from app_id={sender_id[:15]}...")
        return {"ok": True, "skipped": True, "reason": "bot_sender"}
    # Skip canned responses from agents
    canned_patterns = ["【", "】收到", "收到，系统正常", "收到。我是", "待命", "已就位"]
    if any(p in text for p in canned_patterns) and len(text) < 200:
        print(f"[Webhook] Skipping canned agent response: {text[:60]}...")
        return {"ok": True, "skipped": True, "reason": "canned_response"}

    # App ID → Agent mapping for private chat routing
    APP_ID_TO_AGENT = {}
    try:
        ensure_mycompany_path()
        from mycompany.config.secrets import SecretsManager
        sm = SecretsManager()
        for key in sm.list():
            if key.endswith("_AGENT_APP_ID") and key.startswith("FEISHU_"):
                agent_name = key.replace("FEISHU_", "").replace("_AGENT_APP_ID", "").lower().replace("_", "-")
                app_id_val = sm.get(key)
                if app_id_val:
                    APP_ID_TO_AGENT[app_id_val] = f"{agent_name}-agent"
    except Exception as exc:
        from logging import getLogger
        getLogger(__name__).debug("APP_ID_TO_AGENT mapping load failed: %s", exc)

    # Strategy 1: Parse actual @mentions from Feishu event (most reliable)
    mentioned_agents = []
    try:
        message = body.get("event", {}).get("message", {})
        mentions = message.get("mentions", [])
        for mention in mentions:
            if mention.get("mentioned_type") == "bot":
                bot_name = mention.get("name", "").strip().lower()
                agent = BOT_NAME_MAPPING.get(bot_name, "")
                if not agent:
                    # Try hyphenated version
                    bot_hyphen = bot_name.replace(" ", "-").replace("_", "-")
                    agent = BOT_NAME_MAPPING.get(bot_hyphen, "")
                    if not agent and not bot_hyphen.endswith("-agent"):
                        agent = BOT_NAME_MAPPING.get(bot_hyphen + "-agent", "")
                if agent and agent not in mentioned_agents:
                    mentioned_agents.append(agent)
        if mentioned_agents:
            print(f"[Webhook] @mentions detected: {mentioned_agents}")
    except Exception as e:
        print(f"[Webhook] Failed to parse mentions: {e}")

    # Strategy 1.5: For p2p messages, route by app_id if no mentions
    if not mentioned_agents:
        chat_type = body.get("event", {}).get("message", {}).get("chat_type", "")
        app_id = body.get("event", {}).get("header", {}).get("app_id", body.get("header", {}).get("app_id", ""))
        if chat_type == "p2p" and app_id:
            agent_name = APP_ID_TO_AGENT.get(app_id, "")
            if agent_name:
                mentioned_agents.append(agent_name)
                print(f"[Webhook] P2P routed by app_id → {agent_name}")

    # Strategy 2: Fallback to keyword matching from text
    if not mentioned_agents:
        mention_mapping = {
            "software-agent": ["software", "软件", "代码", "coding"],
            "hardware-agent": ["hardware", "硬件", "电路", "pcb"],
            "test-agent": ["test", "测试", "验证", "检查"],
            "reviewer-agent": ["reviewer", "审核", "审查", "review"],
            "pm-agent": ["pm", "项目经理", "计划", "进度"],
            "ceo-agent": ["ceo", "战略", "决策", "风险"],
            "structure-agent": ["structure", "结构", "机械", "3d"],
            "it-ops-agent": ["it-ops", "运维", "系统", "监控"],
            "admin-agent": ["admin", "行政", "文档", "归档"],
            "hr-agent": ["hr", "人事", "团队", "资源"],
        }
        text_lower = text.lower()
        for agent, keywords in mention_mapping.items():
            for kw in keywords:
                if kw.lower() in text_lower or f"@{agent}" in text_lower:
                    mentioned_agents.append(agent)
                    break
        mentioned_agents = list(dict.fromkeys(mentioned_agents))

    import time as _t
    task_id = f"fs-{int(_t.time()*1000)}"
    chat_id = task.get("chat_id", "")
    user_id = task.get("user_id", "")
    chat_type = body.get("event", {}).get("message", {}).get("chat_type", "")
    meeting_id = None

    try:
        rd = get_redis()

        # ── Group session persistence ──
        group_session_id = None
        if chat_id:
            try:
                from vibebridge.conversation_store import create_conversation, add_message, list_conversations
                # Find existing group session for this chat
                existing = list_conversations(session_type="group", status="active")
                for sess in existing:
                    if sess.get("chat_id") == chat_id:
                        group_session_id = sess["id"]
                        break
                if not group_session_id:
                    group_session_id = create_conversation(
                        agent_name="group",
                        title=f"群聊 {chat_id[:20]}",
                        session_type="group",
                        chat_id=chat_id,
                        participants=mentioned_agents,
                    )
                    print(f"[Webhook] Created group session {group_session_id} for chat {chat_id}")
                # Record user message
                add_message(group_session_id, "user", text,
                            metadata={"user_id": user_id, "task_id": task_id, "mentioned_agents": mentioned_agents})
                # Cache session_id in Redis for outbox listener
                rd.setex(f"group_session:{chat_id}", 86400, group_session_id)
            except Exception as e:
                print(f"[Webhook] Group session creation failed: {e}")

        discussion_keywords = ["讨论","评审","review","开会","meeting","会议","复审","协调"]
        should_meeting = len(mentioned_agents) >= 3 and any(kw in text.lower() for kw in discussion_keywords)

        # ── CEO Orchestration: multi-agent or project-path messages go through CEO ──
        has_project_path = bool(re.search(r'/home/[\w\-/.]+|/workspace/[\w\-/.]+|/[\w\-]+/(?:Projects|src|demo)[\w\-/]*', text, re.I))
        should_orchestrate = (len(mentioned_agents) >= 2) or (len(mentioned_agents) >= 1 and has_project_path)

        if should_meeting:
            # Meeting mode — bypass Gateway (no session persistence for meetings)
            meeting_id = f"meeting-{task_id}"
            for agent in mentioned_agents:
                redis_task = {
                    "type": "task",
                    "meeting_id": meeting_id,
                    "task_id": f"{task_id}-{agent}",
                    "from": "feishu",
                    "to": agent,
                    "description": text,
                    "priority": 0,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "participants": mentioned_agents,
                    "is_meeting": True,
                    "timestamp": _t.time(),
                }
                rd.publish(f"task.{agent}", json.dumps(redis_task, ensure_ascii=False))
            rd.publish("meeting.coordinator", json.dumps({
                "type": "meeting_created",
                "meeting_id": meeting_id,
                "participants": mentioned_agents,
                "description": text,
                "chat_id": chat_id,
            }, ensure_ascii=False))
            print(f"[Webhook] Meeting {meeting_id} for {len(mentioned_agents)} agents")
        elif should_orchestrate and not should_meeting:
            # CEO orchestration mode — route ALL multi-agent / project-path messages through CEO
            target_agent = "ceo-agent"
            tid_agent = f"{task_id}-{target_agent}"
            ceo_description = text
            if mentioned_agents:
                ceo_description += f"\n\n【系统提示】用户已 @mention 以下 Agent：{', '.join(mentioned_agents)}。请按正确顺序协调它们完成工作。"
            is_p2p = (chat_type == "p2p")
            if is_p2p:
                routed = route_feishu_p2p(target_agent, ceo_description, chat_id, user_id, tid_agent)
            else:
                is_actual = is_actual_task(text, mentioned_agents)
                routed = route_feishu_group(target_agent, ceo_description, chat_id, user_id, tid_agent, is_actual)
            if routed:
                routed["task"]["mentioned_agents"] = mentioned_agents
                rd.publish(f"task.{target_agent}", json.dumps(routed["task"], ensure_ascii=False))
                print(f"[Webhook] CEO orchestration routed via Gateway session={routed.get('session_id','?')}")
            else:
                rd.publish(f"task.{target_agent}", json.dumps({
                    "type": "task", "task_id": tid_agent, "from": "feishu",
                    "to": target_agent, "description": ceo_description, "priority": 0,
                    "chat_id": chat_id, "user_id": user_id, "timestamp": _t.time(),
                    "mentioned_agents": mentioned_agents,
                }, ensure_ascii=False))
                print("[Webhook] CEO orchestration fallback dispatch")

            # Send immediate acknowledgment to Feishu
            if chat_id:
                try:
                    ack_msg = f"✅ CEO 正在协调 {len(mentioned_agents)} 个 Agent 处理您的请求，请稍候..."
                    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
                    token_data = json.dumps({
                        "app_id": os.environ.get("FEISHU_APP_ID",""),
                        "app_secret": os.environ.get("FEISHU_APP_SECRET","")
                    }).encode()
                    token_req = __import__("urllib.request").Request(token_url, data=token_data,
                        headers={"Content-Type":"application/json"}, method="POST")
                    with __import__("urllib.request").urlopen(token_req, timeout=5) as resp:
                        token = json.loads(resp.read().decode()).get("tenant_access_token","")
                    if token:
                        msg_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
                        msg_body = json.dumps({
                            "receive_id": chat_id,
                            "msg_type": "text",
                            "content": json.dumps({"text": ack_msg})
                        }).encode()
                        msg_req = __import__("urllib.request").Request(msg_url, data=msg_body,
                            headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"}, method="POST")
                        __import__("urllib.request").urlopen(msg_req, timeout=5)
                except Exception:
                    pass  # Ack is best-effort

            return {
                "ok": True, "source": "feishu", "parsed_text": text,
                "task_id": task_id, "status": "queued",
                "message": f"CEO 正在协调 {len(mentioned_agents)} 个 Agent 处理您的请求...",
                "agents": mentioned_agents,
            }
        elif len(mentioned_agents) >= 1:
            # Direct dispatch via Gateway (single agent, no project path)
            is_p2p = (chat_type == "p2p")
            for agent in mentioned_agents:
                tid_agent = f"{task_id}-{agent}"
                if is_p2p:
                    routed = route_feishu_p2p(agent, text, chat_id, user_id, tid_agent)
                else:
                    is_actual = is_actual_task(text, mentioned_agents)
                    routed = route_feishu_group(agent, text, chat_id, user_id, tid_agent, is_actual)
                if routed:
                    rd.publish(f"task.{agent}", json.dumps(routed["task"], ensure_ascii=False))
                    print(f"[Webhook] Gateway routed to {agent} session={routed.get('session_id','?')}")
                else:
                    # Notification mode — send canned task for acknowledgment
                    rd.publish(f"task.{agent}", json.dumps({
                        "type": "task", "task_id": tid_agent, "from": "feishu",
                        "to": agent, "description": text, "priority": 0,
                        "chat_id": chat_id, "user_id": user_id, "timestamp": _t.time(),
                    }, ensure_ascii=False))

            # Send immediate "收到" acknowledgment to Feishu
            if chat_id and mentioned_agents:
                try:
                    ack_msg = "✅ 收到，正在处理..."
                    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
                    token_data = json.dumps({
                        "app_id": os.environ.get("FEISHU_APP_ID",""),
                        "app_secret": os.environ.get("FEISHU_APP_SECRET","")
                    }).encode()
                    token_req = __import__("urllib.request").Request(token_url, data=token_data,
                        headers={"Content-Type":"application/json"}, method="POST")
                    with __import__("urllib.request").urlopen(token_req, timeout=5) as resp:
                        token = json.loads(resp.read().decode()).get("tenant_access_token","")
                    if token:
                        msg_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
                        msg_body = json.dumps({
                            "receive_id": chat_id,
                            "msg_type": "text",
                            "content": json.dumps({"text": ack_msg})
                        }).encode()
                        msg_req = __import__("urllib.request").Request(msg_url, data=msg_body,
                            headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"}, method="POST")
                        __import__("urllib.request").urlopen(msg_req, timeout=5)
                except Exception:
                    pass  # Ack is best-effort

            print(f"[Webhook] Direct dispatch to {len(mentioned_agents)} agents via Gateway")
        else:
            # Default route to CEO Agent (main agent)
            target_agent = "ceo-agent"
            tid_agent = f"{task_id}-{target_agent}"
            is_p2p = (chat_type == "p2p")
            if is_p2p:
                routed = route_feishu_p2p(target_agent, text, chat_id, user_id, tid_agent)
            else:
                routed = route_feishu_group(target_agent, text, chat_id, user_id, tid_agent, True)
            if routed:
                rd.publish(f"task.{target_agent}", json.dumps(routed["task"], ensure_ascii=False))
            else:
                rd.publish(f"task.{target_agent}", json.dumps({
                    "type": "task", "task_id": tid_agent, "from": "feishu",
                    "to": target_agent, "description": text, "priority": 0,
                    "chat_id": chat_id, "user_id": user_id, "timestamp": _t.time(),
                }, ensure_ascii=False))
            print(f"[Webhook] Default dispatch to {target_agent} (main agent)")

        # Build response
        if should_meeting and meeting_id:
            result = {
                "ok": True, "source": "feishu", "parsed_text": text,
                "task_id": meeting_id, "status": "queued",
                "message": f"📢 多Agent会议已创建，召集 {len(mentioned_agents)} 个Agent参与讨论...",
                "agents": mentioned_agents,
            }
        elif mentioned_agents:
            result = {
                "ok": True, "source": "feishu", "parsed_text": text,
                "task_id": task_id, "status": "queued",
                "message": f"任务已收到，正在分配给 {mentioned_agents[0]} 处理...",
                "agents": mentioned_agents[:1],
            }
        else:
            result = {
                "ok": True, "source": "feishu", "parsed_text": text,
                "task_id": task_id, "status": "queued",
                "message": "任务已收到，正在分配给 CEO-Agent 处理...",
            }
    except Exception as e:
        print(f"[Webhook] Failed to dispatch to Redis: {e}")
        import traceback
        traceback.print_exc()
        return {
            "ok": True, "source": "feishu", "parsed_text": text,
            "task": task, "error": str(e), "fallback": True,
        }

    return result


@router.post("/feishu/webhook/opencode")
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
