#!/usr/bin/env python3
"""
隧道监控服务
监控隧道URL变化并自动通知Feishu
"""

import os
import sys
import time
import json
import asyncio
import requests
from pathlib import Path
from typing import Optional

# 添加项目目录到路径
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

from src.legacy.feishu_client import feishu_client


class TunnelMonitor:
    """隧道监控器"""

    def __init__(self, check_interval: int = 30):
        """
        初始化监控器

        Args:
            check_interval: 检查间隔（秒）
        """
        self.check_interval = check_interval
        self.project_dir = Path(__file__).parent.parent
        self.url_file = self.project_dir / "logs" / "current_tunnel_url.txt"
        self.chat_id_file = self.project_dir / "logs" / "default_chat_id.txt"
        self.last_url: Optional[str] = None
        self.running = False

        # 加载默认chat_id
        self.default_chat_id = self._load_default_chat_id()

        # 加载上次URL
        self._load_last_url()

    def _load_default_chat_id(self) -> Optional[str]:
        """加载默认chat_id"""
        # 从环境变量
        chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID")
        if chat_id:
            return chat_id

        # 从文件
        if self.chat_id_file.exists():
            return self.chat_id_file.read_text().strip()

        # 从session记录中查找
        sessions_dir = self.project_dir / "data" / "sessions"
        if sessions_dir.exists():
            try:
                # 获取最近使用的chat_id
                session_files = sorted(
                    sessions_dir.glob("*.json"),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True,
                )
                if session_files:
                    import json

                    with open(session_files[0], "r") as f:
                        data = json.load(f)
                        chat_id = data.get("chat_id")
                        if chat_id:
                            # 保存到文件
                            self.chat_id_file.write_text(chat_id)
                            return chat_id
            except:
                pass

        return None

    def _load_last_url(self):
        """加载上次URL"""
        if self.url_file.exists():
            self.last_url = self.url_file.read_text().strip()
            print(f"[TunnelMonitor] 上次URL: {self.last_url}")

    def _get_current_url(self) -> Optional[str]:
        """获取当前隧道URL"""
        if self.url_file.exists():
            return self.url_file.read_text().strip()
        return None

    async def _send_url_notification(self, url: str, is_update: bool = True):
        """
        发送URL变更通知到Feishu

        Args:
            url: 新的URL
            is_update: 是否是更新（True）还是首次启动（False）
        """
        if not self.default_chat_id:
            print("[TunnelMonitor] ⚠️ 未设置默认chat_id，无法发送通知")
            print("[TunnelMonitor] 请设置FEISHU_DEFAULT_CHAT_ID环境变量")
            return

        try:
            if is_update:
                # URL变更通知
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": "🔄 公网地址已更新"},
                        "template": "blue",
                    },
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"**新的Webhook地址：**\n```\n{url}/feishu/webhook/opencode\n```",
                        },
                        {
                            "tag": "note",
                            "elements": [
                                {
                                    "tag": "plain_text",
                                    "content": "⏰ 更新时间: "
                                    + time.strftime("%Y-%m-%d %H:%M:%S"),
                                }
                            ],
                        },
                    ],
                }

                result = await feishu_client.send_interactive_card(
                    self.default_chat_id, card
                )

                if result.get("code") == 0:
                    print(f"[TunnelMonitor] ✅ URL变更通知已发送到Feishu")
                else:
                    print(f"[TunnelMonitor] ❌ 发送通知失败: {result}")
            else:
                # 首次启动通知
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": "🚀 服务已启动"},
                        "template": "green",
                    },
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"**Webhook地址：**\n```\n{url}/feishu/webhook/opencode\n```\n\n**快捷指令：**\n• 清空session - 清空当前会话\n• kimi - 切换到Kimi模型\n• deepseek - 切换到Deepseek模型\n• git 提交 - 执行Git提交\n• 启动服务器 - 启动本地服务器",
                        }
                    ],
                }

                result = await feishu_client.send_interactive_card(
                    self.default_chat_id, card
                )

                if result.get("code") == 0:
                    print(f"[TunnelMonitor] ✅ 启动通知已发送到Feishu")
                else:
                    print(f"[TunnelMonitor] ❌ 发送通知失败: {result}")

        except Exception as e:
            print(f"[TunnelMonitor] ❌ 发送通知时出错: {e}")

    async def _check_tunnel_health(self, url: str) -> bool:
        """检查隧道健康状态"""
        try:
            import time

            start = time.time()
            response = requests.get(f"{url}/", timeout=5)
            elapsed = time.time() - start
            print(
                f"[TunnelMonitor] Health check: {url}/ -> status={response.status_code}, elapsed={elapsed:.2f}s",
                flush=True,
            )
            result = response.status_code == 200 and '"status":"ok"' in response.text
            print(f"[TunnelMonitor] Health check result: {result}", flush=True)
            return result
        except Exception as e:
            print(f"[TunnelMonitor] Health check error: {e}", flush=True)
            return False

    async def run(self):
        """运行监控循环"""
        print("=" * 70)
        print("🔄 隧道监控服务已启动")
        print("=" * 70)
        print(f"\n📊 配置信息:")
        print(f"   检查间隔: {self.check_interval}秒")
        print(f"   默认Chat ID: {self.default_chat_id or '未设置'}")
        print(f"   URL文件: {self.url_file}")
        print()

        self.running = True
        is_first_run = True
        iteration = 0

        while self.running:
            try:
                current_url = self._get_current_url()
                iteration += 1
                print(
                    f"[TunnelMonitor] 检查周期 #{iteration}，当前URL: {current_url or '无'}"
                )

                if current_url:
                    # 检查是否是新URL
                    if current_url != self.last_url:
                        print(
                            f"[TunnelMonitor] 🔄 URL变更: {self.last_url} -> {current_url}"
                        )

                        # 检查新URL是否可用
                        if await self._check_tunnel_health(current_url):
                            await self._send_url_notification(
                                current_url, is_update=not is_first_run
                            )
                            self.last_url = current_url
                            is_first_run = False
                        else:
                            print(f"[TunnelMonitor] ⚠️ 新URL暂时不可用，等待下次检查")
                    else:
                        # 定期检查URL是否仍然可用
                        if not await self._check_tunnel_health(current_url):
                            print(f"[TunnelMonitor] ⚠️ 当前URL不可用，等待自动切换...")
                else:
                    if self.last_url:
                        print(f"[TunnelMonitor] ⚠️ URL文件不存在，隧道可能已停止")
                        self.last_url = None

                await asyncio.sleep(self.check_interval)

            except Exception as e:
                print(f"[TunnelMonitor] ❌ 监控循环出错: {e}")
                await asyncio.sleep(self.check_interval)

    def stop(self):
        """停止监控"""
        self.running = False
        print("[TunnelMonitor] 🛑 监控服务已停止")


async def main():
    """主函数"""
    monitor = TunnelMonitor(check_interval=30)

    try:
        await monitor.run()
    except KeyboardInterrupt:
        monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
