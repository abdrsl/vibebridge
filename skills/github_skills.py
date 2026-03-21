"""
GitHub Skills Downloader - Downloads skills from GitHub repositories.

This module provides functionality to discover and download skills
from GitHub repositories, particularly those designed for AI assistants
and OpenCode integration.

Usage:
    downloader = GitHubSkillDownloader()
    skills = downloader.search_skills('opencode skills')
    downloader.download_skill('owner/repo', 'skill_name')
"""

import json
import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import subprocess
import sys


@dataclass
class GitHubSkill:
    """Represents a skill available on GitHub."""

    repo: str  # owner/repo
    name: str
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    download_url: str = ""
    requirements: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.repo}/{self.name}"


@dataclass
class GitHubSkillDownloaderConfig:
    """Configuration for GitHub skill downloader."""

    github_api_base: str = "https://api.github.com"
    skills_dir: Path = Path(__file__).parent
    temp_dir: Path = Path(tempfile.gettempdir()) / "github_skills"
    enable_downloads: bool = True
    allowed_repos: List[str] = field(default_factory=list)


class GitHubSkillDownloader:
    """Downloads and manages skills from GitHub."""

    def __init__(self, config: Optional[GitHubSkillDownloaderConfig] = None):
        self.config = config or GitHubSkillDownloaderConfig()
        self.downloaded_skills: Dict[str, GitHubSkill] = {}

        # Create directories if needed
        self.config.temp_dir.mkdir(parents=True, exist_ok=True)
        self.config.skills_dir.mkdir(parents=True, exist_ok=True)

    def search_skills(self, query: str, limit: int = 10) -> List[GitHubSkill]:
        """
        Search for skills on GitHub.

        Note: This is a simplified implementation. In production,
        you would use the GitHub API with proper authentication.

        Args:
            query: Search query (e.g., 'opencode skill')
            limit: Maximum number of results

        Returns:
            List of found skills
        """
        # This is a mock implementation
        # In reality, you would use:
        #   requests.get(f"{self.config.github_api_base}/search/repositories?q={query}")

        print(f"[GitHub] Searching for skills: {query}")

        # Mock results for common AI assistant skills
        mock_skills = [
            GitHubSkill(
                repo="opencode-ai/opencode-skills",
                name="code_review",
                description="Code review skill for OpenCode",
                author="OpenCode Team",
                version="1.2.0",
                tags=["code-review", "quality", "opencode"],
            ),
            GitHubSkill(
                repo="opencode-ai/opencode-skills",
                name="security_audit",
                description="Security audit skill for code analysis",
                author="OpenCode Team",
                version="1.1.0",
                tags=["security", "audit", "opencode"],
            ),
            GitHubSkill(
                repo="anthropic/constitutional-ai",
                name="constitutional_ai",
                description="Constitutional AI principles implementation",
                author="Anthropic",
                version="2.0.0",
                tags=["constitutional", "safety", "ethics"],
            ),
            GitHubSkill(
                repo="openai/openai-cookbook",
                name="prompt_engineering",
                description="Advanced prompt engineering techniques",
                author="OpenAI",
                version="1.5.0",
                tags=["prompt", "engineering", "optimization"],
            ),
        ]

        # Filter by query
        query_lower = query.lower()
        filtered = [
            skill
            for skill in mock_skills
            if (
                query_lower in skill.name.lower()
                or query_lower in skill.description.lower()
                or any(query_lower in tag.lower() for tag in skill.tags)
            )
        ]

        return filtered[:limit]

    def download_skill(self, repo: str, skill_name: str) -> Optional[Path]:
        """
        Download a skill from GitHub repository.

        Args:
            repo: GitHub repository (owner/repo)
            skill_name: Name of the skill to download

        Returns:
            Path to downloaded skill file, or None if failed
        """
        if not self.config.enable_downloads:
            print("[GitHub] Downloads are disabled")
            return None

        # Check if already downloaded
        skill_file = self.config.skills_dir / f"{skill_name}.py"
        if skill_file.exists():
            print(f"[GitHub] Skill already exists: {skill_file}")
            return skill_file

        print(f"[GitHub] Downloading skill {skill_name} from {repo}")

        # Create temporary directory for cloning
        temp_repo_dir = self.config.temp_dir / repo.replace("/", "_")
        if temp_repo_dir.exists():
            shutil.rmtree(temp_repo_dir)

        try:
            # Clone repository (simplified - in production use proper Git library)
            clone_url = f"https://github.com/{repo}.git"
            result = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(temp_repo_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                print(f"[GitHub] Clone failed: {result.stderr}")
                return None

            # Look for skill file
            possible_paths = [
                temp_repo_dir / "skills" / f"{skill_name}.py",
                temp_repo_dir / f"{skill_name}.py",
                temp_repo_dir / f"{skill_name}" / f"{skill_name}.py",
            ]

            skill_source = None
            for path in possible_paths:
                if path.exists():
                    skill_source = path
                    break

            if not skill_source:
                print(f"[GitHub] Skill file not found in repository")
                # List available files for debugging
                py_files = list(temp_repo_dir.rglob("*.py"))
                if py_files:
                    print(
                        f"[GitHub] Available Python files: {[f.name for f in py_files[:5]]}"
                    )
                return None

            # Copy skill file to skills directory
            shutil.copy2(skill_source, skill_file)
            print(f"[GitHub] Skill downloaded: {skill_file}")

            # Check for requirements
            req_file = skill_source.parent / "requirements.txt"
            if req_file.exists():
                print(f"[GitHub] Skill has requirements: {req_file}")
                # In production, you might want to install requirements
                # subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)])

            return skill_file

        except Exception as e:
            print(f"[GitHub] Download error: {e}")
            return None
        finally:
            # Cleanup temporary directory
            if temp_repo_dir.exists():
                shutil.rmtree(temp_repo_dir, ignore_errors=True)

    def download_from_url(self, url: str, skill_name: str) -> Optional[Path]:
        """
        Download skill from direct URL.

        Args:
            url: Direct URL to skill file
            skill_name: Name for the skill

        Returns:
            Path to downloaded skill file
        """
        if not self.config.enable_downloads:
            return None

        skill_file = self.config.skills_dir / f"{skill_name}.py"

        try:
            import requests

            print(f"[GitHub] Downloading from URL: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            skill_file.write_text(response.text, encoding="utf-8")
            print(f"[GitHub] Skill downloaded: {skill_file}")

            return skill_file
        except ImportError:
            print("[GitHub] requests module not installed")
            return None
        except Exception as e:
            print(f"[GitHub] Download error: {e}")
            return None

    def list_downloaded_skills(self) -> List[Dict[str, Any]]:
        """List all downloaded skills."""
        skills = []
        for py_file in self.config.skills_dir.glob("*.py"):
            if py_file.name.startswith("__") or py_file.name == "github_skills.py":
                continue

            skills.append(
                {
                    "name": py_file.stem,
                    "path": str(py_file),
                    "size": py_file.stat().st_size,
                    "modified": py_file.stat().st_mtime,
                }
            )

        return skills

    def update_skill(self, skill_name: str) -> bool:
        """Update a previously downloaded skill."""
        # This would re-download the skill
        # In production, you'd check version and update if newer
        print(f"[GitHub] Skill update not implemented yet: {skill_name}")
        return False


# Global downloader instance
GITHUB_DOWNLOADER: Optional[GitHubSkillDownloader] = None


def get_github_downloader() -> GitHubSkillDownloader:
    """Get or create global GitHub downloader."""
    global GITHUB_DOWNLOADER

    if GITHUB_DOWNLOADER is None:
        GITHUB_DOWNLOADER = GitHubSkillDownloader()

    return GITHUB_DOWNLOADER


if __name__ == "__main__":
    # Test the GitHub downloader
    downloader = GitHubSkillDownloader()

    print("GitHub Skill Downloader Test")
    print("=" * 60)

    # Search for skills
    skills = downloader.search_skills("opencode")
    print(f"Found {len(skills)} skills:")
    for skill in skills:
        print(f"  - {skill.full_name}: {skill.description}")

    # List downloaded skills
    downloaded = downloader.list_downloaded_skills()
    print(f"\nDownloaded skills: {len(downloaded)}")
    for skill in downloaded:
        print(f"  - {skill['name']} ({skill['size']} bytes)")

    print("\nNote: Actual downloading is disabled in test mode.")
    print("To enable downloads, set enable_downloads=True in config.")
