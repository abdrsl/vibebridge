"""Agent Bridge — connects Feishu ↔ Agent system via Redis.

Design:
  1. Feishu webhook receives @mention → routes to task.{agent} channel
  2. Agent run_loop picks up task → executes → publishes result to outbox.{agent}
  3. This bridge subscribes outbox.* → forwards result back to Feishu
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ── Agent name mapping ──────────────────────────────────────────────
AGENT_ALIASES: dict[str, str] = {
    # Full names
    "software-agent": "software-agent",
    "hardware-agent": "hardware-agent",
    "pm-agent": "pm-agent",
    "test-agent": "test-agent",
    "reviewer-agent": "reviewer-agent",
    "it-ops-agent": "it-ops-agent",
    "ceo-agent": "ceo-agent",
    "structure-agent": "structure-agent",
    "admin-agent": "admin-agent",
    "hr-agent": "hr-agent",
    # Chinese aliases
    "软件": "software-agent",
    "硬件": "hardware-agent",
    "项目经理": "pm-agent",
    "测试": "test-agent",
    "审查": "reviewer-agent",
    "运维": "it-ops-agent",
    "ceo": "ceo-agent",
    "结构": "structure-agent",
    "行政": "admin-agent",
    "人事": "hr-agent",
    # Short aliases
    "sw": "software-agent",
    "hw": "hardware-agent",
    "pm": "pm-agent",
    "qa": "test-agent",
    "review": "reviewer-agent",
    "ops": "it-ops-agent",
    "struct": "structure-agent",
}


def resolve_agent(text: str) -> str | None:
    """Extract @mentioned agent name from text.

    Supports:
      @Software-Agent → software-agent
      @软件 → software-agent
      @pm-agent → pm-agent
    """
    import re
    # Match @Name patterns
    mentions = re.findall(r"@([\w\-\u4e00-\u9fff]+)", text)
    for m in mentions:
        key = m.lower().replace("-agent", "").replace("agent", "").strip()
        if key in AGENT_ALIASES:
            return AGENT_ALIASES[key]
        # Try full match
        full = m.lower().strip()
        if full in AGENT_ALIASES:
            return AGENT_ALIASES[full]
    return None


class AgentResultBridge:
    """Subscribes to Redis outbox.* and forwards agent results to Feishu."""

    def __init__(self, redis_client: Any = None, feishu_manager: Any = None, bot_manager: Any = None) -> None:
        self._redis = redis_client
        self._feishu = feishu_manager or bot_manager
        self._task: asyncio.Task[Any] | None = None
        self._running = False
        # Track bot_id per task so replies go to the correct bot
        self._task_bot_map: dict[str, str] = {}

    def start(self) -> None:
        """Start background listener in a dedicated thread."""
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._listen_loop())
            logger.info("AgentResultBridge started")
        except RuntimeError:
            self._thread = threading.Thread(target=self._thread_loop, daemon=True)
            self._thread.start()
            logger.info("AgentResultBridge started (thread mode)")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    def _thread_loop(self) -> None:
        """Synchronous thread wrapper for listening."""
        try:
            pubsub = self._redis.pubsub()
            pubsub.psubscribe("outbox.*")
            logger.info("AgentResultBridge subscribed to outbox.*")
            for msg in pubsub.listen():
                if not self._running:
                    break
                if msg and msg.get("type") == "pmessage":
                    try:
                        data = json.loads(msg["data"])
                        asyncio.run(self._forward_to_feishu(data))
                    except Exception as exc:
                        logger.error("Failed to forward agent result: %s", exc)
        except Exception as exc:
            logger.error("AgentResultBridge listener crashed: %s", exc)

    async def _listen_loop(self) -> None:
        """Async loop for listening to outbox.*."""
        try:
            pubsub = self._redis.pubsub()
            pubsub.psubscribe("outbox.*")
            logger.info("AgentResultBridge subscribed to outbox.*")
            while self._running:
                msg = pubsub.get_message(timeout=1.0)
                if msg and msg.get("type") == "pmessage":
                    try:
                        data = json.loads(msg["data"])
                        await self._forward_to_feishu(data)
                    except Exception as exc:
                        logger.error("Failed to forward agent result: %s", exc)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("AgentResultBridge listener crashed: %s", exc)

    async def _forward_to_feishu(self, result: dict[str, Any]) -> None:
        """Send agent result back to Feishu chat via the correct bot."""
        status = result.get("status", "")
        if status not in ("completed", "failed"):
            return

        agent = result.get("agent", "unknown")
        task_result = result.get("result", {})
        task_id = result.get("task_id", "")

        # Determine which bot and chat to use
        bot_id = self._task_bot_map.pop(task_id, "")
        chat_id = result.get("chat_id", "")
        if not chat_id and isinstance(task_result, dict):
            chat_id = task_result.get("chat_id", "")
        if not bot_id:
            bot_id = result.get("bot_id", "")

        summary = self._extract_summary(task_result, agent)
        summary = self._clean_summary(summary)

        if status == "failed":
            error = ""
            if isinstance(task_result, dict):
                error = task_result.get("error", "") or task_result.get("message", "")
            text = f"❌ **{agent}** 任务失败\n\n{error or summary}"
        else:
            text = f"✅ **{agent}** 任务完成\n\n{summary}"

        # 防级联保护：检查是否包含级联触发器
        if self._is_cascade_trigger(text):
            logger.warning("[AgentResultBridge] BLOCKED cascade trigger from %s: %s", agent, text[:80])
            return

        # 防重复保护：检查是否最近发送过类似内容
        if self._is_recent_duplicate(agent, text):
            logger.warning("[AgentResultBridge] BLOCKED duplicate from %s (recent similar send)", agent)
            return

        # 记录发送
        self._record_send(agent, text)

        if not chat_id:
            chat_id = self._get_default_chat_id(agent)

        if not chat_id:
            return

        try:
            if self._contains_markdown(text) and hasattr(self._feishu, "send_markdown"):
                await self._feishu.send_markdown(chat_id, text, bot_id=bot_id)
            elif hasattr(self._feishu, "send_text"):
                await self._feishu.send_text(chat_id, text, bot_id=bot_id)
            else:
                logger.info("[AgentResultBridge] Result from %s (chat=%s, bot=%s...): %s",
                            agent, chat_id[:12] if chat_id else "(no chat)", bot_id[:8] if bot_id else "default", text[:200])
        except Exception as exc:
            logger.error("Failed to send Feishu message: %s", exc)

    @staticmethod
    def _contains_markdown(text: str) -> bool:
        if not isinstance(text, str):
            return False
        markers = ("**", "*", "# ", "[", "`")
        return any(marker in text for marker in markers)

    _NOISE_PATTERNS = [
        "我来先查看项目现状。",
        "我来分析一下。",
        "让我看看。",
    ]

    _CASCADE_PATTERNS = [
        # 引发级联回复的关键词
        r"请.*自我介绍",
        r"请.*介绍.*自己",
        r"大家.*介绍",
        r"各位.*介绍",
        r"依次.*介绍",
        r"按顺序.*介绍",
        r"来做.*介绍",
        r"做一下.*介绍",
        r"@所有人.*请",
        r"@所有人.*介绍",
        r"@_all.*请",
        r"@_all.*介绍",
        r"请.*回复",
        r"请.*发言",
        r"请.*依次",
        r"请.*按顺序",
        r"接下来.*请",
        r"请各位.*",
        r"请大家.*",
        r"请各位.*介绍",
        r"请大家.*介绍",
        r"现在.*请.*介绍",
        r"接下来.*请.*介绍",
    ]

    # Agent级别的去重：记录最近发送的内容
    _agent_recent_sends: dict[str, tuple[float, str]] = {}
    _agent_duplicate_window_seconds: float = 300.0  # 5分钟内不重复发送类似内容
    _agent_duplicate_similarity_threshold: float = 0.7

    def _is_cascade_trigger(self, text: str) -> bool:
        """检查文本是否包含级联触发关键词"""
        import re
        text_lower = text.lower()
        for pattern in self._CASCADE_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _is_recent_duplicate(self, agent: str, text: str) -> bool:
        """检查Agent是否最近发送过类似内容"""
        import time
        import difflib
        
        if agent not in self._agent_recent_sends:
            return False
        
        last_time, last_text = self._agent_recent_sends[agent]
        if time.time() - last_time > self._agent_duplicate_window_seconds:
            return False
        
        # 计算相似度
        similarity = difflib.SequenceMatcher(None, last_text, text).ratio()
        return similarity > self._agent_duplicate_similarity_threshold

    def _record_send(self, agent: str, text: str) -> None:
        """记录Agent发送的内容"""
        import time
        self._agent_recent_sends[agent] = (time.time(), text)

    def _clean_summary(self, text: str) -> str:
        if not isinstance(text, str):
            text = str(text)
        for pattern in self._NOISE_PATTERNS:
            text = text.replace(pattern, "")
        # Deduplicate sentences
        sentences = [s.strip() for s in text.split("。") if s.strip()]
        seen: set[str] = set()
        unique: list[str] = []
        for s in sentences:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        text = "。".join(unique)
        # Truncate
        max_len = 2000
        if len(text) > max_len:
            text = text[:max_len] + "..."
        return text

    def _extract_summary(self, result: Any, agent_name: str = "") -> str:
        if isinstance(result, str):
            return result
        if not isinstance(result, dict):
            return ""
        for key in ("summary", "response", "result"):
            val = result.get(key)
            if val:
                return str(val)
        return ""

    def _get_default_chat_id(self, agent: str) -> str:
        """Resolve default chat_id from local Feishu bot configuration."""
        try:
            from vibebridge.config import get_config

            cfg = get_config()
            for bot in cfg.feishu.bots:
                if bot.agent == agent:
                    if bot.chat_id:
                        return bot.chat_id
                    if bot.p2p_chat_id:
                        return bot.p2p_chat_id
            # Fallback to ceo-agent config
            for bot in cfg.feishu.bots:
                if bot.agent == "ceo-agent":
                    if bot.p2p_chat_id:
                        return bot.p2p_chat_id
                    if bot.chat_id:
                        return bot.chat_id
        except Exception:
            pass
        return ""


class AgentTaskDispatcher:
    """Dispatches Feishu messages to Agent Redis channels."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def dispatch(self, text: str, chat_id: str, sender: str, message_id: str, bot_id: str = "") -> str | None:
        """Dispatch a Feishu message to the appropriate Agent.

        Returns:
            Agent name if dispatched, None if no agent matched.
        """
        agent = resolve_agent(text)
        if not agent:
            return None

        # Strip @mention from text for the agent
        import re
        clean_text = re.sub(r"@[\w\-\u4e00-\u9fff]+\s*", "", text).strip()

        task = {
            "type": "task",
            "task_id": f"feishu-{message_id}",
            "from": sender,
            "to": agent,
            "description": clean_text,
            "chat_id": chat_id,
            "message_id": message_id,
            "bot_id": bot_id,
            "source": "feishu",
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }

        channel = f"task.{agent}"
        try:
            self._redis.publish(channel, json.dumps(task, ensure_ascii=False))
            logger.info("Dispatched Feishu msg to %s (bot=%s...): %s", channel, bot_id[:8] if bot_id else "default", clean_text[:60])
            return agent
        except Exception as exc:
            logger.error("Failed to dispatch to %s: %s", channel, exc)
            return None

    async def dispatch_multi(self, text: str, chat_id: str, sender: str, message_id: str, bot_id: str = "") -> list[str]:
        """Dispatch a Feishu message to multiple matched agents.

        Returns:
            List of agent names dispatched.
        """
        from vibebridge.agent_config import resolve_all

        agents = resolve_all(text)
        dispatched: list[str] = []

        import re
        clean_text = re.sub(r"@[\w\-\u4e00-\u9fff]+\s*", "", text).strip()

        for agent in agents:
            task = {
                "type": "task",
                "task_id": f"feishu-{message_id}",
                "from": sender,
                "to": agent,
                "description": clean_text,
                "chat_id": chat_id,
                "message_id": message_id,
                "bot_id": bot_id,
                "source": "feishu",
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }

            try:
                self._redis.lpush(f"taskq.{agent}", json.dumps(task, ensure_ascii=False))
                dispatched.append(agent)
                logger.info("Dispatched Feishu msg to taskq.%s (bot=%s...): %s", agent, bot_id[:8] if bot_id else "default", clean_text[:60])
            except Exception as exc:
                logger.error("Failed to dispatch to taskq.%s: %s", agent, exc)

        return dispatched


