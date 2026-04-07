#!/usr/bin/env python3
"""
Feishu模式切换CLI工具
支持命令行切换WebSocket和Webhook模式
"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到路径
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

from src.legacy.config_manager import get_config_manager


def print_colored(text, color_code):
    """打印带颜色的文本"""
    print(f"\033[{color_code}m{text}\033[0m")


def print_success(text):
    """打印成功消息"""
    print_colored(f"✅ {text}", "32")  # 绿色


def print_error(text):
    """打印错误消息"""
    print_colored(f"❌ {text}", "31")  # 红色


def print_info(text):
    """打印信息消息"""
    print_colored(f"ℹ️  {text}", "36")  # 青色


def print_warning(text):
    """打印警告消息"""
    print_colored(f"⚠️  {text}", "33")  # 黄色


def show_current_status(config):
    """显示当前状态"""
    current_mode = config.get_feishu_mode()
    websocket_enabled = config.is_websocket_enabled()

    print("\n" + "=" * 50)
    print_info("📡 Feishu事件接收模式状态")
    print("=" * 50)

    if current_mode == "websocket":
        print_success(f"当前模式: WebSocket长连接")
        print("   状态: 🟢 启用")
        print("   特点: 实时接收，无需公网IP")
        print("   说明: 使用飞书Event Subscription 2.0")
    else:
        print_success(f"当前模式: Webhook回调")
        print("   状态: 🟡 启用")
        print("   特点: 传统方式，需要公网URL")
        print("   说明: 使用飞书Event Subscription 1.0")

    print(f"\n📊 配置摘要:")
    summary = config.get_config_summary()
    for key, value in summary.items():
        print(f"   {key}: {value}")

    print("\n💡 使用说明:")
    print("   飞书切换: 发送 'websocket模式' 或 'webhook模式'")
    print("   CLI切换: python scripts/switch_feishu_mode.py [websocket|webhook]")


def switch_mode(config, new_mode):
    """切换模式"""
    current_mode = config.get_feishu_mode()

    if new_mode not in ["websocket", "webhook"]:
        print_error(f"无效模式: {new_mode}")
        print_info("可用模式: websocket, webhook")
        return False

    if current_mode == new_mode:
        print_warning(f"已经是 {new_mode} 模式，无需切换")
        return True

    print_info(f"正在从 {current_mode} 切换到 {new_mode} 模式...")

    # 执行切换
    success = config.set_feishu_mode(new_mode, save=True)

    if success:
        print_success(f"✅ 模式切换成功!")

        # 显示切换后状态
        if new_mode == "websocket":
            print_info("🔄 需要重启服务器以使WebSocket生效")
            print("   运行: ./manage.sh restart")
        else:
            print_info("🌐 请配置飞书控制台回调URL:")
            print("   /feishu/webhook/opencode")

        return True
    else:
        print_error("❌ 模式切换失败")
        return False


def main():
    """主函数"""
    if len(sys.argv) > 2:
        print_error("参数过多")
        print_info(
            "用法: python scripts/switch_feishu_mode.py [websocket|webhook|status]"
        )
        return 1

    config = get_config_manager()

    if len(sys.argv) == 1:
        # 无参数：显示状态
        show_current_status(config)
        return 0

    command = sys.argv[1].lower()

    if command == "status":
        show_current_status(config)
    elif command in ["websocket", "webhook"]:
        if switch_mode(config, command):
            # 显示切换后状态
            print("\n" + "-" * 40)
            show_current_status(config)
            return 0
        else:
            return 1
    else:
        print_error(f"未知命令: {command}")
        print_info("可用命令: status, websocket, webhook")
        return 1

    return 0


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n\n👋 操作已取消")
        exit(0)
    except Exception as e:
        print_error(f"程序出错: {e}")
        exit(1)
