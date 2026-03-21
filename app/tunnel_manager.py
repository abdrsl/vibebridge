#!/usr/bin/env python3
"""
Tunnel Manager - Manages SSH tunnel to serveo.net and notifies Feishu on URL changes.
"""

import asyncio
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx

# psutil is optional for process checking
PSUTIL_AVAILABLE = False
psutil = None
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    print("⚠️ psutil not installed, using basic process checking")

from app.feishu_client import FeishuClient

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
        """Handle detection of a new tunnel URL."""
        old_url = self.current_url

        if old_url == new_url:
            print(f"🔁 Same URL, no change: {new_url}")
            return

        print(f"🔄 New tunnel URL detected: {new_url}")
        print(f"   Old URL: {old_url}")

        # Save the new URL
        self.save_url(new_url)

        # Send notification to Feishu
        await self.notify_url_change(old_url, new_url)

    async def notify_url_change(self, old_url: Optional[str], new_url: str):
        """Send notification to Feishu about URL change."""
        print(f"📨 Sending URL change notification to Feishu...")

        # Build message
        message_lines = [
            "🚨 **隧道 URL 已更新**",
            "",
            f"**新隧道 URL:**",
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
                print(f"✅ URL change notification sent to Feishu")
            else:
                # Fallback to text message
                print(f"⚠️ Card failed, falling back to text message")
                text_result = await self.feishu_client.send_text_message(
                    receive_id=None, text=message
                )
                if text_result and text_result.get("code") == 0:
                    print(f"✅ Text notification sent to Feishu")
                else:
                    print(f"❌ Failed to send notification: {text_result}")

        except Exception as e:
            print(f"❌ Error sending notification: {e}")

    async def start_tunnel(self):
        """Start the SSH tunnel to serveo.net."""
        # Kill any existing tunnel processes
        self.stop_tunnel()

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

        print("✅ Tunnel process started")
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

    async def health_check(self) -> bool:
        """Check if tunnel is healthy."""
        if not self.current_url:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.current_url}/health")
                return response.status_code == 200
        except Exception:
            return False

    def check_existing_tunnel(self) -> bool:
        """Check if a tunnel process is already running."""
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
            import subprocess

            try:
                result = subprocess.run(
                    ["pgrep", "-f", "ssh.*serveo.net"], capture_output=True, text=True
                )
                return result.returncode == 0 and result.stdout.strip() != ""
            except Exception:
                pass

        return False

    async def extract_url_from_log_file(self) -> Optional[str]:
        """Extract URL from existing tunnel log file."""
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
            if await self.health_check():
                print(f"✅ Last URL is still active: {last_url}")
                # Still notify current URL
                await self.notify_url_change(None, last_url)
        
        # Check if tunnel is already running
        existing_tunnel = self.check_existing_tunnel()
        if existing_tunnel:
            print("🔍 Existing tunnel process detected")

            # Try to extract URL from log file
            current_url = await self.extract_url_from_log_file()
            if current_url:
                print(f"📡 Found URL from logs: {current_url}")
                self.save_url(current_url)
                if last_url != current_url:
                    await self.notify_url_change(last_url, current_url)
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
                    is_healthy = await self.health_check()
                    if not is_healthy:
                        print("⚠️ Tunnel URL not responding, checking tunnel process...")
                        # Check if tunnel process is still alive
                        if not self.check_existing_tunnel():
                            print("❌ Tunnel process dead, restarting...")
                            await self.start_tunnel()
                        else:
                            print("🔧 Tunnel process alive but URL not responding, may be temporary")
                
                # If we have a tunnel process, check if it died
                if self.tunnel_process and self.tunnel_process.poll() is not None:
                    print("⚠️ Managed tunnel process died, restarting...")
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
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the manager
    await manager.run()


if __name__ == "__main__":
    asyncio.run(main())
