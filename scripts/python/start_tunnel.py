#!/usr/bin/env python3
"""
启动隧道管理器获取公网URL
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 加载环境变量
feishu_env = project_root.parent / "VibeBridge" / ".secrets" / "feishu.env"
api_keys_env = project_root.parent / "VibeBridge" / ".secrets" / "api-keys.env"

if feishu_env.exists():
    with open(feishu_env, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()
                print(f"Set {key.strip()}=****")

if api_keys_env.exists():
    with open(api_keys_env, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()
                if "SECRET" in key or "KEY" in key or "TOKEN" in key:
                    print(f"Set {key.strip()}=****")
                else:
                    print(f"Set {key.strip()}={value.strip()}")

# 导入隧道管理器
try:
    from src.legacy.tunnel_manager import TunnelManager
except ImportError as e:
    print(f"导入隧道管理器失败: {e}")
    sys.exit(1)


async def main():
    """主函数"""
    print("=== 启动隧道管理器 ===")
    print("获取公网URL...")

    manager = TunnelManager()

    # 尝试启动隧道
    try:
        print("启动隧道...")
        await manager.start_tunnel()

        # 等待几秒让隧道建立
        await asyncio.sleep(3)

        if manager.current_url:
            print(f"✅ 隧道URL: {manager.current_url}")
            print(f"   OpenCode Webhook: {manager.current_url}/feishu/webhook/opencode")

            # 尝试通知Feishu
            print("发送URL通知到Feishu...")
            success = await manager.notify_feishu_url_change(manager.current_url)
            if success:
                print("✅ URL已通知Feishu")
            else:
                print("⚠️  URL通知失败，请手动更新Feishu后台配置")

            # 保持运行
            print("\n隧道运行中，按Ctrl+C停止...")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n停止隧道...")
                manager.stop_tunnel()
        else:
            print("❌ 无法获取隧道URL")

    except Exception as e:
        print(f"❌ 隧道启动失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
