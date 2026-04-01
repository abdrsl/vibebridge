import logging
import subprocess

from src.agents.base import Agent, Capability
from src.message_bus.bus import Message, MessageType

logger = logging.getLogger(__name__)


class OpenCodeAgent(Agent):
    """OpenCode agent that executes OpenCode CLI tasks."""

    def __init__(self):
        super().__init__("opencode", "OpenCode Agent")

        # Add capabilities
        self.add_capability(
            Capability(
                name="execute_task",
                description="Execute OpenCode CLI tasks",
                metadata={"cli_version": self._get_opencode_version()},
            )
        )
        self.add_capability(
            Capability(
                name="stream_task",
                description="Stream real-time task output",
                metadata={},
            )
        )

        # Subscribe to task messages
        self.message_bus.subscribe(
            MessageType.TASK_CREATE, self.handle_task_create, agent_id=self.agent_id
        )

        logger.info(f"[{self.agent_id}] Initializing in {self._get_workspace_path()}")

    async def start(self):
        """Start the OpenCode agent."""
        self._running = True
        logger.info(f"[{self.agent_id}] OpenCode Agent started")

    async def stop(self):
        """Stop the OpenCode agent."""
        self._running = False
        logger.info(f"[{self.agent_id}] OpenCode Agent stopped")

    def _get_workspace_path(self) -> str:
        """Get the workspace path."""
        import os

        return os.getcwd()

    def _get_opencode_version(self) -> str:
        """Get OpenCode CLI version."""
        try:
            result = subprocess.run(
                ["opencode", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"[{self.agent_id}] OpenCode CLI available: {version}")
                return version
            else:
                logger.warning(
                    f"[{self.agent_id}] OpenCode CLI version check failed: {result.stderr}"
                )
                return "unknown"
        except FileNotFoundError:
            logger.error(f"[{self.agent_id}] OpenCode CLI not found in PATH")
            return "not_installed"
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error checking OpenCode version: {e}")
            return "error"

    async def handle_task_create(self, message: Message):
        """Handle task creation request."""
        task_description = message.payload.get("description", "")
        task_id = message.payload.get("task_id", "")
        chat_id = message.payload.get("chat_id", "")

        logger.info(f"[{self.agent_id}] Received task: {task_description[:50]}...")

        # For now, just log and send a dummy response
        # In real implementation, we would call opencode_manager.create_task()
        await self.send_message(
            MessageType.TASK_PROGRESS,
            recipient=message.sender,
            task_id=task_id,
            progress="starting",
            content="OpenCode task received",
        )

        # Simulate task execution
        await self._execute_opencode_task(task_description, task_id, chat_id)

    async def _execute_opencode_task(
        self, description: str, task_id: str, chat_id: str
    ):
        """Execute an OpenCode task (placeholder)."""
        try:
            # Import the actual opencode manager
            from src.legacy.opencode_integration import opencode_manager

            # Create task
            created_task_id = await opencode_manager.create_task(
                user_message=description, feishu_chat_id=chat_id
            )

            # Run task and stream events
            async for event in opencode_manager.run_opencode(created_task_id):
                event_type = event.get("type", "")
                content = event.get("content", "")

                # Send progress updates
                await self.send_message(
                    MessageType.TASK_PROGRESS,
                    recipient="coordinator",
                    task_id=task_id,
                    progress=event_type,
                    content=content[:500],
                )

                if event_type == "done":
                    # Send final result
                    await self.send_message(
                        MessageType.TASK_RESULT,
                        recipient="coordinator",
                        task_id=task_id,
                        success=True,
                        result=content,
                    )
                elif event_type == "error":
                    await self.send_message(
                        MessageType.TASK_RESULT,
                        recipient="coordinator",
                        task_id=task_id,
                        success=False,
                        error=content,
                    )

        except ImportError:
            logger.error(f"[{self.agent_id}] Could not import opencode_manager")
            await self.send_message(
                MessageType.TASK_RESULT,
                recipient="coordinator",
                task_id=task_id,
                success=False,
                error="OpenCode integration not available",
            )
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error executing OpenCode task: {e}")
            await self.send_message(
                MessageType.TASK_RESULT,
                recipient="coordinator",
                task_id=task_id,
                success=False,
                error=str(e),
            )
