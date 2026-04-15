"""Kimi Code CLI provider implementation (ACP/MCP-based)."""

from __future__ import annotations

import shutil
from typing import AsyncIterator

import httpx

from .base import BaseProvider, StreamEvent, StreamEventType


class KimiProvider(BaseProvider):
    name = "kimi"
    display_name = "Kimi Code"

    def __init__(self, acp_url: str = "http://127.0.0.1:9876"):
        self.acp_url = acp_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=10.0)
        self._binary = shutil.which("kimi") or "kimi"

    async def health_check(self) -> tuple[bool, str]:
        # Step 1: Ensure kimi CLI is installed
        if not shutil.which("kimi"):
            return False, "Kimi CLI not found in PATH. Install: https://moonshotai.github.io/kimi-cli/"

        # Step 2: Try to reach ACP HTTP endpoint (best-effort)
        try:
            resp = await self._client.get(f"{self.acp_url}/health")
            if resp.status_code == 200:
                return True, "Kimi ACP ready"
            return (
                False,
                f"Kimi ACP returned HTTP {resp.status_code}. "
                f"If you started `kimi acp`, it may use a different port or transport.",
            )
        except Exception as e:
            return (
                False,
                f"Kimi CLI found, but ACP server not reachable at {self.acp_url}: {e}. "
                f"Try running `kimi acp` first and verify the endpoint.",
            )

    async def create_task(
        self,
        prompt: str,
        workdir: str,
        session_id: str,
        chat_id: str | None = None,
    ) -> str:
        task_id = f"kimi_{session_id}"
        return task_id

    async def stream_task(self, task_id: str) -> AsyncIterator[StreamEvent]:
        healthy, msg = await self.health_check()
        if not healthy:
            yield StreamEvent(
                type=StreamEventType.STATUS,
                content="Kimi provider is not ready.",
                task_id=task_id,
            )
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content=(
                    f"无法连接到 Kimi ACP 服务。\n"
                    f"诊断信息: {msg}\n\n"
                    f"排查步骤:\n"
                    f"1. 确认已安装 Kimi CLI: `kimi --version`\n"
                    f"2. 启动 ACP server: `kimi acp`\n"
                    f"3. 检查 ACP 端口是否匹配配置 (默认 {self.acp_url})\n"
                    f"4. 若 ACP 使用非 HTTP 传输 (如 Unix socket)，请在配置中指定正确地址"
                ),
                task_id=task_id,
            )
            return

        # If health check passed, we still need a real ACP/MCP implementation
        yield StreamEvent(
            type=StreamEventType.STATUS,
            content="Kimi ACP 连接正常，但执行层尚未完全实现。",
            task_id=task_id,
        )
        yield StreamEvent(
            type=StreamEventType.ERROR,
            content=(
                "Kimi execution via VibeBridge is under development. "
                "Please use `/openc` or `/openclaw` as a fallback for now."
            ),
            task_id=task_id,
        )

    async def cancel_task(self, task_id: str) -> bool:
        return True

    def default_workdir(self) -> str:
        from pathlib import Path

        return str(Path.home() / "workspace")
