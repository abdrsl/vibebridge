import abc
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.message_bus.bus import Message, MessageBus, MessageType, get_message_bus

logger = logging.getLogger(__name__)


@dataclass
class Capability:
    """Represents an agent capability."""

    name: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class Agent(abc.ABC):
    """Base class for all agents."""

    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.capabilities: List[Capability] = []
        self.message_bus: MessageBus = get_message_bus()
        self._running = False

        # Register with message bus
        self.message_bus.register_agent(agent_id)

        # Subscribe to registration confirmed message
        self.message_bus.subscribe(
            MessageType.REGISTRATION_CONFIRMED,
            self.handle_registration_confirmed,
            agent_id=self.agent_id,
        )

        logger.debug(f"[{self.agent_id}] Initialized")

    @abc.abstractmethod
    async def start(self):
        """Start the agent."""
        pass

    @abc.abstractmethod
    async def stop(self):
        """Stop the agent."""
        pass

    def add_capability(self, capability: Capability):
        """Add a capability to this agent."""
        self.capabilities.append(capability)
        logger.debug(f"[{self.agent_id}] Added capability: {capability.name}")

    def get_capabilities(self) -> List[Capability]:
        """Get all capabilities of this agent."""
        return self.capabilities.copy()

    async def handle_registration_confirmed(self, message: Message):
        """Handle registration confirmed message from coordinator."""
        logger.debug(f"[{self.agent_id}] Received registration confirmation")

    async def send_message(
        self, message_type: MessageType, recipient: Optional[str] = None, **payload
    ):
        """Send a message via the message bus."""
        message = Message(
            message_type=message_type,
            sender=self.agent_id,
            recipient=recipient,
            payload=payload,
        )
        await self.message_bus.publish(message)

    async def broadcast_capabilities(self):
        """Broadcast capabilities to coordinator (register)."""
        await self.send_message(
            MessageType.REGISTER,
            recipient="coordinator",
            agent_id=self.agent_id,
            agent_name=self.name,
            capabilities=[
                {
                    "name": cap.name,
                    "description": cap.description,
                    "metadata": cap.metadata,
                }
                for cap in self.capabilities
            ],
        )
        logger.info(f"[{self.agent_id}] Sent capabilities to coordinator")

    def is_running(self) -> bool:
        """Check if agent is running."""
        return self._running


class SystemAgent(Agent):
    """Base class for system-level agents (Coordinator)."""

    def __init__(self, agent_id: str, name: str):
        super().__init__(agent_id, name)
        self.registered_agents: Dict[str, Dict[str, Any]] = {}

    async def register_agent(
        self, agent_id: str, agent_name: str, capabilities: List[Dict[str, Any]]
    ):
        """Register an agent with the system."""
        self.registered_agents[agent_id] = {
            "name": agent_name,
            "capabilities": capabilities,
            "status": "registered",
        }
        logger.info(
            f"[{self.agent_id}] Registered agent {agent_name} ({agent_id}) with {len(capabilities)} capabilities"
        )

        # Send confirmation to the agent
        await self.send_message(
            MessageType.REGISTRATION_CONFIRMED,
            recipient=agent_id,
            agent_id=agent_id,
            coordinator_id=self.agent_id,
        )
