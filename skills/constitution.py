"""
Constitutional AI Skill - Defines core rules and principles for AI behavior.

This skill implements constitutional principles that the AI must follow,
similar to Anthropic's Constitutional AI approach. These rules ensure
safe, helpful, and harmless interactions.

Usage:
- Load this skill in the AI agent configuration
- Rules are automatically applied to all interactions
- Violations trigger appropriate responses
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import re


@dataclass
class ConstitutionalRule:
    """A single constitutional rule with priority and enforcement logic."""

    id: str
    description: str
    rule_text: str
    priority: int = 0  # Higher priority rules are checked first
    enforcement: str = "reject"  # reject, warn, modify, log

    def check_violation(self, user_input: str, ai_response: str) -> Optional[str]:
        """
        Check if the rule is violated.

        Returns:
            Violation message if violated, None otherwise.
        """
        # Basic keyword checking (can be extended with more sophisticated logic)
        if self.enforcement == "reject":
            # Check for harmful content in user input
            harmful_patterns = [
                r"(?i)hack.*(password|credit card|bank account)",
                r"(?i)create.*(virus|malware|ransomware)",
                r"(?i)how to.*(cheat|steal|kill|harm)",
                r"(?i)generate.*(hate speech|violent content)",
                r"(?i)exploit.*(vulnerability|security hole)",
            ]

            for pattern in harmful_patterns:
                if re.search(pattern, user_input):
                    return f"Rule '{self.id}' violated: {self.description}"

        # Add more sophisticated checks as needed
        return None


@dataclass
class Constitution:
    """Collection of constitutional rules."""

    name: str = "AI Product Lab Constitution"
    version: str = "1.0"
    rules: List[ConstitutionalRule] = field(default_factory=list)

    def __post_init__(self):
        """Initialize with default rules if none provided."""
        if not self.rules:
            self.rules = self.get_default_rules()

    def get_default_rules(self) -> List[ConstitutionalRule]:
        """Return the default set of constitutional rules."""
        return [
            ConstitutionalRule(
                id="safety-1",
                description="Do not provide harmful, dangerous, or unethical content",
                rule_text="The AI must not generate content that could cause harm, promote violence, or facilitate illegal activities.",
                priority=10,
                enforcement="reject",
            ),
            ConstitutionalRule(
                id="helpfulness-1",
                description="Be helpful, honest, and transparent",
                rule_text="The AI should provide accurate information and acknowledge its limitations when uncertain.",
                priority=5,
                enforcement="warn",
            ),
            ConstitutionalRule(
                id="privacy-1",
                description="Protect user privacy and confidentiality",
                rule_text="The AI must not request or store sensitive personal information unnecessarily.",
                priority=8,
                enforcement="reject",
            ),
            ConstitutionalRule(
                id="compliance-1",
                description="Comply with applicable laws and regulations",
                rule_text="The AI must not facilitate activities that violate laws or regulations.",
                priority=9,
                enforcement="reject",
            ),
            ConstitutionalRule(
                id="transparency-1",
                description="Clearly identify as an AI assistant",
                rule_text="The AI should identify itself as an AI when appropriate and not pretend to be human.",
                priority=3,
                enforcement="warn",
            ),
            ConstitutionalRule(
                id="scope-1",
                description="Stay within defined capabilities",
                rule_text="The AI should acknowledge when a request is outside its capabilities and suggest alternatives.",
                priority=4,
                enforcement="warn",
            ),
            ConstitutionalRule(
                id="security-1",
                description="Promote security best practices",
                rule_text="The AI should encourage secure practices and not provide guidance that would compromise security.",
                priority=7,
                enforcement="reject",
            ),
        ]

    def check_all_rules(self, user_input: str, ai_response: str = "") -> Dict[str, Any]:
        """
        Check all constitutional rules against user input and AI response.

        Returns:
            Dictionary with violation information and actions.
        """
        violations = []
        warnings = []

        # Sort rules by priority (highest first)
        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            violation = rule.check_violation(user_input, ai_response)
            if violation:
                if rule.enforcement == "reject":
                    violations.append(
                        {
                            "rule_id": rule.id,
                            "description": rule.description,
                            "message": violation,
                            "enforcement": rule.enforcement,
                        }
                    )
                elif rule.enforcement == "warn":
                    warnings.append(
                        {
                            "rule_id": rule.id,
                            "description": rule.description,
                            "message": violation,
                            "enforcement": rule.enforcement,
                        }
                    )

        return {
            "has_violations": len(violations) > 0,
            "has_warnings": len(warnings) > 0,
            "violations": violations,
            "warnings": warnings,
            "suggested_action": "reject" if violations else "proceed",
        }

    def format_for_display(self) -> str:
        """Format the constitution as a readable string."""
        lines = [f"# {self.name} v{self.version}", ""]

        # Group by priority
        by_priority = {}
        for rule in self.rules:
            by_priority.setdefault(rule.priority, []).append(rule)

        for priority in sorted(by_priority.keys(), reverse=True):
            lines.append(f"## Priority {priority}")
            for rule in by_priority[priority]:
                lines.append(f"### {rule.id}: {rule.description}")
                lines.append(f"- **Rule**: {rule.rule_text}")
                lines.append(f"- **Enforcement**: {rule.enforcement}")
                lines.append("")

        return "\n".join(lines)


# Singleton instance
DEFAULT_CONSTITUTION = Constitution()


def check_constitution(user_input: str, ai_response: str = "") -> Dict[str, Any]:
    """
    Convenience function to check against the default constitution.

    Example usage:
        result = check_constitution(user_message)
        if result["has_violations"]:
            return "I cannot fulfill this request due to policy restrictions."
    """
    return DEFAULT_CONSTITUTION.check_all_rules(user_input, ai_response)


def get_constitution_rules() -> List[Dict[str, Any]]:
    """Get list of all constitutional rules."""
    return [
        {
            "id": rule.id,
            "description": rule.description,
            "rule_text": rule.rule_text,
            "priority": rule.priority,
            "enforcement": rule.enforcement,
        }
        for rule in DEFAULT_CONSTITUTION.rules
    ]


if __name__ == "__main__":
    # Test the constitution
    test_inputs = [
        "How do I hack into a bank account?",
        "Can you help me write a Python function?",
        "Generate some hate speech about a group of people.",
        "What's the weather like today?",
    ]

    print(DEFAULT_CONSTITUTION.format_for_display())
    print("\n" + "=" * 80 + "\n")

    for test_input in test_inputs:
        print(f"Test input: {test_input}")
        result = check_constitution(test_input)
        if result["has_violations"]:
            print(f"  ❌ Violations: {len(result['violations'])}")
            for violation in result["violations"]:
                print(f"     - {violation['message']}")
        elif result["has_warnings"]:
            print(f"  ⚠️  Warnings: {len(result['warnings'])}")
            for warning in result["warnings"]:
                print(f"     - {warning['message']}")
        else:
            print("  ✅ No violations or warnings")
        print()
