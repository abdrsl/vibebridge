"""STM32 Project Tools — compile, flash, test for STM32 projects."""

import subprocess
from pathlib import Path
from typing import Any


def compile_stm32_project(project_path: str) -> dict:
    """Compile an STM32 project using its Makefile."""
    build_dir = Path(project_path) / "Build"
    tests_dir = Path(project_path) / "Tests"
    
    results = {"project": project_path, "build": {}, "tests": {}}
    
    # Try unit tests (gcc-based, no hardware needed)
    if tests_dir.exists():
        try:
            subprocess.run(["make", "clean"], cwd=tests_dir, capture_output=True, text=True, timeout=30)
            build = subprocess.run(["make", "all"], cwd=tests_dir, capture_output=True, text=True, timeout=120)
            results["tests"]["build_ok"] = build.returncode == 0
            if build.returncode == 0:
                # Run test executables
                for exe in tests_dir.glob("test_*"):
                    if exe.is_file() and not exe.suffix:
                        run = subprocess.run([str(exe)], cwd=tests_dir, capture_output=True, text=True, timeout=30)
                        results["tests"][exe.name] = {
                            "passed": "ALL TESTS PASSED" in (run.stdout + run.stderr),
                            "output": run.stdout[:500]
                        }
        except Exception as e:
            results["tests"]["error"] = str(e)
    
    # Try STM32 cross-compilation
    if build_dir.exists():
        try:
            subprocess.run(["make", "clean"], cwd=build_dir, capture_output=True, text=True, timeout=30)
            build = subprocess.run(["make", "all"], cwd=build_dir, capture_output=True, text=True, timeout=120)
            results["build"]["ok"] = build.returncode == 0
            results["build"]["output"] = build.stdout[:1000] if build.returncode == 0 else build.stderr[:1000]
        except Exception as e:
            results["build"]["error"] = str(e)
    
    return results


def analyze_stm32_structure(project_path: str) -> dict:
    """Analyze the structure of an STM32 project."""
    path = Path(project_path)
    if not path.exists():
        return {"error": f"Project not found: {project_path}"}
    
    structure = {"path": str(path), "dirs": {}, "files": []}
    
    # Count files by type
    c_files = list(path.rglob("*.c"))
    h_files = list(path.rglob("*.h"))
    md_files = list(path.rglob("*.md"))
    
    structure["counts"] = {
        "c_files": len(c_files),
        "h_files": len(h_files),
        "md_files": len(md_files),
    }
    
    # List key files
    for f in c_files[:10]:
        structure["files"].append({"path": str(f.relative_to(path)), "size": f.stat().st_size})
    
    return structure
