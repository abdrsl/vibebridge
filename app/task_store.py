import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

TASK_DIR = Path("data/tasks")


def ensure_task_dir() -> None:
    TASK_DIR.mkdir(parents=True, exist_ok=True)


def save_task(task_data: dict[str, Any]) -> dict[str, Any]:
    ensure_task_dir()

    task_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    file_path = TASK_DIR / f"{task_id}.json"

    task_data["task_id"] = task_id

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)

    return {
        "task_id": task_id,
        "file_path": str(file_path),
    }


def list_tasks(limit: int = 20) -> list[dict[str, Any]]:
    ensure_task_dir()

    files = sorted(
        TASK_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    results: list[dict[str, Any]] = []

    for path in files[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            results.append(
                {
                    "task_id": data.get("task_id"),
                    "source": data.get("source"),
                    "parsed_text": data.get("parsed_text"),
                    "task_type": data.get("task", {}).get("task_type"),
                    "status": data.get("task", {}).get("status"),
                    "file_path": str(path),
                }
            )
        except Exception as e:
            results.append(
                {
                    "task_id": path.stem,
                    "status": "error",
                    "file_path": str(path),
                    "error": str(e),
                }
            )

    return results


def get_task(task_id: str) -> dict[str, Any] | None:
    ensure_task_dir()

    file_path = TASK_DIR / f"{task_id}.json"
    if not file_path.exists():
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
