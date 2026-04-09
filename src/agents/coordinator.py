import logging
from typing import Any, Dict, Optional

from src.agents.base import SystemAgent
from src.message_bus.bus import Message, MessageType

logger = logging.getLogger(__name__)


class CoordinatorAgent(SystemAgent):
    """Coordinator agent that manages other agents."""

    def __init__(self):
        super().__init__("coordinator", "Coordinator")
        self.memory_agent_id: Optional[str] = None
        self.llm_agent_id: Optional[str] = None

        # Subscribe to registration messages
        self.message_bus.subscribe(
            MessageType.REGISTER, self.handle_register, agent_id=self.agent_id
        )

        logger.info(f"[{self.agent_id}] Initializing Coordinator ({self.agent_id})")

    async def start(self):
        """Start the coordinator."""
        self._running = True
        logger.info(f"[{self.agent_id}] Coordinator started")

    async def stop(self):
        """Stop the coordinator."""
        self._running = False
        logger.info(f"[{self.agent_id}] Coordinator stopped")

    async def handle_register(self, message: Message):
        """Handle agent registration."""
        agent_id = message.payload.get("agent_id")
        agent_name = message.payload.get("agent_name")
        capabilities = message.payload.get("capabilities", [])

        if not agent_id or not agent_name:
            logger.warning(
                f"[{self.agent_id}] Invalid registration message: {message.payload}"
            )
            return

        # Register the agent
        await self.register_agent(agent_id, agent_name, capabilities)

        # Log registration
        logger.info(
            f"[{self.agent_id}] Registered agent {agent_name} ({agent_id}) "
            f"with {len(capabilities)} capabilities"
        )

        # Set memory and LLM agents if applicable
        if agent_name.lower() == "memory agent":
            self.memory_agent_id = agent_id
            logger.info(f"[{self.agent_id}] Memory agent set to {agent_id}")
        elif agent_name.lower() == "llm agent":
            self.llm_agent_id = agent_id
            logger.info(f"[{self.agent_id}] LLM agent set to {agent_id}")

    async def route_message(self, message: Message):
        """Route a message to appropriate agent (simplified)."""
        # For now, just log
        logger.debug(
            f"[{self.agent_id}] Routing message {message.message_type} "
            f"from {message.sender} to {message.recipient}"
        )

    def get_agent_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a registered agent."""
        return self.registered_agents.get(agent_id)

    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """List all registered agents."""
        return self.registered_agents.copy()

    def get_memory_agent(self) -> Optional[str]:
        """Get the memory agent ID."""
        return self.memory_agent_id

    def get_llm_agent(self) -> Optional[str]:
        """Get the LLM agent ID."""
        return self.llm_agent_id
