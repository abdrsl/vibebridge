"""OpenRouter provider for VibeBridge."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncIterator

import httpx

from .base import BaseProvider, StreamEvent, StreamEventType

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider using their API."""

    name = "openrouter"
    display_name = "OpenRouter"

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "openai/gpt-4o",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.default_model = default_model
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self._tasks: dict[str, asyncio.Task] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://vibebridge.ai",
                "X-Title": "VibeBridge",
            }
            self._client = httpx.AsyncClient(
                headers=headers, timeout=httpx.Timeout(300.0, connect=10.0)
            )
        return self._client

    async def health_check(self) -> tuple[bool, str]:
        """Check if OpenRouter API is accessible."""
        if not self.api_key:
            return False, "OpenRouter API key not configured"

        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/models")
            if response.status_code == 200:
                return True, "OpenRouter API is accessible"
            else:
                return False, f"OpenRouter API returned status {response.status_code}"
        except Exception as e:
            return False, f"OpenRouter API error: {str(e)}"

    async def create_task(
        self,
        prompt: str,
        workdir: str,
        session_id: str,
        chat_id: str | None = None,
    ) -> str:
        """Create a task and return task_id."""
        task_id = f"openrouter_{session_id}_{hash(prompt) & 0xFFFFFFFF}"
        
        # Start the task in background
        task = asyncio.create_task(self._execute_task(task_id, prompt, workdir))
        self._tasks[task_id] = task
        
        return task_id

    async def _execute_task(self, task_id: str, prompt: str, workdir: str):
        """Execute the task and store result."""
        try:
            # This is a placeholder - actual execution would happen in stream_task
            logger.info(f"OpenRouter task {task_id} created for prompt: {prompt[:100]}...")
        except Exception as e:
            logger.error(f"Error in OpenRouter task {task_id}: {e}")

    async def stream_task(self, task_id: str) -> AsyncIterator[StreamEvent]:
        """Stream task execution using OpenRouter API."""
        # Get the prompt from task context (in real implementation, we'd store it)
        # For now, we'll use a dummy prompt
        prompt = "Execute the user's request"
        
        try:
            client = await self._get_client()
            
            # Send initial status
            yield StreamEvent(
                type=StreamEventType.STATUS,
                content="Starting OpenRouter task...",
                task_id=task_id,
            )
            
            # Prepare the request
            messages = [
                {
                    "role": "system",
                    "content": "You are an AI assistant that helps with coding tasks. Provide clear, executable solutions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            data = {
                "model": self.default_model,
                "messages": messages,
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 4000,
            }
            
            # Make streaming request
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=data,
            ) as response:
                response.raise_for_status()
                
                buffer = ""
                async for chunk in response.aiter_bytes():
                    chunk_str = chunk.decode("utf-8")
                    lines = chunk_str.split("\n")
                    
                    for line in lines:
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                            
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data_obj = json.loads(data_str)
                                choices = data_obj.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        buffer += content
                                        # Yield text in chunks
                                        if len(buffer) > 100 or "\n" in content:
                                            yield StreamEvent(
                                                type=StreamEventType.TEXT,
                                                content=buffer,
                                                task_id=task_id,
                                            )
                                            buffer = ""
                            except json.JSONDecodeError:
                                continue
                
                # Yield any remaining buffer
                if buffer:
                    yield StreamEvent(
                        type=StreamEventType.TEXT,
                        content=buffer,
                        task_id=task_id,
                    )
                
                # Yield completion
                yield StreamEvent(
                    type=StreamEventType.DONE,
                    content="Task completed successfully",
                    task_id=task_id,
                )
                
        except Exception as e:
            logger.error(f"Error streaming OpenRouter task {task_id}: {e}")
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content=f"OpenRouter API error: {str(e)}",
                task_id=task_id,
            )
        finally:
            # Clean up task
            if task_id in self._tasks:
                del self._tasks[task_id]

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._tasks[task_id]
            return True
        return False

    def default_workdir(self) -> str:
        """Return the suggested default working directory."""
        return os.path.expanduser("~/workspace")

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def test_all_models(self) -> dict:
        """Test all available models on OpenRouter."""
        if not self.api_key:
            return {"error": "OpenRouter API key not configured"}
        
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/models")
            
            if response.status_code != 200:
                return {"error": f"Failed to fetch models: {response.status_code}"}
            
            models_data = response.json()
            models = models_data.get("data", [])
            
            results = {
                "total_models": len(models),
                "available_models": [],
                "test_results": {}
            }
            
            # Test a subset of popular models
            popular_models = [
                "openai/gpt-4o",
                "openai/gpt-4-turbo",
                "anthropic/claude-3.5-sonnet",
                "anthropic/claude-3-opus",
                "google/gemini-2.0-flash-exp",
                "meta-llama/llama-3.3-70b-instruct",
                "mistralai/mistral-large-2411",
                "deepseek/deepseek-chat",
                "deepseek/deepseek-reasoner",
                "qwen/qwen-2.5-72b-instruct",
            ]
            
            for model in popular_models:
                # Check if model is available
                model_available = any(m.get("id") == model for m in models)
                
                if model_available:
                    # Test the model with a simple prompt
                    test_result = await self._test_model(client, model)
                    results["test_results"][model] = test_result
                    results["available_models"].append(model)
                else:
                    results["test_results"][model] = {"available": False, "error": "Model not found"}
            
            return results
            
        except Exception as e:
            return {"error": f"Error testing models: {str(e)}"}

    async def _test_model(self, client: httpx.AsyncClient, model: str) -> dict:
        """Test a specific model with a simple prompt."""
        try:
            messages = [
                {
                    "role": "user",
                    "content": "Hello! Please respond with 'OK' if you can hear me."
                }
            ]
            
            data = {
                "model": model,
                "messages": messages,
                "max_tokens": 10,
                "temperature": 0.1,
            }
            
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=data,
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                return {
                    "available": True,
                    "response": content,
                    "tokens": result.get("usage", {}).get("total_tokens", 0)
                }
            else:
                return {
                    "available": False,
                    "error": f"API error: {response.status_code}",
                    "details": response.text[:200]
                }
                
        except Exception as e:
            return {
                "available": False,
                "error": f"Test failed: {str(e)}"
            }