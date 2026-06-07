"""Provider router: resolves user messages to the correct provider."""

from __future__ import annotations

import asyncio

from .config import AgentsConfig
from .providers.base import BaseProvider


class ProviderRouter:
    # Commands that switch the session's default provider
    SWITCH_COMMANDS: dict[str, str] = {
        "claude": "claude",
        "opencode": "opencode",
        "kimicli": "kimi",
        "kimi": "kimi",
    }

    def __init__(self, config: AgentsConfig, providers: dict[str, BaseProvider]):
        self.providers = providers
        self.prefix_map: dict[str, str] = {
            "/kimi": "kimi",
            "/claude": "claude",
            "/openc": "opencode",
            "/oc": "opencode",
        }
        self.default = config.default_provider

    def is_switch_command(self, text: str) -> str | None:
        """Return provider name if text is a switch command, else None."""
        stripped = text.strip().lower()
        return self.SWITCH_COMMANDS.get(stripped)

    def resolve(self, text: str, session_provider: str | None = None) -> tuple[BaseProvider, str]:
        """Return (provider, cleaned_prompt)."""
        for prefix, provider_name in self.prefix_map.items():
            if text.startswith(prefix + " ") or text == prefix:
                provider = self.providers.get(provider_name)
                if provider:
                    return provider, text[len(prefix):].strip()
        # Fall back to session provider, then global default
        effective_default = session_provider or self.default
        provider = self.providers.get(effective_default)
        if provider is None:
            raise RuntimeError(f"Default provider '{effective_default}' is not available")
        return provider, text

    async def health_table(self) -> dict[str, tuple[bool, str]]:
        """Return health status for all registered providers."""
        results: dict[str, tuple[bool, str]] = {}
        for name, provider in self.providers.items():
            try:
                # Protect each provider's health check with a 10s timeout
                results[name] = await asyncio.wait_for(
                    provider.health_check(), timeout=10.0
                )
            except asyncio.TimeoutError:
                results[name] = (False, "Health check timed out after 10s")
            except Exception as e:
                results[name] = (False, str(e))
        return results
