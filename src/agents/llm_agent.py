import logging
import os
from typing import Any, Dict, Optional

from src.agents.base import Agent, Capability
from src.message_bus.bus import Message, MessageType

logger = logging.getLogger(__name__)


class LLMAgent(Agent):
    """LLM agent that provides language model services."""

    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None):
        super().__init__("llm", "LLM Agent")

        self.provider = provider or os.getenv("LLM_PROVIDER", "deepseek")
        self.api_key = api_key or self._get_api_key()

        # Add capabilities
        self.add_capability(
            Capability(
                name="generate_text",
                description="Generate text from prompt",
                metadata={"provider": self.provider},
            )
        )
        self.add_capability(
            Capability(
                name="chat_completion",
                description="Chat completion",
                metadata={"provider": self.provider},
            )
        )
        self.add_capability(
            Capability(
                name="embeddings",
                description="Generate embeddings",
                metadata={"provider": self.provider},
            )
        )
        self.add_capability(
            Capability(
                name="model_info", description="Get model information", metadata={}
            )
        )

        # Subscribe to LLM messages
        self.message_bus.subscribe(
            MessageType.LLM_REQUEST, self.handle_llm_request, agent_id=self.agent_id
        )

        logger.info(f"[{self.agent_id}] Initializing with provider: {self.provider}")

    async def start(self):
        """Start the LLM agent."""
        self._running = True
        logger.info(f"[{self.agent_id}] LLM Agent started")

    async def stop(self):
        """Stop the LLM agent."""
        self._running = False
        logger.info(f"[{self.agent_id}] LLM Agent stopped")

    def _get_api_key(self) -> str:
        """Get API key from environment."""
        # Try DeepSeek first
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if api_key:
            # Hide most of the key for security
            if len(api_key) > 8:
                hidden = api_key[:4] + "..." + api_key[-4:]
                logger.info(f"[{self.agent_id}] API key available: {hidden}")
            else:
                logger.info(f"[{self.agent_id}] API key available")
            return api_key

        logger.warning(
            f"[{self.agent_id}] No API key found for provider {self.provider}"
        )
        return ""

    async def handle_llm_request(self, message: Message):
        """Handle LLM request."""
        prompt = message.payload.get("prompt", "")
        message.payload.get("model", "")
        message.payload.get("temperature", 0.7)
        message.payload.get("max_tokens", 1000)

        if not prompt:
            logger.warning(f"[{self.agent_id}] Empty prompt")
            return

        logger.info(f"[{self.agent_id}] Processing LLM request, length: {len(prompt)}")

        try:
            # Try to use existing llm module
            from src.legacy.llm import ask_deepseek_for_design_advice

            # Call the LLM function
            response = ask_deepseek_for_design_advice(prompt)

            # Send response
            await self.send_message(
                MessageType.LLM_RESPONSE,
                recipient=message.sender,
                request_id=message.payload.get("request_id"),
                response=response,
                model=self.provider,
                tokens_used=len(response.split()),  # rough estimate
            )

            logger.debug(f"[{self.agent_id}] LLM response sent")

        except ImportError:
            # Fallback to direct API call
            await self._call_direct_api(prompt, message)
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error calling LLM: {e}")
            await self.send_message(
                MessageType.LLM_RESPONSE,
                recipient=message.sender,
                request_id=message.payload.get("request_id"),
                error=str(e),
                model=self.provider,
            )

    async def _call_direct_api(self, prompt: str, message: Message):
        """Call LLM API directly (fallback)."""
        try:
            import httpx

            if self.provider.lower() == "deepseek":
                url = "https://api.deepseek.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                data = {
                    "model": "deepseek-reasoner",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": message.payload.get("temperature", 0.7),
                    "max_tokens": message.payload.get("max_tokens", 1000),
                }

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=data, headers=headers)
                    response.raise_for_status()
                    result = response.json()

                    content = result["choices"][0]["message"]["content"]

                    await self.send_message(
                        MessageType.LLM_RESPONSE,
                        recipient=message.sender,
                        request_id=message.payload.get("request_id"),
                        response=content,
                        model="deepseek-reasoner",
                        tokens_used=result.get("usage", {}).get("total_tokens", 0),
                    )
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

        except Exception as e:
            logger.error(f"[{self.agent_id}] Error in direct API call: {e}")
            await self.send_message(
                MessageType.LLM_RESPONSE,
                recipient=message.sender,
                request_id=message.payload.get("request_id"),
                error=str(e),
                model=self.provider,
            )

    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt (synchronous wrapper)."""
        # This is a synchronous method that could be used directly
        # For now, just return placeholder
        return f"LLM response to: {prompt[:50]}..."

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            "provider": self.provider,
            "api_key_available": bool(self.api_key),
            "capabilities": ["text_generation", "chat_completion"],
        }
