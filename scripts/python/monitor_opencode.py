#!/usr/bin/env python3
"""
OpenCode CLI 状态监控器
实时监控 OpenCode 进程和会话状态
"""

import subprocess
import json
import time
import os
from datetime import datetime
from pathlib import Path


class OpenCodeMonitor:
    def __init__(self):
        self.opencode_dir = Path.home() / ".local/share/opencode"
        self.log_dir = self.opencode_dir / "log"

    def get_running_processes(self):
        """获取正在运行的 OpenCode 进程"""
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            processes = []
            for line in result.stdout.split("\n"):
                if "opencode" in line.lower() and "grep" not in line.lower():
                    parts = line.split()
                    if len(parts) >= 11:
                        pid = parts[1]
                        cpu = parts[2]
                        mem = parts[3]
                        time_str = parts[9]
                        cmd = " ".join(parts[10:])
                        processes.append(
                            {
                                "pid": pid,
                                "cpu": cpu,
                                "memory": mem,
                                "time": time_str,
                                "command": cmd[:100] + "..." if len(cmd) > 100 else cmd,
                            }
                        )
            return processes
        except Exception as e:
            return [{"error": str(e)}]

    def get_task_info(self):
        """获取任务信息"""
        ai_project_dir = Path("/home/user/workspace/opencode-feishu-bridge")
        tasks_dir = ai_project_dir / "data/tasks"

        tasks = []
        if tasks_dir.exists():
            for task_file in sorted(tasks_dir.glob("*.json"))[-10:]:  # 最近10个任务
                try:
                    with open(task_file, "r") as f:
                        task = json.load(f)
                        tasks.append(
                            {
                                "id": task.get("task_id", task_file.stem),
                                "status": task.get("status", "unknown"),
                                "text": task.get("parsed_text", "")[:50] + "...",
                                "updated": task.get("updated_at", "unknown"),
                            }
                        )
                except:
                    pass
        return tasks

    def get_recent_logs(self, lines=20):
        """获取最近的日志"""
        try:
            # 找到最新的日志文件
            log_files = sorted(self.log_dir.glob("*.log"))
            if not log_files:
                return []

            latest_log = log_files[-1]

            # 读取最后几行
            result = subprocess.run(
                ["tail", "-n", str(lines), str(latest_log)],
                capture_output=True,
                text=True,
            )
            return result.stdout.split("\n")
        except Exception as e:
            return [f"Error reading logs: {e}"]

    def display_status(self):
        """显示当前状态"""
        print("=" * 80)
        print(f"OpenCode CLI 状态监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()

        # 1. 运行中的进程
        print("🔄 运行中的 OpenCode 进程:")
        print("-" * 80)
        processes = self.get_running_processes()
        if processes:
            for i, proc in enumerate(processes[:10], 1):  # 显示前10个
                if "error" in proc:
                    print(f"  错误: {proc['error']}")
                else:
                    print(f"  {i}. PID: {proc['pid']}")
                    print(
                        f"     CPU: {proc['cpu']}% | 内存: {proc['memory']}% | 时间: {proc['time']}"
                    )
                    print(f"     命令: {proc['command']}")
                    print()
        else:
            print("  没有运行中的 OpenCode 进程")
        print()

        # 2. 最近任务
        print("📋 最近任务:")
        print("-" * 80)
        tasks = self.get_task_info()
        if tasks:
            for task in tasks:
                status_icon = {
                    "completed": "✅",
                    "running": "🔄",
                    "failed": "❌",
                    "pending": "⏳",
                    "researching": "🔍",
                }.get(task["status"], "❓")
                print(f"  {status_icon} {task['id']}")
                print(f"     状态: {task['status']}")
                print(f"     内容: {task['text']}")
                print()
        else:
            print("  没有任务记录")
        print()

        # 3. 最近日志
        print("📝 最近日志活动:")
        print("-" * 80)
        logs = self.get_recent_logs(10)
        for log in logs[-5:]:  # 显示最后5行
            if log.strip():
                print(f"  {log}")
        print()

        print("=" * 80)

    def watch(self, interval=5):
        """持续监控"""
        try:
            while True:
                os.system("clear" if os.name != "nt" else "cls")
                self.display_status()
                print(f"\n刷新间隔: {interval}秒 | 按 Ctrl+C 退出")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n监控已停止")


if __name__ == "__main__":
    import sys

    monitor = OpenCodeMonitor()

    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        # 持续监控模式
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        monitor.watch(interval)
    else:
        # 单次显示
        monitor.display_status()
