import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

TASK_DIR = Path("data/tasks")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def ensure_task_dir() -> None:
    TASK_DIR.mkdir(parents=True, exist_ok=True)


def save_task(task: dict[str, Any]) -> dict[str, str]:
    ensure_task_dir()

    task_id = task.get("task_id")
    if not task_id:
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid4().hex[:8]
        task["task_id"] = task_id

    now = utc_now_iso()
    if not task.get("created_at"):
        task["created_at"] = now
    task["updated_at"] = now

    file_path = TASK_DIR / f"{task_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False, indent=2)

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
                item = json.load(f)

            task = item.get("task", {})
            results.append(
                {
                    "task_id": item.get("task_id", path.stem),
                    "source": item.get("source"),
                    "parsed_text": item.get("parsed_text"),
                    "task_type": task.get("task_type"),
                    "status": task.get("status"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
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


def update_task(task_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    existing = get_task(task_id)
    if not existing:
        return None

    existing.update(updates)
    existing["updated_at"] = utc_now_iso()

    file_path = TASK_DIR / f"{task_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return existing
