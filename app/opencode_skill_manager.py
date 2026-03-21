"""
OpenCode Skill Manager - Loads and executes OpenCode/Claude-style skills from workspace/.skills/

Skills are directories containing:
- SKILLS.md: Documentation and metadata
- run.sh: Main entry point script (executable)
- Supporting scripts (e.g., .py files)
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import logging

logger = logging.getLogger(__name__)

# Path to workspace skills directory (workspace/.skills/)
WORKSPACE_ROOT = Path("/home/user/workspace")
SKILLS_DIR = WORKSPACE_ROOT / ".skills"


@dataclass
class OpenCodeSkill:
    """Represents an OpenCode-style skill."""

    name: str
    directory: Path
    metadata: Dict[str, Any] = field(default_factory=dict)
    run_script: Optional[Path] = None

    def execute(self, args: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute the skill with given arguments.

        Args:
            args: Dictionary of argument name -> value

        Returns:
            Dictionary with keys: success, output, error, return_code
        """
        if not self.run_script or not self.run_script.exists():
            return {
                "success": False,
                "error": f"Run script not found: {self.run_script}",
                "output": "",
                "return_code": -1,
            }

        # Build command line arguments
        cmd_args = [str(self.run_script)]
        for arg_name, arg_value in args.items():
            if arg_value is not None:
                cmd_args.append(f"--{arg_name}")
                cmd_args.append(str(arg_value))

        try:
            logger.info(f"Executing skill {self.name}: {' '.join(cmd_args)}")
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                cwd=self.directory,
                timeout=30,  # 30 second timeout per skill
            )

            output = result.stdout.strip()
            error = result.stderr.strip()

            # Try to parse JSON output if possible
            parsed_output = None
            if output:
                try:
                    parsed_output = json.loads(output)
                except json.JSONDecodeError:
                    parsed_output = output

            return {
                "success": result.returncode == 0,
                "output": parsed_output if parsed_output is not None else output,
                "error": error,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Skill execution timed out after 30 seconds",
                "output": "",
                "return_code": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Skill execution failed: {str(e)}",
                "output": "",
                "return_code": -1,
            }


