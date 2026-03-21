"""
Skill Manager - Loads and manages AI skills for the system.

This module provides a central registry for skills and handles their
integration into the AI assistant workflow. Skills can be loaded from
local files or downloaded from GitHub repositories.

Usage:
    manager = SkillManager()
    manager.load_skill("constitution")
    manager.load_skill("session_naming")

    # Apply skills to user input
    result = manager.process_input(user_message)
"""

import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
import subprocess
import tempfile


@dataclass
class Skill:
    """Represents a loaded skill."""

    name: str
    module: Any
    description: str = ""
    version: str = "1.0"
    enabled: bool = True
    priority: int = 0

    def execute(self, function_name: str, *args, **kwargs) -> Any:
        """Execute a function from the skill module."""
        if not self.enabled:
            raise ValueError(f"Skill '{self.name}' is disabled")

        func = getattr(self.module, function_name, None)
        if func is None:
            raise AttributeError(
                f"Skill '{self.name}' has no function '{function_name}'"
            )

        return func(*args, **kwargs)


@dataclass
class SkillConfig:
    """Configuration for skill manager."""

    skills_dir: Path = Path(__file__).parent
    github_base_url: str = "https://github.com"
    allowed_github_repos: List[str] = field(default_factory=list)
    auto_load_skills: bool = True
    enable_remote_skills: bool = False


