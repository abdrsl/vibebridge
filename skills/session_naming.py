"""
Session Naming Skill - Automatically generates descriptive session names
based on user input.

This skill analyzes user input to create meaningful session/task names
that summarize the conversation intent. This helps with organization
and retrieval of historical sessions.

Usage:
- Call `generate_session_name(user_input)` to get a session name
- Integrate with task/session creation systems
- Names are cached for consistency
"""

import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib
import json


@dataclass
class SessionNamingRule:
    """Rule for extracting key information from user input."""

    name: str
    pattern: str  # Regex pattern
    extract_group: int = 1  # Which group to extract
    prefix: str = ""  # Optional prefix for the session name
    suffix: str = ""  # Optional suffix
    max_length: int = 50  # Maximum length of extracted text

    def apply(self, text: str) -> Optional[str]:
        """Apply rule to extract session name component."""
        match = re.search(self.pattern, text, re.IGNORECASE)
        if match:
            extracted = match.group(self.extract_group).strip()
            if len(extracted) > self.max_length:
                extracted = extracted[: self.max_length] + "..."
            return f"{self.prefix}{extracted}{self.suffix}"
        return None


@dataclass
class SessionNamingConfig:
    """Configuration for session naming."""

    default_name: str = "AI会话"
    max_total_length: int = 60
    include_hash: bool = True  # Include hash for uniqueness
    hash_length: int = 8
    rules: List[SessionNamingRule] = field(default_factory=list)

    def __post_init__(self):
        """Initialize with default rules if none provided."""
        if not self.rules:
            self.rules = self.get_default_rules()

    def get_default_rules(self) -> List[SessionNamingRule]:
        """Return default session naming rules."""
        return [
            # Programming/development tasks
            SessionNamingRule(
                name="python_function",
                pattern=r"(?:写|创建|实现|编写|make|create|implement)\s+(?:一个|a\s+)?(?:Python\s+)?(?:函数|function)\s+(?:名为|called|named)?\s*['\"]?([^'\"]+)['\"]?",
                prefix="Python函数: ",
                max_length=30,
            ),
            SessionNamingRule(
                name="fix_bug",
                pattern=r"(?:修复|解决|fix|debug)\s+(?:一个|a\s+)?(?:bug|错误|问题)\s*(?:在|in)?\s*(?:['\"]([^'\"]+)['\"]|(\S+))",
                prefix="修复: ",
                max_length=25,
            ),
            SessionNamingRule(
                name="add_feature",
                pattern=r"(?:添加|增加|add)\s+(?:一个|a\s+)?(?:功能|feature)\s*(?:名为|called)?\s*['\"]?([^'\"]+)['\"]?",
                prefix="功能: ",
                max_length=25,
            ),
            SessionNamingRule(
                name="optimize",
                pattern=r"(?:优化|改进|optimize|improve)\s+(?:['\"]([^'\"]+)['\"]|(\S+))",
                prefix="优化: ",
                max_length=25,
            ),
            # File operations
            SessionNamingRule(
                name="create_file",
                pattern=r"(?:创建|新建|create)\s+(?:一个|a\s+)?(?:文件|file)\s*(?:名为|called)?\s*['\"]?([^'\"]+)['\"]?",
                prefix="文件: ",
                max_length=25,
            ),
            SessionNamingRule(
                name="modify_file",
                pattern=r"(?:修改|编辑|edit|modify)\s+(?:文件|file)\s*(?:['\"]([^'\"]+)['\"]|(\S+))",
                prefix="编辑: ",
                max_length=25,
            ),
            # API/Web related
            SessionNamingRule(
                name="api_endpoint",
                pattern=r"(?:创建|添加|create|add)\s+(?:一个|a\s+)?(?:API\s+端点|endpoint)\s*(?:用于|for)?\s*['\"]?([^'\"]+)['\"]?",
                prefix="API: ",
                max_length=25,
            ),
            # General requests
            SessionNamingRule(
                name="help_with",
                pattern=r"(?:帮|帮助|help)\s+(?:我|with)?\s*(?:['\"]([^'\"]+)['\"]|(.+?))(?:\?|$)",
                prefix="帮助: ",
                max_length=30,
            ),
            SessionNamingRule(
                name="how_to",
                pattern=r"(?:如何|how\s+to)\s+(['\"]([^'\"]+)['\"]|(.+?))(?:\?|$)",
                prefix="如何: ",
                max_length=30,
            ),
            # Project specific (OpenCode-Feishu Bridge)
            SessionNamingRule(
                name="feishu_integration",
                pattern=r"(?:飞书|Feishu|feishu)\s*(?:集成|integration|连接|connect)",
                prefix="飞书集成",
            ),
            SessionNamingRule(
                name="opencode_task",
                pattern=r"(?:OpenCode|opencode)\s*(?:任务|task)",
                prefix="OpenCode任务",
            ),
            SessionNamingRule(
                name="security_enhancement",
                pattern=r"(?:安全|security)\s*(?:增强|improve|加固)",
                prefix="安全加固",
            ),
        ]

    def generate_hash(self, text: str) -> str:
        """Generate short hash from text."""
        hash_obj = hashlib.sha256(text.encode("utf-8"))
        return hash_obj.hexdigest()[: self.hash_length]


