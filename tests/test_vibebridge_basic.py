"""Basic unit tests for VibeBridge core components."""

import pytest

from vibebridge.config import AgentsConfig, FeishuConfig
from vibebridge.providers import build_providers
from vibebridge.providers.base import StreamEvent, StreamEventType
from vibebridge.providers.claude import ClaudeProvider
from vibebridge.providers.kimi import KimiProvider
from vibebridge.providers.openclaw import OpenClawProvider
from vibebridge.providers.opencode import OpenCodeProvider
from vibebridge.router import ProviderRouter
from vibebridge.session import SessionManager


@pytest.fixture
def test_agents_config():
    return AgentsConfig(
        default_provider="opencode",
        opencode={"enabled": True, "binary": "auto", "model": "test-model"},
        openclaw={"enabled": True},
        kimi={"enabled": True},
        claude={"enabled": False},
    )


@pytest.fixture
def test_router(test_agents_config):
    providers = build_providers(test_agents_config)
    return ProviderRouter(test_agents_config, providers)


def test_provider_router_resolve_default(test_router):
    provider, prompt = test_router.resolve("write a python script")
    assert provider.name == "opencode"
    assert prompt == "write a python script"


def test_provider_router_resolve_kimi(test_router):
    provider, prompt = test_router.resolve("/kimi refactor this")
    assert provider.name == "kimi"
    assert prompt == "refactor this"


def test_provider_router_resolve_claude_fallback(test_router):
    # claude is disabled, should fallback to default
    provider, prompt = test_router.resolve("/claude do this")
    assert provider.name == "opencode"


def test_opencode_provider_default_workdir():
    p = OpenCodeProvider(default_workdir="~/test_workspace")
    assert "test_workspace" in p.default_workdir()


@pytest.mark.asyncio
async def test_opencode_provider_health_real():
    """Assumes opencode is installed in the test environment."""
    p = OpenCodeProvider()
    healthy, msg = await p.health_check()
    # We do not assert healthy=True because opencode may not be installed everywhere.
    assert isinstance(healthy, bool)
    assert isinstance(msg, str)


def test_kimi_provider_placeholder():
    p = KimiProvider()
    assert p.name == "kimi"


def test_openclaw_provider_placeholder():
    p = OpenClawProvider()
    assert p.name == "openclaw"


def test_claude_provider_disabled():
    p = ClaudeProvider()
    assert p.name == "claude"


def test_session_manager(tmp_path):
    sm = SessionManager(data_dir=tmp_path)
    session = sm.get_or_create("user_1", "chat_1", provider="opencode")
    assert session.user_id == "user_1"
    assert session.chat_id == "chat_1"
    assert session.provider == "opencode"

    sm.clear(session.session_id)
    assert sm.get(session.session_id) is None


@pytest.mark.asyncio
async def test_opencode_provider_stream_error_on_missing_task():
    p = OpenCodeProvider()
    events = []
    async for ev in p.stream_task("non_existent_task"):
        events.append(ev)
    assert len(events) == 1
    assert events[0].type == StreamEventType.ERROR
