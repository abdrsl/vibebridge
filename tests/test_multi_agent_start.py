#!/usr/bin/env python3
"""
Test script to verify multi-agent system starts correctly.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging to see debug messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


async def test_system_start():
    """Test that the multi-agent system starts and registers agents."""
    from src.system import MultiAgentSystem

    print("=== Testing Multi-Agent System ===")

    system = MultiAgentSystem()

    try:
        print("Starting system...")
        await system.start()

        # Wait a moment for registration
        await asyncio.sleep(1)

        # Check system status
        print(f"System running: {system.is_running()}")
        print(f"Number of agents: {len(system.agents)}")

        # List agents
        for agent_id, agent in system.agents.items():
            print(f"  - {agent_id}: {agent.name}, running={agent.is_running()}")

        # Check coordinator's registered agents
        coordinator = system.get_agent("coordinator")
        if coordinator:
            print(
                f"Coordinator registered agents: {len(coordinator.registered_agents)}"
            )
            for agent_id, info in coordinator.registered_agents.items():
                print(
                    f"  - {agent_id}: {info['name']} with {len(info['capabilities'])} capabilities"
                )

        # Verify we have 6 agents
        assert len(system.agents) == 6, f"Expected 6 agents, got {len(system.agents)}"

        # Verify all agents are running
        for agent_id, agent in system.agents.items():
            assert agent.is_running(), f"Agent {agent_id} is not running"

        print("✓ All agents started and registered successfully")

    finally:
        print("Stopping system...")
        await system.stop()
        print("System stopped")

    print("=== Test completed successfully ===")


if __name__ == "__main__":
    asyncio.run(test_system_start())