class SessionNamer:
    """Main class for generating session names."""

    def __init__(self, config: Optional[SessionNamingConfig] = None):
        self.config = config or SessionNamingConfig()
        self.cache: Dict[str, str] = {}  # Cache of input -> session name

    def generate_session_name(self, user_input: str) -> str:
        """
        Generate a session name from user input.

        Args:
            user_input: The user's message or query

        Returns:
            Descriptive session name
        """
        # Check cache first
        cache_key = user_input[:100]  # Use first 100 chars as cache key
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Try each rule in order
        for rule in self.config.rules:
            result = rule.apply(user_input)
            if result:
                session_name = self._finalize_name(result, user_input)
                self.cache[cache_key] = session_name
                return session_name

        # No rule matched, use default with context
        default_name = self._create_default_name(user_input)
        self.cache[cache_key] = default_name
        return default_name

    def _finalize_name(self, base_name: str, original_input: str) -> str:
        """Finalize session name with length limits and hash."""
        # Truncate if too long
        if len(base_name) > self.config.max_total_length:
            base_name = base_name[: self.config.max_total_length - 3] + "..."

        # Add hash if configured
        if self.config.include_hash:
            hash_str = self.config.generate_hash(original_input)
            if len(base_name) + len(hash_str) + 1 <= self.config.max_total_length:
                return f"{base_name} #{hash_str}"
            else:
                # Truncate base name to make room for hash
                available = self.config.max_total_length - len(hash_str) - 1
                if available > 10:  # Ensure reasonable minimum
                    base_name = base_name[:available] + "..."
                    return f"{base_name} #{hash_str}"

        return base_name

    def _create_default_name(self, user_input: str) -> str:
        """Create default session name from input."""
        # Extract first meaningful sentence
        sentences = re.split(r"[.!?。！？]", user_input)
        first_sentence = sentences[0].strip() if sentences else user_input

        # Clean up
        first_sentence = re.sub(r"\s+", " ", first_sentence)

        # Truncate
        if len(first_sentence) > 30:
            first_sentence = first_sentence[:30] + "..."

        if not first_sentence or len(first_sentence) < 5:
            first_sentence = self.config.default_name

        return self._finalize_name(first_sentence, user_input)

    def batch_generate(self, inputs: List[str]) -> List[str]:
        """Generate session names for multiple inputs."""
        return [self.generate_session_name(input_text) for input_text in inputs]

    def analyze_input(self, user_input: str) -> Dict[str, Any]:
        """Analyze user input and show which rules matched."""
        analysis = {
            "input": user_input,
            "length": len(user_input),
            "matched_rules": [],
            "suggested_name": None,
        }

        for rule in self.config.rules:
            result = rule.apply(user_input)
            if result:
                analysis["matched_rules"].append(
                    {
                        "rule_name": rule.name,
                        "pattern": rule.pattern,
                        "extracted": result,
                    }
                )

        analysis["suggested_name"] = self.generate_session_name(user_input)
        return analysis


# Singleton instance
DEFAULT_SESSION_NAMER = SessionNamer()


def generate_session_name(user_input: str) -> str:
    """
    Convenience function to generate session name.

    Example usage:
        session_name = generate_session_name("帮我写一个Python函数计算斐波那契数列")
        # Returns: "Python函数: 计算斐波那契数列 #a1b2c3d4"
    """
    return DEFAULT_SESSION_NAMER.generate_session_name(user_input)


def analyze_session_name(user_input: str) -> Dict[str, Any]:
    """Analyze how session name would be generated."""
    return DEFAULT_SESSION_NAMER.analyze_input(user_input)


if __name__ == "__main__":
    # Test the session namer
    test_inputs = [
        "帮我写一个Python函数计算斐波那契数列",
        "如何优化这个数据库查询的性能？",
        "创建一个名为user_auth的API端点",
        "修复登录页面的bug",
        "添加用户注册功能",
        "安全加固我们的Feishu集成",
        "Hello, how are you?",
        "OpenCode任务：清理项目结构",
        "修改app/main.py文件添加新路由",
        "飞书集成测试",
    ]

    namer = SessionNamer()

    print("Session Naming Skill Test\n" + "=" * 60)

    for test_input in test_inputs:
        name = namer.generate_session_name(test_input)
        analysis = namer.analyze_input(test_input)

        print(f"\nInput: {test_input[:50]}...")
        print(f"Session Name: {name}")

        if analysis["matched_rules"]:
            print(f"Matched Rules: {len(analysis['matched_rules'])}")
            for match in analysis["matched_rules"]:
                print(f"  - {match['rule_name']}: {match['extracted']}")
        else:
            print("No specific rules matched (using default)")

        print(f"Length: {len(name)} chars")

    print("\n" + "=" * 60)
    print(f"Tested {len(test_inputs)} inputs successfully.")
