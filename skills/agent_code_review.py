"""Code Review Skill — reads project files and provides structured review."""

import subprocess
from pathlib import Path


def review_python_file(filepath: str) -> dict:
    """Review a Python file: syntax check, danger patterns, style."""
    path = Path(filepath)
    if not path.exists():
        return {"error": f"File not found: {filepath}"}
    
    code = path.read_text(encoding="utf-8", errors="replace")
    issues = []
    
    # Syntax check
    try:
        compile(code, str(path), "exec")
    except SyntaxError as e:
        issues.append({"severity": "blocker", "line": e.lineno, "msg": f"SyntaxError: {e.msg}"})
    
    # Danger patterns
    import re
    danger_patterns = [
        (r"eval\s*\(", "eval() risk"),
        (r"exec\s*\(", "exec() risk"),
        (r"shell\s*=\s*True", "shell=True risk"),
    ]
    for pattern, msg in danger_patterns:
        for m in re.finditer(pattern, code):
            line = code[:m.start()].count("\n") + 1
            issues.append({"severity": "warning", "line": line, "msg": msg})
    
    return {
        "file": str(path),
        "lines": len(code.splitlines()),
        "issues_count": len(issues),
        "issues": issues[:20],
        "has_blockers": any(i["severity"] == "blocker" for i in issues),
    }


def review_c_file(filepath: str) -> dict:
    """Review a C file: compile check, danger patterns."""
    path = Path(filepath)
    if not path.exists():
        return {"error": f"File not found: {filepath}"}
    
    issues = []
    
    # Compile check
    try:
        result = subprocess.run(
            ["gcc", "-fsyntax-only", "-Wall", str(path)],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            issues.append({"severity": "blocker", "msg": result.stderr[:500]})
    except FileNotFoundError:
        issues.append({"severity": "info", "msg": "gcc not available"})
    except Exception as e:
        issues.append({"severity": "info", "msg": str(e)})
    
    # Danger patterns
    code = path.read_text(encoding="utf-8", errors="replace")
    import re
    if re.search(r"\bstrcpy\s*\(", code):
        issues.append({"severity": "warning", "msg": "strcpy may overflow"})
    if re.search(r"\bgets\s*\(", code):
        issues.append({"severity": "blocker", "msg": "gets() is unsafe"})
    
    return {
        "file": str(path),
        "issues_count": len(issues),
        "issues": issues,
        "has_blockers": any(i["severity"] == "blocker" for i in issues),
    }
