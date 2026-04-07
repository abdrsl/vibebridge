"""
AI Skills Package - Contains constitutional rules, session naming, and other skills.

This package provides modular skills that can be loaded and applied to AI interactions.
"""

from .constitution import (
    DEFAULT_CONSTITUTION,
    Constitution,
    ConstitutionalRule,
    check_constitution,
    get_constitution_rules,
)
from .session_naming import (
    DEFAULT_SESSION_NAMER,
    SessionNamer,
    SessionNamingConfig,
    SessionNamingRule,
    analyze_session_name,
    generate_session_name,
)
from .skill_manager import (
    Skill,
    SkillConfig,
    SkillManager,
    get_skill_manager,
    process_user_input,
)

__version__ = "1.0.0"
__all__ = [
    # Constitution
    "ConstitutionalRule",
    "Constitution",
    "DEFAULT_CONSTITUTION",
    "check_constitution",
    "get_constitution_rules",
    # Session Naming
    "SessionNamingRule",
    "SessionNamingConfig",
    "SessionNamer",
    "DEFAULT_SESSION_NAMER",
    "generate_session_name",
    "analyze_session_name",
    # Skill Manager
    "Skill",
    "SkillConfig",
    "SkillManager",
    "get_skill_manager",
    "process_user_input",
]
