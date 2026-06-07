"""Streaming card lifecycle for Feishu interactive messages."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class TimelineEntry:
    event_type: str
    message: str


@dataclass
class _CardState:
    status: str
    agent_name: str
    percent: float
    last_update: float
    message_id: str
    chat_id: str
    task_id: str


def _build_thinking_card(
    agent_name: str, thought: str, task_id: str = "", step_info: str = ""
) -> dict:
    elements = []
    if thought:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": thought}})
    if step_info:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": step_info}})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"🤖 {agent_name} 正在思考"},
            "template": "blue",
        },
        "elements": elements,
    }


def _build_progress_card(
    agent_name: str,
    percent: float,
    step: str,
    detail: str = "",
    elapsed: float = 0.0,
    timeline: list[TimelineEntry] | None = None,
) -> dict:
    template = "wathet" if percent < 100 else "green"
    elements = []
    if step:
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**步骤:** {step}"}}
        )
    if detail:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": detail}})
    if elapsed:
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**已用时:** {elapsed:.1f}s"},
            }
        )
    if timeline:
        for entry in timeline:
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"• {entry.event_type}: {entry.message}",
                    },
                }
            )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"⏳ {agent_name} {percent:.0f}% 执行中",
            },
            "template": template,
        },
        "elements": elements,
    }


def _build_result_card(
    agent_name: str,
    status: str,
    summary: str,
    result: str = "",
    task_id: str = "",
    elapsed: float = 0.0,
    timeline: list[TimelineEntry] | None = None,
) -> dict:
    template = "green" if status == "completed" else "red"
    icon = "✅" if status == "completed" else "❌"
    elements = []
    if summary:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": summary}})
    if result:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": result}})
    if elapsed:
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**用时:** {elapsed:.1f}s"},
            }
        )
    if timeline:
        for entry in timeline:
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"• {entry.event_type}: {entry.message}",
                    },
                }
            )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{icon} {agent_name} 任务结果"},
            "template": template,
        },
        "elements": elements,
    }


class StreamingCardManager:
    def __init__(self, feishu_client):
        self._feishu = feishu_client
        self._states: dict[str, _CardState] = {}
        self._update_interval: float = 1.0

    def set_update_interval(self, seconds: float) -> None:
        self._update_interval = seconds

    def start_task(
        self, chat_id: str, agent_name: str, task_id: str, thought: str = ""
    ) -> str | None:
        card = _build_thinking_card(agent_name, thought, task_id)
        ok, msg_id = self._feishu.send_card_with_id(chat_id, card)
        if not ok:
            return None
        card_id = f"{chat_id}:{task_id}"
        self._states[card_id] = _CardState(
            status="thinking",
            agent_name=agent_name,
            percent=0.0,
            last_update=time.time(),
            message_id=msg_id,
            chat_id=chat_id,
            task_id=task_id,
        )
        return card_id

    def update_progress(
        self, card_id: str, percent: float, step: str, detail: str = ""
    ) -> bool:
        state = self._states.get(card_id)
        if not state or not self._throttle(state):
            return False
        state.status = "progress"
        state.percent = percent
        card = _build_progress_card(
            agent_name=state.agent_name,
            percent=percent,
            step=step,
            detail=detail,
        )
        try:
            return self._feishu.update_card(state.message_id, card)
        except Exception:
            return False

    def update_tool_call(self, card_id: str, tool_name: str, tool_args: str) -> bool:
        state = self._states.get(card_id)
        if not state or not self._throttle(state):
            return False
        state.status = "tool_call"
        detail = f"**调用工具:** `{tool_name}`\n```\n{tool_args}\n```"
        card = _build_progress_card(
            agent_name=state.agent_name,
            percent=state.percent,
            step=tool_name,
            detail=detail,
        )
        try:
            return self._feishu.update_card(state.message_id, card)
        except Exception:
            return False

    def finish_task(
        self, card_id: str, status: str, summary: str, result: str = ""
    ) -> bool:
        state = self._states.get(card_id)
        if not state:
            return False
        card = _build_result_card(
            agent_name=state.agent_name,
            status=status,
            summary=summary,
            result=result,
        )
        try:
            ok = self._feishu.update_card(state.message_id, card)
        except Exception:
            ok = False
        self._states.pop(card_id, None)
        return bool(ok)

    def cancel_task(self, card_id: str, reason: str = "") -> bool:
        state = self._states.get(card_id)
        if not state:
            return False
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "⛔ 任务已取消"},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": reason or "任务已被取消"},
                }
            ],
        }
        try:
            self._feishu.update_card(state.message_id, card)
        except Exception:
            pass
        self._states.pop(card_id, None)
        return True

    def get_state(self, card_id: str):
        return self._states.get(card_id)

    def _throttle(self, state: _CardState) -> bool:
        now = time.time()
        if now - state.last_update < self._update_interval:
            return False
        state.last_update = now
        return True