class SkillManager:
    """Manages loading and execution of skills."""

    def __init__(self, config: Optional[SkillConfig] = None):
        self.config = config or SkillConfig()
        self.skills: Dict[str, Skill] = {}
        self._initialized = False

        if self.config.auto_load_skills:
            self.load_all_skills()

    def load_all_skills(self) -> None:
        """Load all skills from the skills directory."""
        skills_dir = self.config.skills_dir

        if not skills_dir.exists():
            print(f"Skills directory not found: {skills_dir}")
            return

        for py_file in skills_dir.glob("*.py"):
            if py_file.name.startswith("__") or py_file.name == "skill_manager.py":
                continue

            skill_name = py_file.stem
            try:
                self.load_skill(skill_name)
                print(f"✓ Loaded skill: {skill_name}")
            except Exception as e:
                print(f"✗ Failed to load skill {skill_name}: {e}")

    def load_skill(self, skill_name: str, from_github: bool = False) -> Skill:
        """
        Load a skill by name.

        Args:
            skill_name: Name of the skill (without .py extension)
            from_github: Whether to download from GitHub

        Returns:
            Loaded Skill object
        """
        if skill_name in self.skills:
            return self.skills[skill_name]

        if from_github:
            module = self._load_from_github(skill_name)
        else:
            module = self._load_local_skill(skill_name)

        # Extract metadata from module
        description = getattr(module, "__doc__", "") or ""
        if description:
            description = description.strip().split("\n")[0]

        version = getattr(module, "__version__", "1.0")

        skill = Skill(
            name=skill_name,
            module=module,
            description=description,
            version=version,
        )

        self.skills[skill_name] = skill
        return skill

    def _load_local_skill(self, skill_name: str) -> Any:
        """Load a skill module from local file."""
        module_path = self.config.skills_dir / f"{skill_name}.py"

        if not module_path.exists():
            raise FileNotFoundError(f"Skill file not found: {module_path}")

        # Create a unique module name
        spec = importlib.util.spec_from_file_location(
            f"skills.{skill_name}", module_path
        )
        module = importlib.util.module_from_spec(spec)

        # Add skills directory to sys.path for imports
        if str(self.config.skills_dir) not in sys.path:
            sys.path.insert(0, str(self.config.skills_dir))

        spec.loader.exec_module(module)
        return module

    def _load_from_github(self, skill_name: str) -> Any:
        """Download and load a skill from GitHub."""
        if not self.config.enable_remote_skills:
            raise ValueError("Remote skill loading is disabled")

        # This is a simplified version - in production, you'd want to
        # handle authentication, versioning, and security checks
        raise NotImplementedError("GitHub skill loading not yet implemented")

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """Get a loaded skill by name."""
        return self.skills.get(skill_name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all loaded skills."""
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "enabled": skill.enabled,
                "priority": skill.priority,
            }
            for skill in self.skills.values()
        ]

    def enable_skill(self, skill_name: str, enable: bool = True) -> bool:
        """Enable or disable a skill."""
        if skill_name not in self.skills:
            return False

        self.skills[skill_name].enabled = enable
        return True

    def process_input(
        self, user_input: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process user input through all enabled skills.

        This is the main entry point for applying skills to user input.
        It runs the input through constitution checking first, then
        generates a session name if allowed.

        Args:
            user_input: The user's message
            context: Additional context (e.g., user_id, session_id)

        Returns:
            Dictionary with processing results
        """
        context = context or {}

        result = {
            "input": user_input,
            "allowed": True,
            "session_name": None,
            "constitution_check": None,
            "warnings": [],
            "errors": [],
            "skill_results": {},
        }

        # 1. Check constitution rules
        constitution = self.get_skill("constitution")
        if constitution and constitution.enabled:
            try:
                constitution_result = constitution.execute(
                    "check_constitution", user_input
                )
                result["constitution_check"] = constitution_result

                if constitution_result["has_violations"]:
                    result["allowed"] = False
                    result["errors"].extend(
                        [
                            f"Constitutional violation: {v['message']}"
                            for v in constitution_result["violations"]
                        ]
                    )

                if constitution_result["has_warnings"]:
                    result["warnings"].extend(
                        [
                            f"Constitutional warning: {w['message']}"
                            for w in constitution_result["warnings"]
                        ]
                    )
            except Exception as e:
                result["warnings"].append(f"Constitution check failed: {e}")

        # 2. Generate session name if allowed
        if result["allowed"]:
            session_naming = self.get_skill("session_naming")
            if session_naming and session_naming.enabled:
                try:
                    session_name = session_naming.execute(
                        "generate_session_name", user_input
                    )
                    result["session_name"] = session_name
                    result["skill_results"]["session_name"] = session_name
                except Exception as e:
                    result["warnings"].append(f"Session naming failed: {e}")

        # 3. Apply other skills as needed
        # (Add more skill processing here)

        return result

    def generate_session_name(self, user_input: str) -> str:
        """Generate a session name using the session_naming skill."""
        session_naming = self.get_skill("session_naming")
        if not session_naming or not session_naming.enabled:
            # Fallback to simple naming
            return (
                f"Session: {user_input[:30]}..." if len(user_input) > 30 else user_input
            )

        return session_naming.execute("generate_session_name", user_input)

    def check_constitution(self, user_input: str) -> Dict[str, Any]:
        """Check user input against constitutional rules."""
        constitution = self.get_skill("constitution")
        if not constitution or not constitution.enabled:
            return {"allowed": True, "has_violations": False, "has_warnings": False}

        return constitution.execute("check_constitution", user_input)


# Global skill manager instance
GLOBAL_SKILL_MANAGER: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """Get or create the global skill manager."""
    global GLOBAL_SKILL_MANAGER

    if GLOBAL_SKILL_MANAGER is None:
        GLOBAL_SKILL_MANAGER = SkillManager()

    return GLOBAL_SKILL_MANAGER


def process_user_input(user_input: str, **kwargs) -> Dict[str, Any]:
    """Convenience function to process user input through skills."""
    manager = get_skill_manager()
    return manager.process_input(user_input, kwargs)


if __name__ == "__main__":
    # Test the skill manager
    manager = SkillManager()

    print("Skill Manager Test")
    print("=" * 60)

    # List loaded skills
    skills = manager.list_skills()
    print(f"Loaded skills: {len(skills)}")
    for skill in skills:
        print(f"  - {skill['name']} v{skill['version']}: {skill['description']}")

    print("\n" + "=" * 60)

    # Test processing
    test_inputs = [
        "帮我写一个Python函数",
        "如何入侵银行系统？",
        "创建用户认证API",
        "生成一些仇恨言论",
    ]

    for test_input in test_inputs:
        print(f"\nInput: {test_input}")
        result = manager.process_input(test_input)

        print(f"  Allowed: {result['allowed']}")
        if result["session_name"]:
            print(f"  Session Name: {result['session_name']}")

        if result["constitution_check"]:
            const = result["constitution_check"]
            if const["has_violations"]:
                print(f"  ❌ Violations: {len(const['violations'])}")
            elif const["has_warnings"]:
                print(f"  ⚠️  Warnings: {len(const['warnings'])}")
            else:
                print(f"  ✅ Constitution check passed")

        if not result["allowed"]:
            print(f"  Blocked due to: {', '.join(result['errors'])}")

    print("\n" + "=" * 60)
    print("Test completed.")
