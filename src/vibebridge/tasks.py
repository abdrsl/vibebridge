"""Unified task orchestrator."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from .cards.error import render_error_card
from .cards.progress import render_progress_card
from .cards.result import render_result_card
from .cards.start import render_start_card
from .im.base import BaseIMAdapter, InboundMessage
from .providers.base import BaseProvider, StreamEventType
from .router import ProviderRouter
from .session import SessionManager


class ApprovalEngine:
    """Simple rule-based approval engine."""

    def __init__(self, config):
        self.config = config

    def evaluate(self, provider_name: str, prompt: str):
        class Risk:
            def __init__(self, level: str):
                self.level = level

        for rule in self.config.rules:
            if rule.provider != "*" and rule.provider != provider_name:
                continue
            if re.search(rule.pattern, prompt, re.IGNORECASE):
                return Risk(rule.level)
        return Risk(self.config.default_level)


class TaskOrchestrator:
    def __init__(
        self,
        router: ProviderRouter,
        im_adapter: BaseIMAdapter,
        session_manager: SessionManager,
        approval_engine: ApprovalEngine | None = None,
    ):
        self.router = router
        self.im = im_adapter
        self.sessions = session_manager
        self.approval = approval_engine
        self._active_cards: dict[str, str] = {}  # task_id -> message_id

    async def handle_message(self, message: InboundMessage) -> dict:
        """Main entry point for incoming IM messages."""
        try:
            provider, prompt = self.router.resolve(message.text)
        except RuntimeError as e:
            await self.im.send_text(message.chat_id, f"❌ {e}")
            return {"status": "error", "reason": str(e)}

        # Check provider health
        healthy, reason = await provider.health_check()
        if not healthy:
            await self.im.send_text(
                message.chat_id,
                f"⚠️ Provider '{provider.display_name}' is not healthy: {reason}",
            )
            return {"status": "error", "reason": reason}

        # Approval check
        if self.approval and self.approval.config.enabled:
            risk = self.approval.evaluate(provider.name, prompt)
            if risk.level in ("high", "critical"):
                await self.im.send_text(
                    message.chat_id,
                    f"⏸️ 该命令被标记为 **{risk.level}** 风险，已提交审批。"
                    f"请等待管理员在飞书中批准。\n\n命令: `{prompt[:200]}`",
                )
                return {
                    "status": "pending_approval",
                    "risk_level": risk.level,
                }

        # Session management
        session = self.sessions.get_or_create(
            user_id=message.sender_id,
            chat_id=message.chat_id,
            provider=provider.name,
            workdir=provider.default_workdir(),
        )
        session.add_message("user", prompt)
        self.sessions.save(session)

        # Create task
        task_id = await provider.create_task(
            prompt=prompt,
            workdir=session.workdir,
            session_id=session.session_id,
            chat_id=message.chat_id,
        )

        # Send start card
        start_card = render_start_card(task_id, provider.display_name, prompt)
        start_msg_id = await self._send_card(message.chat_id, start_card)
        if start_msg_id:
            self._active_cards[task_id] = start_msg_id

        # Run task in background so HTTP returns quickly
        asyncio.create_task(
            self._run_task_stream(message.chat_id, provider, task_id, session)
        )

        return {"status": "accepted", "task_id": task_id}

    async def _run_task_stream(
        self,
        chat_id: str,
        provider: BaseProvider,
        task_id: str,
        session,
    ) -> None:
        """Stream task events and update cards/messages."""
        progress_lines: list[str] = []
        final_files: list[str] = []

        try:
            async for event in provider.stream_task(task_id):
                if event.type == StreamEventType.STATUS:
                    progress_lines.append(event.content)
                elif event.type == StreamEventType.TOOL_USE:
                    progress_lines.append(event.content)
                elif event.type == StreamEventType.TEXT:
                    progress_lines.append(event.content)
                elif event.type == StreamEventType.ERROR:
                    progress_lines.append(f"❌ {event.content}")
                elif event.type == StreamEventType.DONE:
                    progress_lines.append(f"✅ {event.content}")

                # Update progress card every few events or on terminal events
                if event.type in (StreamEventType.STATUS, StreamEventType.TOOL_USE):
                    progress_text = "\n".join(progress_lines[-20:])
                    card = render_progress_card(
                        task_id, provider.display_name, progress_text
                    )
                    await self._update_card(chat_id, task_id, card)

            # Determine final result
            # For now, use the last few lines or done content
            result_text = "\n".join(progress_lines)
            if not result_text.strip():
                result_text = "任务执行完成，无文本输出。"

            # TODO: Detect generated files in workdir and upload them
            final_files = self._detect_new_files(session.workdir)

            result_card = render_result_card(
                task_id, provider.display_name, result_text, final_files
            )
            await self._update_card(chat_id, task_id, result_card)

            session.add_message("assistant", result_text)
            self.sessions.save(session)

            # Upload files if any
            for fpath in final_files:
                await self.im.upload_file(chat_id, fpath)

        except Exception as e:
            error_card = render_error_card(task_id, str(e))
            await self._update_card(chat_id, task_id, error_card)

    async def _send_card(self, chat_id: str, card: dict) -> str | None:
        """Send a card and return message_id if supported."""
        # For now, FeishuAdapter will handle this; we just pass through.
        # Return a dummy ID until FeishuAdapter supports real message IDs.
        await self.im.send_card(chat_id, "interactive", card)
        return f"msg_{id(card)}"

    async def _update_card(self, chat_id: str, task_id: str, card: dict) -> None:
        """Update an existing card or send a new one."""
        # TODO: Implement card update via update_to_message_id when FeishuAdapter supports it.
        await self.im.send_card(chat_id, "interactive", card)

    def _detect_new_files(self, workdir: str) -> list[str]:
        """Detect recently modified files in workdir (placeholder heuristic)."""
        # TODO: Implement proper file tracking by snapshotting before/after task.
        return []
