"""Test for B1 fix: OpenRouter Provider prompt propagation.

Ensures that the prompt passed to create_task() is correctly used
in stream_task() instead of the hard-coded dummy string.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from vibebridge.providers.openrouter import OpenRouterProvider, StreamEventType


@pytest.fixture
def provider():
    return OpenRouterProvider(api_key="test-key", default_model="test/model")


@pytest.mark.asyncio
async def test_create_task_stores_prompt_in_context(provider):
    """B1: prompt must be stored in _task_contexts for later retrieval."""
    prompt = "Write a UART driver for STM32F4"
    task_id = await provider.create_task(
        prompt=prompt,
        workdir="/tmp/test",
        session_id="sess-001",
        chat_id="chat-001",
    )

    assert task_id in provider._task_contexts
    ctx = provider._task_contexts[task_id]
    assert ctx["prompt"] == prompt
    assert ctx["workdir"] == "/tmp/test"
    assert ctx["session_id"] == "sess-001"
    assert ctx["chat_id"] == "chat-001"


@pytest.mark.asyncio
async def test_stream_task_uses_stored_prompt(provider):
    """B1: stream_task must yield the original prompt, not the hard-coded fallback."""
    original_prompt = "Implement a circular buffer in C"
    task_id = await provider.create_task(
        prompt=original_prompt,
        workdir="/tmp/test",
        session_id="sess-002",
    )

    # Mock the HTTP stream to capture what prompt is sent
    mock_response = MagicMock()
    mock_response.aiter_bytes = AsyncMock(return_value=iter([]))
    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)
    provider._client = mock_client

    events = []
    async for event in provider.stream_task(task_id):
        events.append(event)

    # Verify the request was built with the original prompt
    call_args = mock_client.stream.call_args
    assert call_args is not None
    json_payload = call_args.kwargs.get("json") or call_args[1].get("json")
    messages = json_payload["messages"]
    assert messages[1]["content"] == original_prompt
    assert messages[1]["content"] != "Execute the user's request"


@pytest.mark.asyncio
async def test_stream_task_fallback_when_no_context(provider):
    """B1: stream_task should use fallback prompt when context is missing."""
    task_id = "openrouter_unknown_12345"

    mock_response = MagicMock()
    mock_response.aiter_bytes = AsyncMock(return_value=iter([]))
    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)
    provider._client = mock_client

    events = []
    async for event in provider.stream_task(task_id):
        events.append(event)

    call_args = mock_client.stream.call_args
    json_payload = call_args.kwargs.get("json") or call_args[1].get("json")
    messages = json_payload["messages"]
    # Fallback prompt should be used
    assert messages[1]["content"] == "Execute the user's request"


@pytest.mark.asyncio
async def test_task_context_cleaned_up_after_stream(provider):
    """B1: _task_contexts should be cleaned up after stream_task completes."""
    task_id = await provider.create_task(
        prompt="Test cleanup",
        workdir="/tmp",
        session_id="sess-003",
    )

    mock_response = MagicMock()
    mock_response.aiter_bytes = AsyncMock(return_value=iter([]))
    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)
    provider._client = mock_client

    async for _ in provider.stream_task(task_id):
        pass

    assert task_id not in provider._task_contexts
    assert task_id not in provider._tasks
