"""Provider router: resolves user messages to the correct provider."""

from __future__ import annotations

import asyncio

from .config import AgentsConfig
from .providers.base import BaseProvider


class ProviderRouter:
    def __init__(self, config: AgentsConfig, providers: dict[str, BaseProvider]):
        self.providers = providers
        self.prefix_map: dict[str, str] = {
            "/kimi": "kimi",
            "/claude": "claude",
            "/openc": "opencode",
            "/oc": "opencode",
            "/openclaw": "openclaw",
        }
        self.default = config.default_provider

    def resolve(self, text: str) -> tuple[BaseProvider, str]:
        """Return (provider, cleaned_prompt)."""
        for prefix, provider_name in self.prefix_map.items():
            if text.startswith(prefix + " ") or text == prefix:
                provider = self.providers.get(provider_name)
                if provider:
                    return provider, text[len(prefix):].strip()
        provider = self.providers.get(self.default)
        if provider is None:
            raise RuntimeError(f"Default provider '{self.default}' is not available")
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
