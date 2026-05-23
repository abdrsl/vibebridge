"""Repo Analyzer Skill — Deep architectural analysis of projects.
Inspired by: yzddmr6/repo-analyzer (GitHub, April 2026, 342 stars)
"""

import os
import json
from pathlib import Path
from typing import Any


def analyze_repo_structure(project_path: str) -> dict:
    """One-command deep analysis of a project repository.
    
    Returns structured report: overview, tech stack, directory tree,
    core modules, dependencies, and improvement suggestions.
    """
    path = Path(project_path)
    if not path.exists():
        return {"error": f"Project not found: {project_path}"}
    
    result = {
        "project": str(path),
        "overview": {},
        "tech_stack": {},
        "structure": {},
        "core_modules": [],
        "dependencies": [],
        "quality": {},
        "suggestions": [],
    }
    
    # 1. Overview
    readme = _find_file(path, "README.md")
    if readme:
        first_lines = readme.read_text(errors="replace").split("\n")[:10]
        result["overview"]["description"] = "\n".join(line for line in first_lines if line.strip())
    
    # 2. Tech stack detection
    tech = result["tech_stack"]
    tech["languages"] = _count_by_extension(path)
    if next(path.glob("Makefile"), None):
        tech["build_system"] = "Make"
    if next(path.glob("CMakeLists.txt"), None):
        tech["build_system"] = "CMake"
    if next(path.glob("setup.py"), None) or next(path.glob("pyproject.toml"), None):
        tech["build_system"] = tech.get("build_system", "") + "/Python"
    if next(path.glob("Dockerfile*"), None):
        tech["container"] = True
    if next(path.glob(".git"), None):
        tech["vcs"] = "git"
    
    # 3. Structure
    result["structure"] = _get_dir_tree(path, max_depth=3)
    
    # 4. Core modules
    for py_file in sorted(path.rglob("*.py")):
        if "__pycache__" not in str(py_file):
            size = py_file.stat().st_size
            if size > 1000:  # Only files >1KB
                result["core_modules"].append({
                    "path": str(py_file.relative_to(path)),
                    "size": size,
                    "lines": len(py_file.read_text(errors="replace").splitlines()),
                })
    
    # 5. Quality metrics
    total_files = len(list(path.rglob("*")))
    py_files = len(list(path.rglob("*.py")))
    md_files = len(list(path.rglob("*.md")))
    result["quality"] = {
        "total_files": total_files,
        "python_files": py_files,
        "documentation_files": md_files,
        "doc_ratio": round(md_files / max(py_files, 1), 2),
    }
    
    # 6. Suggestions
    q = result["quality"]
    if q["doc_ratio"] < 0.1:
        result["suggestions"].append("文档覆盖率低，建议添加更多README和设计文档")
    if len(result["core_modules"]) > 50:
        result["suggestions"].append("项目规模较大，建议按功能拆分为子模块")
    if not tech.get("build_system"):
        result["suggestions"].append("未检测到构建系统（Makefile/CMake/setup.py）")
    has_tests = bool(next(path.rglob("test_*.py"), None) or next(path.rglob("*_test.py"), None))
    if not has_tests:
        result["suggestions"].append("未检测到测试文件，建议添加单元测试")
    
    return result


def _find_file(path: Path, name: str) -> Path | None:
    """Find a file by name in directory tree."""
    for f in path.rglob(name):
        return f
    return None


def _count_by_extension(path: Path) -> dict:
    """Count files by extension."""
    counts = {}
    for f in path.rglob("*"):
        if f.is_file() and "__pycache__" not in str(f):
            ext = f.suffix.lower() or "(no ext)"
            counts[ext] = counts.get(ext, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10])


def _get_dir_tree(path: Path, max_depth: int = 3, current_depth: int = 0) -> dict:
    """Generate directory tree structure."""
    if current_depth > max_depth:
        return {"...": "truncated"}
    
    tree = {}
    try:
        for item in sorted(path.iterdir()):
            if item.name.startswith(".") and item.name not in (".git", ".github", ".env", ".config"):
                continue
            if item.name == "__pycache__":
                continue
            if item.is_dir():
                subtree = _get_dir_tree(item, max_depth, current_depth + 1)
                if subtree:
                    tree[item.name + "/"] = subtree
            elif item.is_file():
                tree[item.name] = item.stat().st_size
    except PermissionError:
        tree["(permission denied)"] = None
    
    return tree


def compare_agent_outputs(task_results: list) -> dict:
    """Compare outputs from multiple agents on the same task.
    Inspired by Google agents-cli eval skill.
    """
    if not task_results:
        return {"error": "No results to compare"}
    
    comparison = {
        "total_agents": len(task_results),
        "successful": sum(1 for r in task_results if r.get("status") == "completed"),
        "failed": sum(1 for r in task_results if r.get("status") == "failed"),
        "avg_response_length": sum(len(str(r.get("result", {}).get("response", ""))) for r in task_results) // max(len(task_results), 1),
        "agents": [],
    }
    
    for r in task_results:
        comparison["agents"].append({
            "agent": r.get("agent", "?"),
            "status": r.get("status", "?"),
            "tools_used": len(r.get("result", {}).get("all_tool_calls", [])),
            "response_size": len(str(r.get("result", {}).get("response", ""))),
        })
    
    return comparison
