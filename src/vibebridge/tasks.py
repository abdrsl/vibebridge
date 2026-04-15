"""Unified task orchestrator."""

from __future__ import annotations

import asyncio
import os
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
        self._task_timeout_seconds = 1800  # 30 minutes max per task
        self._running_tasks: set[asyncio.Task] = set()

    async def handle_message(self, message: InboundMessage) -> dict:
        """Main entry point for incoming IM messages."""
        try:
            provider, prompt = self.router.resolve(message.text)
        except RuntimeError as e:
            await self._safe_send_text(message.chat_id, f"❌ {e}")
            return {"status": "error", "reason": str(e)}

        # Check provider health
        try:
            healthy, reason = await provider.health_check()
        except Exception as e:
            await self._safe_send_text(
                message.chat_id,
                f"⚠️ Provider '{provider.display_name}' health check crashed: {e}",
            )
            return {"status": "error", "reason": str(e)}

        if not healthy:
            await self._safe_send_text(
                message.chat_id,
                f"⚠️ Provider '{provider.display_name}' is not healthy: {reason}",
            )
            return {"status": "error", "reason": reason}

        # Approval check
        if self.approval and self.approval.config.enabled:
            risk = self.approval.evaluate(provider.name, prompt)
            if risk.level in ("high", "critical"):
                await self._safe_send_text(
                    message.chat_id,
                    f"⏸️ 该命令被标记为 **{risk.level}** 风险，已提交审批。"
                    f"请等待管理员在飞书中批准。\n\n命令: `{prompt[:200]}`",
                )
                return {
                    "status": "pending_approval",
                    "risk_level": risk.level,
                }

        # Resolve workdir safely
        try:
            workdir = provider.default_workdir()
        except Exception as e:
            workdir = str(Path.home() / "workspace")
            print(f"[TaskOrchestrator] default_workdir failed, fallback to {workdir}: {e}")

        # Session management
        try:
            session = self.sessions.get_or_create(
                user_id=message.sender_id,
                chat_id=message.chat_id,
                provider=provider.name,
                workdir=workdir,
            )
            session.add_message("user", prompt)
            self.sessions.save(session)
        except Exception as e:
            await self._safe_send_text(
                message.chat_id, f"❌ Session error: {e}"
            )
            return {"status": "error", "reason": f"session error: {e}"}

        # Create task
        try:
            task_id = await provider.create_task(
                prompt=prompt,
                workdir=session.workdir,
                session_id=session.session_id,
                chat_id=message.chat_id,
            )
        except Exception as e:
            await self._safe_send_text(
                message.chat_id,
                f"❌ Failed to create task with {provider.display_name}: {e}",
            )
            return {"status": "error", "reason": f"create_task failed: {e}"}

        # Send start card
        try:
            start_card = render_start_card(task_id, provider.display_name, prompt)
            start_msg_id = await self._send_card(message.chat_id, start_card)
            if start_msg_id:
                self._active_cards[task_id] = start_msg_id
        except Exception as e:
            print(f"[TaskOrchestrator] Failed to send start card: {e}")

        # Run task in background so HTTP returns quickly
        task_coro = self._run_task_stream(message.chat_id, provider, task_id, session)
        task_handle = asyncio.create_task(task_coro)
        self._running_tasks.add(task_handle)
        task_handle.add_done_callback(self._running_tasks.discard)
        task_handle.add_done_callback(self._log_task_exception)

        return {"status": "accepted", "task_id": task_id}

    def _log_task_exception(self, task: asyncio.Task) -> None:
        """Log exceptions from background tasks to prevent 'never retrieved' warnings."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[TaskOrchestrator] Background task crashed: {e}")

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
            # Apply global task timeout
            await asyncio.wait_for(
                self._consume_stream(
                    chat_id, provider, task_id, session, progress_lines, final_files
                ),
                timeout=self._task_timeout_seconds,
            )
        except asyncio.TimeoutError:
            progress_lines.append(f"⏱️ 任务执行超过 {self._task_timeout_seconds} 秒，已强制终止。")
            try:
                await provider.cancel_task(task_id)
            except Exception:
                pass
            try:
                error_card = render_error_card(
                    task_id,
                    f"任务超时（>{self._task_timeout_seconds}s）。"
                    f"可能原因：模型响应过慢或陷入死循环。",
                )
                await self._update_card(chat_id, task_id, error_card)
            except Exception as e2:
                await self._safe_send_text(
                    chat_id,
                    f"❌ 任务超时且卡片发送失败: {e2}",
                )
        except Exception as e:
            print(f"[TaskOrchestrator] Unexpected error in task {task_id}: {e}")
            try:
                error_card = render_error_card(task_id, f"任务执行异常: {e}")
                await self._update_card(chat_id, task_id, error_card)
            except Exception as e2:
                await self._safe_send_text(
                    chat_id,
                    f"❌ 任务异常且卡片发送失败: {e2}",
                )

    async def _consume_stream(
        self,
        chat_id: str,
        provider: BaseProvider,
        task_id: str,
        session,
        progress_lines: list[str],
        final_files: list[str],
    ) -> None:
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
        except Exception as e:
            # If provider stream itself breaks, record it and re-raise so outer layer sends error card
            progress_lines.append(f"❌ 流式输出中断: {e}")
            raise

        # Determine final result
        result_text = "\n".join(progress_lines)
        if not result_text.strip():
            result_text = "任务执行完成，无文本输出。"

        # Detect generated files
        try:
            final_files = self._detect_new_files(session.workdir)
        except Exception as e:
            print(f"[TaskOrchestrator] file detection error: {e}")

        try:
            result_card = render_result_card(
                task_id, provider.display_name, result_text, final_files
            )
            await self._update_card(chat_id, task_id, result_card)
        except Exception as e:
            await self._safe_send_text(
                chat_id,
                f"✅ 任务完成（卡片发送失败，降级为文本）\n\n{result_text[:1500]}",
            )
            raise

        try:
            session.add_message("assistant", result_text)
            self.sessions.save(session)
        except Exception as e:
            print(f"[TaskOrchestrator] session save error: {e}")

        # Upload files if any
        for fpath in final_files:
            try:
                await self.im.upload_file(chat_id, fpath)
            except Exception as e:
                print(f"[TaskOrchestrator] upload_file error for {fpath}: {e}")
                # Notify user that file exists but upload failed
                await self._safe_send_text(
                    chat_id,
                    f"⚠️ 文件生成成功但上传失败：{fpath}\n错误：{e}",
                )

    async def _safe_send_text(self, chat_id: str, text: str) -> None:
        """Send text with exception swallowed to avoid cascading failures."""
        try:
            await self.im.send_text(chat_id, text)
        except Exception as e:
            print(f"[TaskOrchestrator] safe_send_text failed: {e}")

    async def _send_card(self, chat_id: str, card: dict) -> str | None:
        """Send a card and return message_id if supported."""
        try:
            await self.im.send_card(chat_id, "interactive", card)
            return f"msg_{id(card)}"
        except Exception as e:
            print(f"[TaskOrchestrator] _send_card failed: {e}")
            # Fallback to plain text summary
            header = "VibeBridge Message"
            try:
                header = card.get("header", {}).get("title", {}).get("content", header)
            except Exception:
                pass
            await self._safe_send_text(
                chat_id,
                f"[卡片发送失败，降级为文本] {header}",
            )
            return None

    async def _update_card(self, chat_id: str, task_id: str, card: dict) -> None:
        """Update an existing card or send a new one."""
        try:
            await self.im.send_card(chat_id, "interactive", card)
        except Exception as e:
            print(f"[TaskOrchestrator] _update_card failed: {e}")
            # Fallback to text so user is not left hanging
            header = "Update"
            text_body = ""
            try:
                header = card.get("header", {}).get("title", {}).get("content", header)
                elements = card.get("elements", [])
                for el in elements:
                    txt = el.get("text", {}).get("content", "")
                    if txt:
                        text_body = txt[:500]
                        break
            except Exception:
                pass
            await self._safe_send_text(
                chat_id,
                f"{header}\n{text_body}",
            )

    def _detect_new_files(self, workdir: str) -> list[str]:
        """Detect files modified in the last 5 minutes in workdir."""
        import time

        detected: list[str] = []
        wd = Path(workdir).expanduser()
        if not wd.exists():
            return detected

        now = time.time()
        cutoff = now - 300  # 5 minutes

        try:
            for path in wd.rglob("*"):
                if path.is_file() and path.stat().st_mtime > cutoff:
                    # Exclude common temp/cache files
                    if path.name.startswith("."):
                        continue
                    if path.suffix in (".tmp", ".log", ".pyc", ".pyo"):
                        continue
                    if "__pycache__" in str(path):
                        continue
                    detected.append(str(path.relative_to(wd)))
        except Exception as e:
            print(f"[TaskOrchestrator] _detect_new_files error: {e}")

        return detected[:20]  # cap at 20 files
