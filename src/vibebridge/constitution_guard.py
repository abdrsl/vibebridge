"""Constitutional Guard — Intercepts dangerous tool-use commands."""

from __future__ import annotations

import re

# ── Dangerous command patterns ──────────────────────────────────────────
# Each tuple: (regex_pattern, human_readable_description)
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    # Destructive file operations
    (r"\brm\s+-[rf]*[rf]\b", "删除文件/目录（强制/递归）"),
    (r"\brm\s+--recursive", "递归删除文件/目录"),
    (r"\brm\s+.*\*/?\s*$", "删除通配文件"),
    (r"\brmdir\s+-p\b", "递归删除目录"),
    (r"\bunlink\s+", "删除文件"),
    (r"\bfind\s+.*-delete\b", "批量删除文件"),
    (r"\bfind\s+.*-exec\s+rm\b", "批量删除文件"),
    # Git destructive
    (r"\bgit\s+reset\s+--hard\b", "强制重置代码（不可逆）"),
    (r"\bgit\s+clean\s+-[fdx]*[fdx]\b", "清理未跟踪文件"),
    (r"\bgit\s+push\s+--force\b", "强制推送（覆盖远程）"),
    (r"\bgit\s+push\s+-f\b", "强制推送（覆盖远程）"),
    # Database destructive
    (r"\bdrop\s+(database|table|schema|index|view)\b", "删除数据库对象"),
    (r"\bdelete\s+from\b", "删除数据"),
    (r"\btruncate\s+table\b", "清空表数据"),
    # Disk / system destructive
    (r"\bdd\s+if=", "磁盘直接写入（dd）"),
    (r"\bmkfs\b", "格式化磁盘"),
    (r"\bmkfs\.[a-z0-9]+\b", "格式化磁盘"),
    (r"\bparted\s+.*mklabel\b", "重新分区"),
    (r"\bfdisk\s+.*-d\b", "删除分区"),
    # Permission changes that can lock out
    (r"\bchmod\s+[-+]?0[0-7]{2,3}\b", "修改文件权限（可能锁定）"),
    (r"\bchmod\s+[-+]?000\b", "剥夺所有权限"),
    (r"\bchown\s+-R\b", "递归修改文件所有者"),
    # Privilege escalation
    (r"\bsudo\b", "提权执行（sudo）"),
    (r"\bsu\s+-\b", "切换用户（su）"),
    # Remote code execution
    (r"\bcurl\s+.*\|\s*(ba)?sh\b", "远程脚本执行"),
    (r"\bwget\s+.*-O\s+-.*\|\s*(ba)?sh\b", "远程脚本执行"),
    (r"\beval\s+\$", "动态代码执行"),
    (r"\beval\s+\`", "动态代码执行"),
    # System shutdown / process kill
    (r"\bshutdown\b", "系统关机"),
    (r"\breboot\b", "系统重启"),
    (r"\bpoweroff\b", "系统关机"),
    (r"\bhalt\b", "系统停机"),
    (r"\bkill\s+-9\b", "强制终止进程"),
    (r"\bpkill\s+-9\b", "强制终止进程"),
    (r"\bkillall\s+-9\b", "强制终止进程"),
    # Dangerous redirects
    (r">\s*/dev/[sh]da\b", "写入块设备"),
    (r">\s*/dev/null\b.*\b(rm|mv|cp)\b", "结合重定向的危险操作"),
    # Move to dangerous locations
    (r"\bmv\s+.*\s+/\s*$", "移动到根目录"),
    (r"\bmv\s+.*\s+/dev/null\b", "移动到空设备（删除）"),
    # npm / pip destructive
    (r"\bnpm\s+uninstall\s+-g\b", "全局卸载包"),
    (r"\bpip\s+uninstall\s+-y\b", "强制卸载包"),
    (r"\bconda\s+remove\s+-y\b", "强制卸载包"),
    # Docker destructive
    (r"\bdocker\s+(rm|rmi|system\s+prune)\b", "删除容器/镜像"),
    (r"\bdocker\s+.*--force\b", "强制删除容器/镜像"),
]

# Commands that are always allowed (whitelist overrides)
SAFE_COMMANDS: list[str] = [
    r"^git\s+status\b",
    r"^git\s+log\b",
    r"^git\s+diff\b",
    r"^git\s+show\b",
    r"^git\s+branch\b",
    r"^ls\b",
    r"^cat\b",
    r"^echo\b",
    r"^grep\b",
    r"^find\b.*-type\s+f\b",
    r"^find\b.*-name\b",
    r"^pwd\b",
    r"^head\b",
    r"^tail\b",
    r"^wc\b",
    r"^ps\b",
    r"^top\b",
    r"^df\b",
    r"^du\b",
    r"^mkdir\b",
    r"^touch\b",
    r"^cp\b",
    r"^mv\b.*[^/]\s+[^/]\b",  # mv that is not to root
]


def is_dangerous_command(command: str) -> tuple[bool, str]:
    """Check if a command is dangerous.

    Returns:
        (is_dangerous, description) tuple.
    """
    if not command or not command.strip():
        return False, ""

    cmd = command.strip()

    # Whitelist check first — safe commands bypass all checks
    for safe_pat in SAFE_COMMANDS:
        if re.search(safe_pat, cmd, re.IGNORECASE):
            return False, ""

    # Check dangerous patterns
    for pattern, desc in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return True, desc

    return False, ""


def format_auth_prompt(command: str, description: str) -> str:
    """Format the authorization prompt for a dangerous command."""
    short_cmd = command[:80] + "..." if len(command) > 80 else command
    return (
        f"⛔ **检测到危险操作：{description}**\n"
        f"```\n{short_cmd}\n```\n"
        f"如需授权执行，请发送：`mysecret {short_cmd}`"
    )


# ── Authorization token ────────────────────────────────────────────────
AUTH_PREFIX = "mysecret"


def parse_auth_message(text: str) -> str | None:
    """Parse an authorization message.

    Args:
        text: User message, e.g. "mysecret rm -rf dist/"

    Returns:
        The command to authorize, or None if not an auth message.
    """
    text = text.strip()
    if text.lower().startswith(AUTH_PREFIX.lower()):
        remainder = text[len(AUTH_PREFIX) :].strip()
        return remainder if remainder else None
    return None


def is_auth_message(text: str) -> bool:
    """Check if a message is an authorization message."""
    return text.strip().lower().startswith(AUTH_PREFIX.lower())
