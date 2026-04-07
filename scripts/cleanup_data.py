#!/usr/bin/env python3
"""
数据清理脚本
用于清理测试数据和历史数据
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta


def cleanup_old_data(days_old=7):
    """清理指定天数前的数据文件"""
    data_dir = Path("data")
    cutoff_date = datetime.now() - timedelta(days=days_old)

    cleaned_files = []

    # 清理任务数据
    tasks_dir = data_dir / "tasks"
    if tasks_dir.exists():
        for task_file in tasks_dir.glob("*.json"):
            try:
                with open(task_file, "r") as f:
                    task_data = json.load(f)

                # 检查创建时间
                created_str = task_data.get("created_at", "")
                if created_str:
                    created_date = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    )
                    if created_date < cutoff_date:
                        task_file.unlink()
                        cleaned_files.append(str(task_file))
            except (json.JSONDecodeError, KeyError, ValueError):
                # 如果文件损坏或格式错误，也清理
                task_file.unlink()
                cleaned_files.append(str(task_file))

    # 清理会话数据
    sessions_dir = data_dir / "sessions"
    if sessions_dir.exists():
        for session_file in sessions_dir.glob("*.json"):
            try:
                stat_info = session_file.stat()
                modified_date = datetime.fromtimestamp(stat_info.st_mtime)
                if modified_date < cutoff_date:
                    session_file.unlink()
                    cleaned_files.append(str(session_file))
            except Exception:
                pass

    return cleaned_files


def cleanup_logs(days_old=3):
    """清理旧的日志文件"""
    logs_dir = Path("logs")
    cutoff_date = datetime.now() - timedelta(days=days_old)

    cleaned_logs = []

    if logs_dir.exists():
        for log_file in logs_dir.glob("*.log"):
            try:
                stat_info = log_file.stat()
                modified_date = datetime.fromtimestamp(stat_info.st_mtime)
                if modified_date < cutoff_date:
                    log_file.unlink()
                    cleaned_logs.append(str(log_file))
            except Exception:
                pass

    return cleaned_logs


def cleanup_temp_files():
    """清理临时文件目录"""
    tmp_dir = Path("tmp")
    cleaned_tmp = []

    if tmp_dir.exists():
        for tmp_file in tmp_dir.iterdir():
            if tmp_file.is_file():
                try:
                    tmp_file.unlink()
                    cleaned_tmp.append(str(tmp_file))
                except Exception:
                    pass

    return cleaned_tmp


def main():
    """主清理函数"""
    print("开始数据清理...")

    # 清理7天前的数据
    cleaned_data = cleanup_old_data(days_old=7)
    print(f"清理了 {len(cleaned_data)} 个旧数据文件")

    # 清理3天前的日志
    cleaned_logs = cleanup_logs(days_old=3)
    print(f"清理了 {len(cleaned_logs)} 个旧日志文件")

    # 清理临时文件
    cleaned_tmp = cleanup_temp_files()
    print(f"清理了 {len(cleaned_tmp)} 个临时文件")

    # 保留必要的占位文件
    data_dir = Path("data")
    for subdir in ["tasks", "sessions"]:
        subdir_path = data_dir / subdir
        if subdir_path.exists():
            gitkeep = subdir_path / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()

    print("数据清理完成！")


if __name__ == "__main__":
    main()