# ── Auto Review Router ──────────────────────────────────────────────

class AutoReviewRouter:
    """Automatically routes agent outputs to reviewer-agent for quality checks.

    Subscribes to ``outbox.*`` and dispatches review tasks when:
      - software-agent generates code
      - hardware-agent produces a design
      - structure-agent produces a design
      - pm-agent produces a plan with subtasks
    """

    # Agent types whose outputs should be auto-reviewed
    REVIEWABLE_AGENTS = {
        "software-agent",
        "hardware-agent",
        "structure-agent",
        "pm-agent",
    }

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client
        self._task: asyncio.Task[Any] | None = None
        self._running = False
        # Deduplication set (in-memory, per session)
        self._reviewed_tasks: set[str] = set()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._listen_loop())
            logger.info("AutoReviewRouter started")
        except RuntimeError:
            pass

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _listen_loop(self) -> None:
        try:
            pubsub = self._redis.pubsub()
            pubsub.psubscribe("outbox.*")
            logger.info("AutoReviewRouter subscribed to outbox.*")
            while self._running:
                msg = pubsub.get_message(timeout=1.0)
                if msg and msg.get("type") == "pmessage":
                    try:
                        data = json.loads(msg["data"])
                        await self._maybe_dispatch_review(data)
                    except Exception as exc:
                        logger.error("AutoReviewRouter processing error: %s", exc)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("AutoReviewRouter listener crashed: %s", exc)

    async def _maybe_dispatch_review(self, result: dict[str, Any]) -> None:
        agent = result.get("agent", "")
        if agent not in self.REVIEWABLE_AGENTS:
            return

        task_id = result.get("task_id", "")
        if not task_id or task_id in self._reviewed_tasks:
            return

        status = result.get("status", "")
        if status != "completed":
            return

        # Build review task description
        task_result = result.get("result", {})
        description = self._build_review_description(agent, task_id, task_result)

        review_task = {
            "type": "task",
            "task_id": f"review-{task_id}",
            "from": "auto-review-router",
            "to": "reviewer-agent",
            "description": description,
            "original_agent": agent,
            "original_task_id": task_id,
            "original_task_type": result.get("task_type", "task"),
            "source": "auto-review",
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }

        try:
            self._redis.publish("task.reviewer-agent", json.dumps(review_task, ensure_ascii=False))
            self._reviewed_tasks.add(task_id)
            # Prevent unbounded growth
            if len(self._reviewed_tasks) > 1000:
                self._reviewed_tasks = set(list(self._reviewed_tasks)[-500:])
            logger.info("AutoReviewRouter dispatched review for %s task %s", agent, task_id)
        except Exception as exc:
            logger.error("AutoReviewRouter failed to dispatch review: %s", exc)

    def _build_review_description(self, agent: str, task_id: str, task_result: dict[str, Any]) -> str:
        parts = [f"请审查 **{agent}** 的任务结果（task_id: {task_id}）"]

        if agent == "software-agent":
            files = task_result.get("files_created", [])
            compiles = task_result.get("compile_results", [])
            parts.append(f"生成文件: {len(files)} 个")
            if compiles:
                ok = sum(1 for c in compiles if isinstance(c, dict) and c.get("status") == "ok")
                parts.append(f"编译通过: {ok}/{len(compiles)}")
            parts.append("请审查代码质量、安全性和可维护性。")

        elif agent == "hardware-agent":
            bom_count = task_result.get("bom_item_count", 0)
            summary = task_result.get("design_summary", "")
            parts.append(f"BOM 条目: {bom_count}")
            if summary:
                parts.append(f"设计摘要: {summary[:200]}")
            parts.append("请审查电路设计合理性和元器件选型。")

        elif agent == "structure-agent":
            mat_count = task_result.get("material_count", 0)
            summary = task_result.get("design_summary", "")
            parts.append(f"材料种类: {mat_count}")
            if summary:
                parts.append(f"设计摘要: {summary[:200]}")
            parts.append("请审查结构强度、材料选型和制造工艺可行性。")

        elif agent == "pm-agent":
            subtask_count = task_result.get("subtask_count", 0)
            parts.append(f"子任务数: {subtask_count}")
            parts.append("请审查任务分解合理性、依赖关系和工时估算。")

        return "\n".join(parts)
