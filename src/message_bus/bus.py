import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Callable, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that can be sent between agents."""

    # System messages
    REGISTER = "register"
    REGISTRATION_CONFIRMED = "registration_confirmed"
    # Task messages
    TASK_CREATE = "task_create"
    TASK_RESULT = "task_result"
    TASK_PROGRESS = "task_progress"
    # Feishu messages
    SEND_CARD = "send_card"
    SEND_TEXT = "send_text"
    # LLM messages
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    # Memory messages
    STORE_MEMORY = "store_memory"
    RETRIEVE_MEMORY = "retrieve_memory"
    # Skill messages
    EXECUTE_SKILL = "execute_skill"
    SKILL_RESULT = "skill_result"
    # Custom messages
    CUSTOM = "custom"


@dataclass
class Message:
    """A message sent between agents."""

    message_type: MessageType
    sender: str  # Agent ID
    recipient: Optional[str] = None  # Specific recipient, None for broadcast
    payload: Dict[str, Any] = field(default_factory=dict)
    message_id: str = ""  # Unique ID, auto-generated if empty
    timestamp: float = 0.0  # Unix timestamp

    def __post_init__(self):
        import time

        if not self.message_id:
            self.message_id = f"msg_{int(time.time() * 1000)}_{id(self)}"
        if not self.timestamp:
            self.timestamp = time.time()


class MessageBus:
    """Simple message bus for agent communication."""

    def __init__(self):
        self._handlers: Dict[MessageType, List[Callable[[Message], Any]]] = {}
        self._agent_handlers: Dict[
            str, Dict[MessageType, List[Callable[[Message], Any]]]
        ] = {}
        self._registered_agents: Set[str] = set()
        logger.info("[MessageBus] Started")

    def register_agent(self, agent_id: str):
        """Register an agent with the message bus."""
        self._registered_agents.add(agent_id)
        logger.debug(f"[MessageBus] Registered agent {agent_id}")

    def unregister_agent(self, agent_id: str):
        """Unregister an agent."""
        self._registered_agents.discard(agent_id)
        if agent_id in self._agent_handlers:
            del self._agent_handlers[agent_id]
        logger.debug(f"[MessageBus] Unregistered agent {agent_id}")

    def subscribe(
        self,
        message_type: MessageType,
        handler: Callable[[Message], Any],
        agent_id: Optional[str] = None,
    ):
        """Subscribe to messages of a given type."""
        if agent_id:
            if agent_id not in self._agent_handlers:
                self._agent_handlers[agent_id] = {}
            if message_type not in self._agent_handlers[agent_id]:
                self._agent_handlers[agent_id][message_type] = []
            self._agent_handlers[agent_id][message_type].append(handler)
        else:
            if message_type not in self._handlers:
                self._handlers[message_type] = []
            self._handlers[message_type].append(handler)
        logger.debug(
            f"[MessageBus] Subscribed {agent_id or 'global'} to {message_type}"
        )

    async def publish(self, message: Message):
        """Publish a message to all subscribers."""
        logger.debug(
            f"[MessageBus] Publishing {message.message_type} from {message.sender} to {message.recipient or 'broadcast'}"
        )

        # First, send to specific recipient if specified
        if message.recipient and message.recipient in self._agent_handlers:
            handlers = self._agent_handlers[message.recipient].get(
                message.message_type, []
            )
            for handler in handlers:
                try:
                    result = handler(message)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(
                        f"[MessageBus] Error in agent handler {message.recipient}: {e}"
                    )

        # Then send to global handlers for this message type
        handlers = self._handlers.get(message.message_type, [])
        for handler in handlers:
            try:
                result = handler(message)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"[MessageBus] Error in global handler: {e}")

        # If no recipient specified, also send to all agents that subscribed to this message type
        if not message.recipient:
            for agent_id, agent_handlers in self._agent_handlers.items():
                handlers = agent_handlers.get(message.message_type, [])
                for handler in handlers:
                    try:
                        result = handler(message)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(
                            f"[MessageBus] Error in agent handler {agent_id}: {e}"
                        )

    def get_registered_agents(self) -> List[str]:
        """Get list of registered agent IDs."""
        return list(self._registered_agents)


# Global message bus instance
_message_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Get or create the global message bus instance."""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
    return _message_bus
