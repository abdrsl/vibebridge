import logging
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.agents.base import Agent, Capability
from src.message_bus.bus import MessageType, Message

logger = logging.getLogger(__name__)


class SkillAgent(Agent):
    """Skill agent that loads and executes skills."""

    def __init__(self, skills_dir: Optional[str] = None):
        super().__init__("skill", "Skill Agent")

        # Determine skills directory
        if skills_dir is None:
            project_dir = Path(__file__).parent.parent.parent
            self.skills_dir = project_dir / "skills"
        else:
            self.skills_dir = Path(skills_dir)

        # Loaded skills
        self.skills: Dict[str, Any] = {}
        self.skill_modules: Dict[str, Any] = {}

        # Add capabilities (dynamically added after loading skills)
        self.add_capability(
            Capability(
                name="execute_skill", description="Execute a loaded skill", metadata={}
            )
        )
        self.add_capability(
            Capability(
                name="list_skills", description="List all available skills", metadata={}
            )
        )
        self.add_capability(
            Capability(
                name="reload_skills",
                description="Reload skills from directory",
                metadata={},
            )
        )

        # Subscribe to skill messages
        self.message_bus.subscribe(
            MessageType.EXECUTE_SKILL, self.handle_execute_skill, agent_id=self.agent_id
        )

        logger.info(f"[{self.agent_id}] Initializing")

    async def start(self):
        """Start the skill agent."""
        self._running = True
        self._load_skills()
        logger.info(f"[{self.agent_id}] Skill Agent started")

    async def stop(self):
        """Stop the skill agent."""
        self._running = False
        logger.info(f"[{self.agent_id}] Skill Agent stopped")

    def _load_skills(self):
        """Load skills from the skills directory."""
        logger.info(f"[{self.agent_id}] Loading skills from: {self.skills_dir}")

        if not self.skills_dir.exists():
            logger.warning(
                f"[{self.agent_id}] Skills directory not found: {self.skills_dir}"
            )
            return

        # Load Python modules from skills directory
        try:
            # Add skills directory to Python path
            import sys

            sys.path.insert(0, str(self.skills_dir.parent))

            # Import the skills package
            import skills

            # Iterate through modules in skills package
            for _, module_name, is_pkg in pkgutil.iter_modules(skills.__path__):
                if not is_pkg:
                    try:
                        module = importlib.import_module(f"skills.{module_name}")
                        self.skill_modules[module_name] = module
                        logger.info(
                            f"[{self.agent_id}] Loaded skill module: {module_name}"
                        )

                        # Extract skill functions from module
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if callable(attr) and not attr_name.startswith("_"):
                                skill_key = f"{module_name}.{attr_name}"
                                self.skills[skill_key] = attr
                    except Exception as e:
                        logger.warning(
                            f"[{self.agent_id}] Failed to load module {module_name}: {e}"
                        )

            logger.info(f"[{self.agent_id}] Loaded {len(self.skills)} skills")

        except ImportError as e:
            logger.error(f"[{self.agent_id}] Could not import skills package: {e}")
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error loading skills: {e}")

    async def handle_execute_skill(self, message: Message):
        """Handle skill execution request."""
        skill_name = message.payload.get("skill_name")
        skill_args = message.payload.get("args", {})

        if not skill_name:
            logger.warning(f"[{self.agent_id}] No skill name provided")
            return

        logger.info(f"[{self.agent_id}] Executing skill: {skill_name}")

        # Find the skill
        skill_func = self.skills.get(skill_name)
        if not skill_func:
            logger.warning(f"[{self.agent_id}] Skill not found: {skill_name}")
            await self.send_message(
                MessageType.SKILL_RESULT,
                recipient=message.sender,
                skill_name=skill_name,
                success=False,
                error=f"Skill not found: {skill_name}",
            )
            return

        try:
            # Execute the skill
            result = skill_func(**skill_args)

            # If result is a coroutine, await it
            import asyncio

            if asyncio.iscoroutine(result):
                result = await result

            # Send result
            await self.send_message(
                MessageType.SKILL_RESULT,
                recipient=message.sender,
                skill_name=skill_name,
                success=True,
                result=result,
            )

            logger.info(f"[{self.agent_id}] Skill executed successfully: {skill_name}")

        except Exception as e:
            logger.error(f"[{self.agent_id}] Error executing skill {skill_name}: {e}")
            await self.send_message(
                MessageType.SKILL_RESULT,
                recipient=message.sender,
                skill_name=skill_name,
                success=False,
                error=str(e),
            )

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all loaded skills."""
        skills_list = []
        for skill_key, skill_func in self.skills.items():
            skills_list.append(
                {
                    "name": skill_key,
                    "module": skill_key.split(".")[0],
                    "function": skill_key.split(".")[1]
                    if "." in skill_key
                    else skill_key,
                    "description": skill_func.__doc__ or "No description",
                }
            )
        return skills_list

    def get_skill(self, skill_name: str) -> Any:
        """Get a skill function by name."""
        return self.skills.get(skill_name)

    async def reload_skills(self):
        """Reload skills from directory."""
        self.skills.clear()
        self.skill_modules.clear()
        self._load_skills()

        logger.info(
            f"[{self.agent_id}] Skills reloaded, now {len(self.skills)} skills available"
        )
