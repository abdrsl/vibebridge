#!/usr/bin/env python3
"""
Tunnel Manager - Manages SSH tunnel to serveo.net and notifies Feishu on URL changes.
"""

import asyncio
import os
import re
import signal
import subprocess
from pathlib import Path
from typing import Optional

import httpx

from .feishu_client import FeishuClient

# psutil is optional for process checking
PSUTIL_AVAILABLE = False
psutil = None
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    print("⚠️ psutil not installed, using basic process checking")

PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
TUNNEL_LOG = LOG_DIR / "tunnel.log"
LAST_URL_FILE = LOG_DIR / "last_tunnel_url.txt"


class TunnelManager:
    def __init__(self):
        self.tunnel_process: Optional[subprocess.Popen] = None
        self.current_url: Optional[str] = None
        self.feishu_client = FeishuClient()
        self.running = False
        self.tunnel_type = os.getenv("TUNNEL_TYPE", "ssh").lower()  # ssh or ngrok

        # URL稳定性跟踪
        self.url_candidate: Optional[str] = None
        self.url_candidate_time: float = 0
        self.url_stable_threshold: float = 30.0  # 秒，URL需要稳定至少30秒才通知
        self.last_notified_url: Optional[str] = None
        self.consecutive_failures: int = 0
        self.max_consecutive_failures: int = 3  # 最大连续失败次数

        # Ensure log directory exists
        LOG_DIR.mkdir(exist_ok=True)

    def load_last_url(self) -> Optional[str]:
        """Load the last known tunnel URL from file."""
        if LAST_URL_FILE.exists():
            try:
                with open(LAST_URL_FILE, "r") as f:
                    url = f.read().strip()
                    if url:
                        self.current_url = url
                        return url
            except Exception:
                pass
        return None

    def save_url(self, url: str):
        """Save tunnel URL to file."""
        self.current_url = url
        try:
            with open(LAST_URL_FILE, "w") as f:
                f.write(url)
            print(f"📝 Saved tunnel URL: {url}")
        except Exception as e:
            print(f"❌ Failed to save URL: {e}")

    async def extract_url_from_log(self, log_line: str) -> Optional[str]:
        """Extract tunnel URL from log line."""
        # Pattern: https://xxxxxx-xx-xx-xx-xx.serveousercontent.com
        patterns = [
            r"https://[a-zA-Z0-9-]+\.serveousercontent\.com",
            r"Forwarding HTTP traffic from (https://[^\s]+)",
            r"https://[a-zA-Z0-9-]+-\d+-\d+-\d+-\d+\.serveousercontent\.com",
            # ngrok patterns
            r"https://[a-zA-Z0-9-]+\.ngrok(-free)?\.dev",
            r"started tunnel.*url=(https://[^\s]+)",
            r"url=([^\s]+\.ngrok(-free)?\.dev)",
            # localtunnel patterns
            r"https://[a-zA-Z0-9-]+\.loca\.lt",
            r"your url is: (https://[^\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, log_line)
            if match:
                url = match.group(0)
                if "Forwarding HTTP traffic from" in log_line:
                    # Extract just the URL part
                    url_match = re.search(r"https://[^\s]+", log_line)
                    if url_match:
                        url = url_match.group(0)
                # For ngrok "url=" format, extract the URL
                if "url=" in log_line and match.group(1):
                    url = match.group(1)
                return url

        return None

    async def monitor_tunnel_output(self):
        """Monitor tunnel process output for URL changes."""
        if not self.tunnel_process or not self.tunnel_process.stdout:
            return

        print("🔍 Monitoring tunnel output...")

        # Read from both stdout and stderr
        stdout = self.tunnel_process.stdout
        stderr = self.tunnel_process.stderr

        while self.running and self.tunnel_process.poll() is None:
            try:
                # Read lines from stdout
                line = stdout.readline()
                if line:
                    line = line.decode("utf-8", errors="ignore").strip()
                    print(f"[TUNNEL] {line}")

                    # Check for URL in line
                    url = await self.extract_url_from_log(line)
                    if url:
                        await self.handle_new_url(url)

                # Also check stderr
                if stderr:
                    try:
                        stderr_line = stderr.readline()
                        if stderr_line:
                            stderr_line = stderr_line.decode(
                                "utf-8", errors="ignore"
                            ).strip()
                            print(f"[TUNNEL-ERR] {stderr_line}")
                    except Exception:
                        pass

                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"❌ Error reading tunnel output: {e}")
                await asyncio.sleep(1)

    async def handle_new_url(self, new_url: str):
        """Handle detection of a new tunnel URL with stability checking."""
        import time

        old_url = self.current_url

        if old_url == new_url:
            print(f"🔁 Same URL, no change: {new_url}")
            return

        print(f"🔄 New tunnel URL candidate detected: {new_url}")
        print(f"   Old URL: {old_url}")
        print(f"   Last notified URL: {self.last_notified_url}")

        # 如果新URL与上次通知的URL相同，且时间较短，忽略
        if self.last_notified_url == new_url:
            print("📝 URL already notified recently, ignoring")
            return

        # 检查URL候选
        current_time = time.time()

        if self.url_candidate != new_url:
            # 新的候选URL
            self.url_candidate = new_url
            self.url_candidate_time = current_time
            print("📝 New URL candidate registered, waiting for stability...")
        else:
            # 同一个候选URL，检查是否稳定足够长时间
            elapsed = current_time - self.url_candidate_time
            if elapsed >= self.url_stable_threshold:
                print(f"✅ URL candidate stable for {elapsed:.1f}s, accepting")

                # 更新当前URL
                self.current_url = new_url
                self.save_url(new_url)

                # 发送通知
                await self.notify_url_change(old_url, new_url)

                # 重置候选
                self.url_candidate = None
                self.url_candidate_time = 0
                self.last_notified_url = new_url
                self.consecutive_failures = 0  # 重置失败计数器
            else:
                print(
                    f"⏳ URL candidate not stable yet: "
                    f"{elapsed:.1f}/{self.url_stable_threshold}s"
                )

    async def notify_url_change(self, old_url: Optional[str], new_url: str):
        """Send notification to Feishu about URL change."""
        print("📨 Sending URL change notification to Feishu...")

        # Build message
        message_lines = [
            "🚨 **隧道 URL 已更新**",
            "",
            "**新隧道 URL:**",
            f"`{new_url}`",
            "",
            "**Webhook 端点:**",
            f"- OpenCode: `{new_url}/feishu/webhook/opencode`",
            f"- 标准: `{new_url}/feishu/webhook`",
            "",
            "**需要手动更新:**",
            "1. 登录飞书开发者后台",
            "2. 找到机器人配置",
            "3. 更新 webhook URL",
            "4. 保存配置",
        ]

        if old_url:
            message_lines.insert(2, f"**旧 URL:** `{old_url}`")
            message_lines.insert(3, "")

        message = "\n".join(message_lines)

        try:
            # Try to send as interactive card first
            card = {
                "config": {"wide_screen_mode": True},
                "elements": [
                    {"tag": "markdown", "content": message},
                    {"tag": "hr"},
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "📋 复制新 URL",
                                },
                                "type": "primary",
                                "multi_url": {
                                    "url": new_url,
                                    "android_url": "",
                                    "ios_url": "",
                                    "pc_url": "",
                                },
                            }
                        ],
                    },
                ],
                "header": {
                    "title": {"tag": "plain_text", "content": "🔄 隧道 URL 更新"},
                    "template": "blue",
                },
            }

            result = await self.feishu_client.send_interactive_card(
                receive_id=None,  # Will use default chat ID
                card=card,
            )

            if result and result.get("code") == 0:
                print("✅ URL change notification sent to Feishu")
                # 更新最后通知的URL
                self.last_notified_url = new_url
            else:
                # Fallback to text message
                print("⚠️ Card failed, falling back to text message")
                text_result = await self.feishu_client.send_text_message(
                    receive_id=None, text=message
                )
                if text_result and text_result.get("code") == 0:
                    print("✅ Text notification sent to Feishu")
                    # 更新最后通知的URL
                    self.last_notified_url = new_url
                else:
                    print(f"❌ Failed to send notification: {text_result}")

        except Exception as e:
            print(f"❌ Error sending notification: {e}")

    async def start_tunnel(self):
        """启动隧道，支持故障转移和重试。"""
        # 停止任何现有隧道进程
        self.stop_tunnel()

        # 重置状态（新隧道启动）
        self.consecutive_failures = 0
        self.url_candidate = None
        self.url_candidate_time = 0

        print(f"🔄 Starting tunnel with type: {self.tunnel_type}")

        # 根据配置的隧道类型启动
        if self.tunnel_type == "ngrok":
            try:
                return await self.start_ngrok_tunnel()
            except Exception as e:
                print(f"❌ ngrok tunnel failed: {e}")
                print("🔄 Falling back to SSH tunnel...")
                return await self.start_ssh_tunnel_with_fallback()
        else:
            # SSH是默认类型，但有故障转移
            return await self.start_ssh_tunnel_with_fallback()

    async def start_ssh_tunnel_with_fallback(self):
        """启动SSH隧道，失败时回退到localtunnel。"""
        try:
            print("🔧 Attempting SSH tunnel to serveo.net...")
            return await self.start_ssh_tunnel()
        except Exception as e:
            print(f"❌ SSH tunnel failed: {e}")
            print("🔄 Falling back to localtunnel...")
            try:
                return await self.start_localtunnel_tunnel()
            except Exception as e2:
                print(f"❌ Localtunnel also failed: {e2}")
                print("💥 All tunnel options failed. Service will run locally only.")
                # 设置一个虚拟URL用于健康检查
                self.current_url = "http://localhost:8000"
                return None

    async def start_ssh_tunnel(self):
        """Start the SSH tunnel to serveo.net."""
        print("🚀 Starting SSH tunnel to serveo.net...")

        # Build command
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-R",
            "80:localhost:8000",
            "serveo.net",
        ]

        # Start process with pipes
        self.tunnel_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
        )

        self.running = True

        # Start monitoring
        asyncio.create_task(self.monitor_tunnel_output())

        print("✅ SSH tunnel process started")
        return self.tunnel_process

    async def start_localtunnel_tunnel(self):
        """Start localtunnel tunnel."""
        print("🚀 Starting localtunnel tunnel...")

        # Check if npx/local command is available
        try:
            subprocess.run(["which", "npx"], capture_output=True, check=True)
        except Exception as e:
            print(f"❌ npx not available: {e}")
            raise Exception("npx not available for localtunnel") from e

        # Build command - use --print-url to get the URL directly
        cmd = ["npx", "localtunnel", "--port", "8000", "--print-url"]

        # Start process with pipes
        self.tunnel_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,  # Use text mode for easier output parsing
            universal_newlines=True,
        )

        self.running = True

        # Start monitoring
        asyncio.create_task(self.monitor_tunnel_output())

        print("✅ Localtunnel process started")
        return self.tunnel_process

    async def start_ngrok_tunnel(self):
        """Start ngrok tunnel."""
        print("🚀 Starting ngrok tunnel...")

        # Check if ngrok is available
        try:
            subprocess.run(["ngrok", "--version"], capture_output=True, check=True)
        except Exception as e:
            print(f"❌ ngrok not available: {e}")
            print("🔄 Falling back to SSH tunnel...")
            return await self.start_ssh_tunnel()

        # Build ngrok command - use 127.0.0.1 to avoid IPv6 issues
        cmd = [
            "ngrok",
            "http",
            "127.0.0.1:8000",
            "--log=stdout",
            "--pooling-enabled",
            "--inspect=false",
        ]

        # Start process with pipes
        self.tunnel_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
        )

        self.running = True

        # Start monitoring
        asyncio.create_task(self.monitor_tunnel_output())

        # Wait a moment for ngrok to start
        await asyncio.sleep(3)

        # Try to get URL from ngrok API with retries
        ngrok_url = None
        max_retries = 5
        for attempt in range(max_retries):
            ngrok_url = await self.get_ngrok_url()
            if ngrok_url:
                break
            if attempt < max_retries - 1:
                print(
                    f"⏳ Waiting for ngrok API (attempt {attempt + 1}/{max_retries})..."
                )
                await asyncio.sleep(2)

        if ngrok_url:
            print(f"✅ ngrok tunnel started: {ngrok_url}")
            await self.handle_new_url(ngrok_url)
        else:
            print(
                "✅ ngrok tunnel process started (URL not yet available, "
                "will monitor logs)"
            )

        return self.tunnel_process

    def stop_tunnel(self):
        """Stop the tunnel process."""
        self.running = False

        if self.tunnel_process:
            print("🛑 Stopping tunnel process...")
            try:
                # Try graceful termination
                self.tunnel_process.terminate()
                try:
                    self.tunnel_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if not responding
                    self.tunnel_process.kill()
                    self.tunnel_process.wait()
            except Exception as e:
                print(f"❌ Error stopping tunnel: {e}")

            self.tunnel_process = None

    async def health_check(self) -> tuple[bool, str]:
        """检查隧道健康状况，返回(是否健康, 诊断信息)。"""
        if not self.current_url:
            return False, "No tunnel URL available"

        # 测试GET请求
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 测试健康端点
                get_response = await client.get(f"{self.current_url}/health")
                if get_response.status_code != 200:
                    return False, f"GET /health returned {get_response.status_code}"

                # 测试POST请求（模拟webhook调用）
                post_response = await client.post(
                    f"{self.current_url}/feishu/webhook/opencode",
                    json={
                        "schema": "2.0",
                        "header": {
                            "event_id": "tunnel_health_check",
                            "event_type": "im.message.receive_v1",
                            "create_time": "1775655000000",
                            "token": "health_check",
                            "app_id": "cli_xxxxxxxxxxxxxxxx",
                            "tenant_key": "REDACTED_TENANT_KEY",
                        },
                        "event": {
                            "sender": {"sender_id": {"open_id": "test_user"}},
                            "message": {
                                "message_id": "om_health_check",
                                "chat_id": "oc_health_check",
                                "content": '{"text": "健康检查"}',
                            },
                        },
                    },
                    timeout=15.0,
                )

                # POST请求应该返回200或包含错误信息的响应
                if post_response.status_code not in [200, 400, 403]:
                    return (
                        False,
                        f"POST /feishu/webhook/opencode returned "
                        f"{post_response.status_code}",
                    )

                return (
                    True,
                    f"Tunnel healthy: GET={get_response.status_code}, "
                    f"POST={post_response.status_code}",
                )

        except httpx.TimeoutException:
            return False, "Tunnel timeout (requests taking too long)"
        except httpx.ConnectError:
            return False, "Connection refused (tunnel may be down)"
        except Exception as e:
            return False, f"Health check error: {e}"

    async def get_ngrok_url(self) -> Optional[str]:
        """Get ngrok tunnel URL from ngrok API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try to get tunnel info from ngrok API
                response = await client.get("http://localhost:4040/api/tunnels")
                if response.status_code == 200:
                    data = response.json()
                    tunnels = data.get("tunnels", [])
                    for tunnel in tunnels:
                        if tunnel.get("proto") == "https":
                            public_url = tunnel.get("public_url")
                            if public_url:
                                return public_url
        except Exception as e:
            print(f"⚠️ Could not get ngrok URL from API: {e}")

        return None

    def check_existing_tunnel(self) -> bool:
        """Check if a tunnel process is already running."""
        if self.tunnel_type == "ngrok":
            return self.check_ngrok_process()
        else:
            return self.check_ssh_process()

    def check_ssh_process(self) -> bool:
        """Check if SSH tunnel process is running."""
        if PSUTIL_AVAILABLE and psutil:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info["cmdline"]
                    if (
                        cmdline
                        and "ssh" in cmdline
                        and "serveo.net" in " ".join(cmdline)
                    ):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        else:
            # Fallback using pgrep
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "ssh.*serveo.net"], capture_output=True, text=True
                )
                return result.returncode == 0 and result.stdout.strip() != ""
            except Exception:
                pass
        return False

    def check_ngrok_process(self) -> bool:
        """Check if ngrok process is running."""
        if PSUTIL_AVAILABLE and psutil:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info["cmdline"]
                    if cmdline and "ngrok" in cmdline and "http" in " ".join(cmdline):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        else:
            # Fallback using pgrep
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "ngrok.*http"], capture_output=True, text=True
                )
                return result.returncode == 0 and result.stdout.strip() != ""
            except Exception:
                pass
        return False

    async def extract_url_from_log_file(self) -> Optional[str]:
        """Extract URL from existing tunnel log file."""
        # For ngrok, try to get URL from API first
        if self.tunnel_type == "ngrok":
            ngrok_url = await self.get_ngrok_url()
            if ngrok_url:
                return ngrok_url

        # Fallback to reading log file
        if not TUNNEL_LOG.exists():
            return None

        try:
            with open(TUNNEL_LOG, "r") as f:
                # Read last few lines
                lines = f.readlines()[-20:]  # Last 20 lines
                for line in reversed(lines):
                    url = await self.extract_url_from_log(line)
                    if url:
                        return url
        except Exception as e:
            print(f"❌ Error reading tunnel log: {e}")

        return None

    async def run(self):
        """Main entry point - start and manage tunnel."""
        # Load last known URL
        last_url = self.load_last_url()
        if last_url:
            print(f"📖 Last tunnel URL: {last_url}")

            # Check if last URL still works
            is_healthy, health_msg = await self.health_check()
            if is_healthy:
                print(f"✅ Last URL is still active: {last_url}")
                print(f"   Health check: {health_msg}")
                # 设置last_notified_url但不发送通知
                self.last_notified_url = last_url
                print(f"📝 Set last_notified_url to: {last_url}")
            else:
                print(f"⚠️ Last URL not healthy: {health_msg}")

        # Check if tunnel is already running
        existing_tunnel = self.check_existing_tunnel()
        if existing_tunnel:
            print("🔍 Existing tunnel process detected")

            # Try to extract URL from log file
            current_url = await self.extract_url_from_log_file()
            if current_url:
                print(f"📡 Found URL from logs: {current_url}")
                # 使用稳定性检查逻辑处理URL
                await self.handle_new_url(current_url)
            else:
                print("⚠️ Could not extract URL from logs")

        # Start new tunnel if not already running
        if not existing_tunnel:
            print("🚀 No existing tunnel, starting new one...")
            await self.start_tunnel()
        else:
            print("👂 Monitoring existing tunnel...")
            self.running = True  # Set running flag for monitoring

        # Keep running and monitor
        try:
            while self.running:
                await asyncio.sleep(5)  # Check every 5 seconds

                # Check tunnel health
                if self.current_url:
                    is_healthy, health_msg = await self.health_check()
                    if not is_healthy:
                        self.consecutive_failures += 1
                        print(
                            f"⚠️ Tunnel health check failed "
                            f"({self.consecutive_failures}/{self.max_consecutive_failures}): "
                            f"{health_msg}"
                        )

                        # 检查是否达到最大失败次数
                        if self.consecutive_failures >= self.max_consecutive_failures:
                            print(
                                f"❌ Max consecutive failures reached, checking tunnel process..."
                            )
                            # Check if tunnel process is still alive
                            if not self.check_existing_tunnel():
                                print("❌ Tunnel process dead, restarting...")
                                await self.start_tunnel()
                                self.consecutive_failures = 0
                            else:
                                print(
                                    f"🔧 Tunnel process alive but unhealthy, will keep trying"
                                )
                        else:
                            print(
                                f"⏳ Health check failed, will retry (failure #{self.consecutive_failures})"
                            )
                    else:
                        # 健康检查成功，重置失败计数器
                        if self.consecutive_failures > 0:
                            print(
                                f"✅ Tunnel health restored after {self.consecutive_failures} failures"
                            )
                            self.consecutive_failures = 0

                        # 定期打印健康状态（每30秒一次）
                        import time

                        if int(time.time()) % 30 == 0:  # 每30秒打印一次
                            print(f"✅ Tunnel healthy: {health_msg}")

                # If we have a tunnel process, check if it died
                if self.tunnel_process and self.tunnel_process.poll() is not None:
                    print("⚠️ Managed tunnel process died, restarting...")
                    # 重置状态
                    self.consecutive_failures = 0
                    self.url_candidate = None
                    self.url_candidate_time = 0
                    await self.start_tunnel()

        except KeyboardInterrupt:
            print("\n🛑 Received interrupt, shutting down...")
        finally:
            self.stop_tunnel()


async def main():
    """Main function."""
    manager = TunnelManager()

    # Handle signals
    def signal_handler(signum, frame):
        print(f"\n📡 Received signal {signum}, shutting down...")
        manager.stop_tunnel()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the manager
    await manager.run()


if __name__ == "__main__":
    asyncio.run(main())
