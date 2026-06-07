"""Unified agent configuration — aliases and display names."""
from __future__ import annotations

import re
from dataclasses import dataclass

AGENT_NAMES = [
    "ceo-agent",
    "pm-agent",
    "software-agent",
    "hardware-agent",
    "test-agent",
    "reviewer-agent",
    "structure-agent",
    "it-ops-agent",
    "admin-agent",
    "hr-agent",
]

AGENTS = {
    "ceo-agent": {"display_name": "CEO"},
    "pm-agent": {"display_name": "Project Manager"},
    "software-agent": {"display_name": "Software Engineer"},
    "hardware-agent": {"display_name": "Hardware Engineer"},
    "test-agent": {"display_name": "Test Engineer"},
    "reviewer-agent": {"display_name": "Quality Reviewer"},
    "structure-agent": {"display_name": "Structure Engineer"},
    "it-ops-agent": {"display_name": "IT Ops"},
    "admin-agent": {"display_name": "Admin"},
    "hr-agent": {"display_name": "HR"},
}


def get_display_name(agent_name: str) -> str:
    return AGENTS.get(agent_name, {}).get("display_name", agent_name)

_AGENT_ALIASES: dict[str, str] = {
    "ceo": "ceo-agent",
    "ceo-agent": "ceo-agent",
    "项目经理": "pm-agent",
    "pm": "pm-agent",
    "pm-agent": "pm-agent",
    "software": "software-agent",
    "software-agent": "software-agent",
    "软件工程师": "software-agent",
    "hardware": "hardware-agent",
    "hardware-agent": "hardware-agent",
    "硬件工程师": "hardware-agent",
    "test": "test-agent",
    "test-agent": "test-agent",
    "测试工程师": "test-agent",
    "reviewer": "reviewer-agent",
    "reviewer-agent": "reviewer-agent",
    "质量审核员": "reviewer-agent",
    "structure": "structure-agent",
    "structure-agent": "structure-agent",
    "结构工程师": "structure-agent",
    "it": "it-ops-agent",
    "it-ops": "it-ops-agent",
    "it-ops-agent": "it-ops-agent",
    "运维": "it-ops-agent",
    "admin": "admin-agent",
    "admin-agent": "admin-agent",
    "行政": "admin-agent",
    "hr": "hr-agent",
    "hr-agent": "hr-agent",
    "人事": "hr-agent",
}


def resolve_all(text: str) -> list[str]:
    """Extract agent names from @mentions in text."""
    mentions = re.findall(r"@([\w\-\u4e00-\u9fff]+)", text)
    if not mentions:
        return ["ceo-agent"]

    results: list[str] = []
    seen: set[str] = set()
    for mention in mentions:
        mention_lower = mention.lower()
        if mention_lower == "_all":
            return list(AGENT_NAMES)
        agent = _AGENT_ALIASES.get(mention_lower)
        if agent and agent not in seen:
            results.append(agent)
            seen.add(agent)

    return results if results else ["ceo-agent"]
