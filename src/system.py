"""
Multi-agent system manager.
Starts and coordinates all agents.
"""

import asyncio
import logging
from typing import Dict, Any, List

from src.agents.coordinator import CoordinatorAgent
from src.agents.opencode_agent import OpenCodeAgent
from src.agents.feishu_agent import FeishuAgent
from src.agents.memory_agent import MemoryAgent
from src.agents.llm_agent import LLMAgent
from src.agents.skill_agent import SkillAgent
from src.message_bus.bus import get_message_bus

logger = logging.getLogger(__name__)


class MultiAgentSystem:
    """Manages the multi-agent system."""

    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.message_bus = get_message_bus()
        self.running = False

        logger.info("[System] Starting multi-agent system...")

    async def start(self):
        """Start the multi-agent system."""
        if self.running:
            logger.warning("[System] System already running")
            return

        logger.info("[System] Creating agents...")

        # Create agents
        self.agents["coordinator"] = CoordinatorAgent()
        self.agents["opencode"] = OpenCodeAgent()
        self.agents["feishu"] = FeishuAgent()
        self.agents["memory"] = MemoryAgent()
        self.agents["llm"] = LLMAgent()
        self.agents["skill"] = SkillAgent()

        logger.info("[System] Starting agents...")

        # Start agents in order
        await self.agents["coordinator"].start()
        logger.info("[System] Started coordinator: Coordinator")

        await self.agents["opencode"].start()
        logger.info("[System] Started agent: OpenCode Agent")

        await self.agents["feishu"].start()
        logger.info("[System] Started agent: Feishu Agent")

        await self.agents["memory"].start()
        logger.info("[System] Started agent: Memory Agent")

        await self.agents["llm"].start()
        logger.info("[System] Started agent: LLM Agent")

        await self.agents["skill"].start()
        logger.info("[System] Started agent: Skill Agent")

        logger.info("[System] Registering agents with coordinator...")

        # Register agents with coordinator
        for agent_id, agent in self.agents.items():
            if agent_id == "coordinator":
                continue
            await agent.broadcast_capabilities()

        # Wait a moment for registration to complete
        await asyncio.sleep(0.5)

        self.running = True
        logger.info("[System] System started with 6 agents")
        logger.info("Multi-agent system started")

    async def stop(self):
        """Stop the multi-agent system."""
        if not self.running:
            return

        logger.info("[System] Stopping multi-agent system...")

        # Stop agents in reverse order
        for agent_id in reversed(list(self.agents.keys())):
            try:
                await self.agents[agent_id].stop()
                logger.info(f"[System] Stopped agent: {agent_id}")
            except Exception as e:
                logger.error(f"[System] Error stopping agent {agent_id}: {e}")

        self.agents.clear()
        self.running = False
        logger.info("[System] Multi-agent system stopped")

    def get_agent(self, agent_id: str):
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents with their status."""
        agents_list = []
        for agent_id, agent in self.agents.items():
            agents_list.append(
                {
                    "id": agent_id,
                    "name": agent.name,
                    "running": agent.is_running(),
                    "capabilities": [cap.name for cap in agent.get_capabilities()],
                }
            )
        return agents_list

    def is_running(self) -> bool:
        """Check if system is running."""
        return self.running


# Global instance
_system: MultiAgentSystem = None


async def start_multi_agent_system():
    """Start the multi-agent system (for use in FastAPI lifespan)."""
    global _system
    if _system is None:
        _system = MultiAgentSystem()
    await _system.start()
    return _system


async def stop_multi_agent_system():
    """Stop the multi-agent system."""
    global _system
    if _system is not None:
        await _system.stop()
        _system = None


def get_system() -> MultiAgentSystem:
    """Get the global multi-agent system instance."""
    global _system
    return _system
