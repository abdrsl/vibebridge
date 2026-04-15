"""Provider registry and factory."""

from __future__ import annotations

from .base import BaseProvider
from .claude import ClaudeProvider
from .kimi import KimiProvider
from .openclaw import OpenClawProvider
from .opencode import OpenCodeProvider


__all__ = [
    "BaseProvider",
    "ClaudeProvider",
    "KimiProvider",
    "OpenClawProvider",
    "OpenCodeProvider",
    "build_providers",
]


def build_providers(config) -> dict[str, BaseProvider]:
    """Build provider instances from config."""
    from ..config import AgentsConfig

    assert isinstance(config, AgentsConfig)
    providers: dict[str, BaseProvider] = {}

    if config.opencode.enabled:
        providers["opencode"] = OpenCodeProvider(
            binary=None if config.opencode.binary == "auto" else config.opencode.binary,
            model=config.opencode.model,
            default_workdir=config.opencode.default_workdir,
        )

    if config.openclaw.enabled:
        providers["openclaw"] = OpenClawProvider(
            gateway_url=config.openclaw.gateway_url,
        )

    if config.kimi.enabled:
        providers["kimi"] = KimiProvider(
            acp_url=config.kimi.acp_url,
        )

    if config.claude.enabled:
        providers["claude"] = ClaudeProvider(
            binary=None if config.claude.binary == "auto" else config.claude.binary,
        )

    return providers
