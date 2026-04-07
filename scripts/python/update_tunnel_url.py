#!/usr/bin/env python3
import os
import sys
from pathlib import Path


def update_tunnel_url(url=None):
    """更新隧道URL到文件，供隧道管理器使用"""
    if not url:
        # 尝试从当前localtunnel日志获取URL
        log_file = Path("logs/localtunnel.log")
        if log_file.exists():
            with open(log_file, "r") as f:
                for line in f:
                    if "your url is:" in line:
                        import re

                        match = re.search(r"https://[^\s]+", line)
                        if match:
                            url = match.group(0)
                            break

    if not url:
        print("❌ 无法获取隧道URL")
        print("请提供URL或检查localtunnel是否运行")
        return False

    # 写入文件
    url_file = Path("logs/current_tunnel_url.txt")
    url_file.parent.mkdir(exist_ok=True)

    with open(url_file, "w") as f:
        f.write(url)

    print(f"✅ 隧道URL已更新: {url}")
    print(f"文件: {url_file}")

    # 生成Feishu配置指南
    webhook_url = f"{url}/feishu/webhook/opencode"
    print("\n📋 Feishu事件订阅配置:")
    print("=" * 50)
    print(f"URL: {webhook_url}")
    print("\n请按以下步骤更新飞书开放平台配置:")
    print("1. 登录飞书开放平台 (https://open.feishu.cn)")
    print("2. 进入你的应用")
    print("3. 左侧菜单选择「事件订阅」")
    print("4. 在「请求地址」中输入上面的URL")
    print("5. 点击「保存」并验证")
    print("6. 确保已订阅事件: im.message.receive_v1")
    print("7. 发布新版本")
    print("\n💡 提示: 旧URL是4天前的，需要更新为新URL")

    return True


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    update_tunnel_url(url)