class OpenCodeSkillManager:
    """Manages OpenCode-style skills from workspace/.skills/"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.skills: Dict[str, OpenCodeSkill] = {}
        self._load_skills()

    def _load_skills(self) -> None:
        """Load all skills from the skills directory."""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_name = skill_dir.name
                try:
                    skill = self._load_skill(skill_dir)
                    self.skills[skill_name] = skill
                    logger.info(f"Loaded skill: {skill_name}")
                except Exception as e:
                    logger.warning(f"Failed to load skill {skill_name}: {e}")

    def _load_skill(self, skill_dir: Path) -> OpenCodeSkill:
        """Load a single skill from directory."""
        skill_name = skill_dir.name

        # Look for SKILLS.md
        skills_md = skill_dir / "SKILLS.md"
        metadata = {}
        if skills_md.exists():
            metadata = self._parse_skills_md(skills_md)

        # Look for run.sh (preferred) or any executable script
        run_script = skill_dir / "run.sh"
        if not run_script.exists():
            # Look for other potential entry points
            for script in skill_dir.glob("*.sh"):
                if script.name != "run.sh" and os.access(script, os.X_OK):
                    run_script = script
                    break
            else:
                # No executable shell script found
                run_script = None

        return OpenCodeSkill(
            name=skill_name,
            directory=skill_dir,
            metadata=metadata,
            run_script=run_script,
        )

    def _parse_skills_md(self, md_path: Path) -> Dict[str, Any]:
        """Parse SKILLS.md file to extract metadata."""
        content = md_path.read_text(encoding="utf-8", errors="ignore")

        metadata = {
            "purpose": "",
            "when_to_use": [],
            "inputs": [],
            "examples": [],
        }

        current_section = None
        for line in content.splitlines():
            line = line.strip()

            # Detect section headers
            if line.startswith("## "):
                section = line[3:].lower()
                if "purpose" in section:
                    current_section = "purpose"
                elif "when to use" in section:
                    current_section = "when_to_use"
                elif "inputs" in section:
                    current_section = "inputs"
                elif "examples" in section:
                    current_section = "examples"
                else:
                    current_section = None
            elif current_section == "purpose" and line and not line.startswith("#"):
                metadata["purpose"] = line
            elif current_section == "when_to_use" and line.startswith("- "):
                metadata["when_to_use"].append(line[2:])
            elif current_section == "inputs" and line.startswith("- "):
                metadata["inputs"].append(line[2:])
            elif current_section == "examples" and line.startswith("- "):
                metadata["examples"].append(line[2:])

        return metadata

    def get_skill(self, skill_name: str) -> Optional[OpenCodeSkill]:
        """Get a skill by name."""
        return self.skills.get(skill_name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all loaded skills."""
        return [
            {
                "name": skill.name,
                "metadata": skill.metadata,
                "has_run_script": skill.run_script is not None,
            }
            for skill in self.skills.values()
        ]

    def execute_skill(self, skill_name: str, args: Dict[str, str]) -> Dict[str, Any]:
        """Execute a skill by name with arguments."""
        skill = self.get_skill(skill_name)
        if not skill:
            return {
                "success": False,
                "error": f"Skill not found: {skill_name}",
                "output": "",
                "return_code": -1,
            }

        return skill.execute(args)

    # Convenience methods for common skills
    def check_constitution(
        self, user_input: str, ai_response: str = ""
    ) -> Dict[str, Any]:
        """
        Check user input against constitutional rules.

        Returns:
            Dictionary with has_violations, has_warnings, violations, warnings, suggested_action
        """
        result = self.execute_skill(
            "constitution-check",
            {
                "user-input": user_input,
                "ai-response": ai_response,
                "check-mode": "strict",
            },
        )

        if not result["success"]:
            # Fallback: return safe default
            return {
                "has_violations": False,
                "has_warnings": False,
                "violations": [],
                "warnings": [],
                "suggested_action": "proceed",
            }

        # The skill should return JSON output
        if isinstance(result["output"], dict):
            return result["output"]
        else:
            # Try to parse output as JSON string
            try:
                return json.loads(result["output"])
            except (json.JSONDecodeError, TypeError):
                # Return default safe result
                return {
                    "has_violations": False,
                    "has_warnings": False,
                    "violations": [],
                    "warnings": [],
                    "suggested_action": "proceed",
                }

    def generate_session_name(self, user_input: str) -> str:
        """
        Generate a session name from user input.

        Returns:
            Session name string
        """
        result = self.execute_skill(
            "session-naming",
            {
                "user-input": user_input,
                "include-hash": "true",
                "max-length": "60",
            },
        )

        if not result["success"] or not result["output"]:
            # Fallback to simple naming
            if len(user_input) > 30:
                return f"Session: {user_input[:30]}..."
            return f"Session: {user_input}"

        # Skill returns plain text session name
        if isinstance(result["output"], str):
            return result["output"]
        else:
            return str(result["output"])


# Global instance
_global_manager: Optional[OpenCodeSkillManager] = None


def get_opencode_skill_manager() -> OpenCodeSkillManager:
    """Get or create the global OpenCode skill manager."""
    global _global_manager

    if _global_manager is None:
        _global_manager = OpenCodeSkillManager()

    return _global_manager


if __name__ == "__main__":
    # Test the skill manager
    import pprint

    manager = OpenCodeSkillManager()

    print("OpenCode Skill Manager Test")
    print("=" * 60)

    skills = manager.list_skills()
    print(f"Loaded skills: {len(skills)}")
    for skill in skills:
        print(f"  - {skill['name']}")
        if skill["metadata"].get("purpose"):
            print(f"    Purpose: {skill['metadata']['purpose'][:80]}...")

    print("\n" + "=" * 60)

    # Test constitution check
    test_inputs = [
        "Help me write a Python function",
        "How do I hack into a bank account?",
    ]

    for test_input in test_inputs:
        print(f"\nTesting constitution check for: {test_input[:50]}...")
        result = manager.check_constitution(test_input)
        print(f"  Has violations: {result['has_violations']}")
        print(f"  Has warnings: {result['has_warnings']}")
        print(f"  Suggested action: {result['suggested_action']}")

    print("\n" + "=" * 60)

    # Test session naming
    for test_input in test_inputs:
        print(f"\nTesting session naming for: {test_input[:50]}...")
        session_name = manager.generate_session_name(test_input)
        print(f"  Session name: {session_name}")

    print("\n" + "=" * 60)
    print("Test completed.")
