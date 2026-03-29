import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.agents.base import Agent, Capability
from src.message_bus.bus import MessageType, Message

logger = logging.getLogger(__name__)


class MemoryAgent(Agent):
    """Memory agent that stores and retrieves memories."""

    def __init__(self, memory_file: Optional[str] = None):
        super().__init__("memory", "Memory Agent")

        # Determine memory file path
        if memory_file is None:
            project_dir = Path(__file__).parent.parent.parent
            self.memory_file = project_dir / "data" / "memory.json"
        else:
            self.memory_file = Path(memory_file)

        # Ensure directory exists
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing memories
        self.memories: List[Dict[str, Any]] = []
        self._load_memories()

        # Add capabilities
        self.add_capability(
            Capability(
                name="store_memory",
                description="Store a memory",
                metadata={"format": "json"},
            )
        )
        self.add_capability(
            Capability(
                name="retrieve_memory",
                description="Retrieve memories by query",
                metadata={},
            )
        )
        self.add_capability(
            Capability(
                name="search_memories",
                description="Search memories by keyword",
                metadata={},
            )
        )
        self.add_capability(
            Capability(
                name="clear_old_memories",
                description="Clear memories older than specified days",
                metadata={},
            )
        )

        # Subscribe to memory messages
        self.message_bus.subscribe(
            MessageType.STORE_MEMORY, self.handle_store_memory, agent_id=self.agent_id
        )
        self.message_bus.subscribe(
            MessageType.RETRIEVE_MEMORY,
            self.handle_retrieve_memory,
            agent_id=self.agent_id,
        )

        logger.info(f"[{self.agent_id}] Initializing, memory file: {self.memory_file}")

    async def start(self):
        """Start the memory agent."""
        self._running = True
        logger.info(f"[{self.agent_id}] Memory Agent started")

    async def stop(self):
        """Stop the memory agent."""
        # Save memories before stopping
        self._save_memories()
        self._running = False
        logger.info(f"[{self.agent_id}] Memory Agent stopped")

    def _load_memories(self):
        """Load memories from file."""
        try:
            if self.memory_file.exists():
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.memories = json.load(f)
                logger.info(f"[{self.agent_id}] Loaded {len(self.memories)} memories")
            else:
                self.memories = []
                logger.info(f"[{self.agent_id}] No existing memories found")
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error loading memories: {e}")
            self.memories = []

    def _save_memories(self):
        """Save memories to file."""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
            logger.debug(f"[{self.agent_id}] Saved {len(self.memories)} memories")
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error saving memories: {e}")

    async def handle_store_memory(self, message: Message):
        """Handle store memory request."""
        memory_data = message.payload.get("memory", {})
        memory_type = message.payload.get("type", "generic")
        tags = message.payload.get("tags", [])
        ttl = message.payload.get("ttl")  # Time to live in seconds

        if not memory_data:
            logger.warning(f"[{self.agent_id}] Empty memory data")
            return

        memory = {
            "id": f"mem_{datetime.now().timestamp()}",
            "type": memory_type,
            "data": memory_data,
            "tags": tags,
            "created_at": datetime.now().isoformat(),
            "source": message.sender,
        }

        if ttl:
            import time

            memory["expires_at"] = time.time() + ttl

        self.memories.append(memory)
        self._save_memories()

        logger.info(
            f"[{self.agent_id}] Stored memory {memory['id']} from {message.sender}"
        )

        # Send confirmation
        await self.send_message(
            MessageType.CUSTOM,
            recipient=message.sender,
            action="memory_stored",
            memory_id=memory["id"],
        )

    async def handle_retrieve_memory(self, message: Message):
        """Handle retrieve memory request."""
        query = message.payload.get("query", "")
        memory_type = message.payload.get("type")
        tags = message.payload.get("tags", [])
        limit = message.payload.get("limit", 10)

        # Filter memories
        filtered = self.memories

        # Filter by type
        if memory_type:
            filtered = [m for m in filtered if m.get("type") == memory_type]

        # Filter by tags
        if tags:
            filtered = [
                m for m in filtered if any(tag in m.get("tags", []) for tag in tags)
            ]

        # Filter by query in data (simple string search)
        if query:
            query_lower = query.lower()
            filtered = [
                m for m in filtered if self._memory_matches_query(m, query_lower)
            ]

        # Apply limit
        filtered = filtered[:limit]

        # Remove expired memories
        filtered = [m for m in filtered if not self._is_expired(m)]

        logger.info(
            f"[{self.agent_id}] Retrieved {len(filtered)} memories for query: {query}"
        )

        # Send results
        await self.send_message(
            MessageType.CUSTOM,
            recipient=message.sender,
            action="memories_retrieved",
            memories=filtered,
            count=len(filtered),
        )

    def _memory_matches_query(self, memory: Dict[str, Any], query: str) -> bool:
        """Check if memory matches query."""
        # Search in data (if it's a string)
        data = memory.get("data", {})
        if isinstance(data, str):
            return query in data.lower()
        elif isinstance(data, dict):
            # Convert dict to string for searching
            data_str = json.dumps(data).lower()
            return query in data_str
        return False

    def _is_expired(self, memory: Dict[str, Any]) -> bool:
        """Check if memory is expired."""
        expires_at = memory.get("expires_at")
        if expires_at:
            import time

            return time.time() > expires_at
        return False

    def search_memories(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories by query (synchronous)."""
        results = []
        query_lower = query.lower()

        for memory in self.memories:
            if self._memory_matches_query(memory, query_lower):
                results.append(memory)
                if len(results) >= limit:
                    break

        return results

    def store_memory_sync(
        self,
        memory_data: Dict[str, Any],
        memory_type: str = "generic",
        tags: Optional[List[str]] = None,
    ) -> str:
        """Store a memory synchronously."""
        memory = {
            "id": f"mem_{datetime.now().timestamp()}",
            "type": memory_type,
            "data": memory_data,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "source": "sync",
        }

        self.memories.append(memory)
        self._save_memories()

        return memory["id"]
