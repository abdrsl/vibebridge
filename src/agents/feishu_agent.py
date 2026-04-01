import logging

from src.agents.base import Agent, Capability
from src.message_bus.bus import Message, MessageType

logger = logging.getLogger(__name__)


class FeishuAgent(Agent):
    """Feishu agent that handles Feishu API communication."""

    def __init__(self, app_id: str = ""):
        super().__init__("feishu", "Feishu Agent")

        self.app_id = app_id or self._get_app_id()

        # Add capabilities
        self.add_capability(
            Capability(
                name="send_card",
                description="Send interactive cards to Feishu",
                metadata={"api": "im/v1/messages"},
            )
        )
        self.add_capability(
            Capability(
                name="send_text",
                description="Send text messages to Feishu",
                metadata={"api": "im/v1/messages"},
            )
        )
        self.add_capability(
            Capability(
                name="get_access_token",
                description="Get Feishu access token",
                metadata={},
            )
        )
        self.add_capability(
            Capability(
                name="handle_webhook",
                description="Process Feishu webhook events",
                metadata={},
            )
        )

        # Subscribe to Feishu-related messages
        self.message_bus.subscribe(
            MessageType.SEND_CARD, self.handle_send_card, agent_id=self.agent_id
        )
        self.message_bus.subscribe(
            MessageType.SEND_TEXT, self.handle_send_text, agent_id=self.agent_id
        )

        logger.info(f"[{self.agent_id}] Initializing with App ID: {self.app_id}")

    async def start(self):
        """Start the Feishu agent."""
        self._running = True
        logger.info(f"[{self.agent_id}] Feishu client initialized")

    async def stop(self):
        """Stop the Feishu agent."""
        self._running = False
        logger.info(f"[{self.agent_id}] Feishu Agent stopped")

    def _get_app_id(self) -> str:
        """Get Feishu App ID from environment."""
        import os

        app_id = os.getenv("FEISHU_APP_ID", "")
        if not app_id:
            logger.warning(f"[{self.agent_id}] FEISHU_APP_ID not set")
            return "unknown"
        # Hide most of the app ID for security
        if len(app_id) > 8:
            return app_id[:4] + "..." + app_id[-4:]
        return app_id

    async def handle_send_card(self, message: Message):
        """Handle send card request."""
        chat_id = message.payload.get("chat_id")
        card_content = message.payload.get("card")
        message.payload.get("card_type", "interactive")

        if not chat_id or not card_content:
            logger.warning(
                f"[{self.agent_id}] Invalid send card request: {message.payload}"
            )
            return

        logger.info(f"[{self.agent_id}] Sending interactive card to {chat_id}")

        try:
            from src.legacy.feishu_client import feishu_client

            result = await feishu_client.send_interactive_card(chat_id, card_content)

            await self.send_message(
                MessageType.CUSTOM,
                recipient=message.sender,
                action="card_sent",
                result=result,
                chat_id=chat_id,
            )

        except ImportError:
            logger.error(f"[{self.agent_id}] Could not import feishu_client")
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error sending card: {e}")

    async def handle_send_text(self, message: Message):
        """Handle send text request."""
        chat_id = message.payload.get("chat_id")
        text = message.payload.get("text")

        if not chat_id or not text:
            logger.warning(
                f"[{self.agent_id}] Invalid send text request: {message.payload}"
            )
            return

        logger.info(f"[{self.agent_id}] Sending text to {chat_id}")

        try:
            from src.legacy.feishu_client import feishu_client

            result = await feishu_client.send_text_message(chat_id, text)

            await self.send_message(
                MessageType.CUSTOM,
                recipient=message.sender,
                action="text_sent",
                result=result,
                chat_id=chat_id,
            )

        except ImportError:
            logger.error(f"[{self.agent_id}] Could not import feishu_client")
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error sending text: {e}")

    async def get_access_token(self) -> str:
        """Get Feishu access token."""
        try:
            from src.legacy.feishu_client import feishu_client

            # The feishu_client might have a method to get token
            # If not, we can call the internal method
            logger.debug(
                f"[{self.agent_id}] Getting access token, app_id={self.app_id}"
            )
            # This is a placeholder - actual implementation depends on feishu_client
            return "token_placeholder"
        except ImportError:
            logger.error(f"[{self.agent_id}] Could not import feishu_client")
            return ""
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error getting access token: {e}")
            return ""
