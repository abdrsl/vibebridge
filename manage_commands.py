#!/usr/bin/env python3
"""
自定义指令管理工具
用于添加、删除、查看和管理自定义指令
"""

import json
import sys
from pathlib import Path


def load_commands():
    """加载指令配置"""
    config_path = Path(__file__).parent / "config" / "commands.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"commands": {}, "models": {}}


def save_commands(config):
    """保存指令配置"""
    config_path = Path(__file__).parent / "config" / "commands.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"✅ 配置已保存到 {config_path}")


def list_commands(config):
    """列出所有指令"""
    commands = config.get("commands", {})
    if not commands:
        print("\n📋 当前没有自定义指令")
        return

    print("\n📋 自定义指令列表:")
    print("=" * 70)
    for name, cmd in commands.items():
        print(f"\n🔹 {name}")
        print(f"   动作: {cmd.get('action', 'N/A')}")
        print(f"   描述: {cmd.get('description', 'N/A')}")
        print(f"   需要确认: {'是' if cmd.get('confirm', False) else '否'}")
        if cmd.get("model"):
            print(f"   模型: {cmd['model']}")
    print("\n" + "=" * 70)


def add_command(config):
    """添加新指令"""
    print("\n➕ 添加新指令")
    print("-" * 70)

    name = input("指令名称 (如: 清空session): ").strip()
    if not name:
        print("❌ 指令名称不能为空")
        return

    if name in config.get("commands", {}):
        print(f"⚠️  指令 '{name}' 已存在")
        overwrite = input("是否覆盖? (y/n): ").strip().lower()
        if overwrite != "y":
            return

    print("\n可用动作类型:")
    print("  1. clear_session - 清空会话")
    print("  2. switch_model - 切换模型")
    print("  3. git_commit - Git提交")
    print("  4. start_server - 启动服务器")
    print("  5. custom - 自定义")

    action_type = input("\n选择动作类型 (1-5): ").strip()

    action_map = {
        "1": "clear_session",
        "2": "switch_model",
        "3": "git_commit",
        "4": "start_server",
        "5": "custom",
    }

    action = action_map.get(action_type, "custom")

    cmd_config = {
        "action": action,
        "description": input("描述: ").strip() or name,
        "confirm": input("是否需要确认? (y/n): ").strip().lower() == "y",
        "response": input("响应消息: ").strip() or f"✅ {name} 已执行",
    }

    if action == "switch_model":
        cmd_config["model"] = input("模型名称 (kimi-k2.5/deepseek-reasoner): ").strip()

    if cmd_config["confirm"]:
        cmd_config["confirm_message"] = (
            input("确认提示消息: ").strip() or f"确定要执行 {name} 吗？"
        )

    config["commands"][name] = cmd_config
    save_commands(config)
    print(f"\n✅ 指令 '{name}' 已添加")


def remove_command(config):
    """删除指令"""
    print("\n➖ 删除指令")
    print("-" * 70)

    commands = config.get("commands", {})
    if not commands:
        print("📋 没有可删除的指令")
        return

    list_commands(config)

    name = input("\n要删除的指令名称: ").strip()
    if name not in commands:
        print(f"❌ 指令 '{name}' 不存在")
        return

    confirm = input(f"确定要删除 '{name}'? (y/n): ").strip().lower()
    if confirm == "y":
        del config["commands"][name]
        save_commands(config)
        print(f"✅ 指令 '{name}' 已删除")
    else:
        print("已取消")


def edit_command(config):
    """编辑指令"""
    print("\n✏️ 编辑指令")
    print("-" * 70)

    commands = config.get("commands", {})
    if not commands:
        print("📋 没有可编辑的指令")
        return

    list_commands(config)

    name = input("\n要编辑的指令名称: ").strip()
    if name not in commands:
        print(f"❌ 指令 '{name}' 不存在")
        return

    cmd = commands[name]
    print(f"\n正在编辑: {name}")
    print("(直接回车保持原值不变)")
    print()

    new_name = input(f"指令名称 [{name}]: ").strip()
    if new_name and new_name != name:
        # 重命名
        config["commands"][new_name] = config["commands"].pop(name)
        name = new_name
        cmd = config["commands"][name]

    description = input(f"描述 [{cmd.get('description', '')}]: ").strip()
    if description:
        cmd["description"] = description

    response = input(f"响应消息 [{cmd.get('response', '')}]: ").strip()
    if response:
        cmd["response"] = response

    confirm_str = "是" if cmd.get("confirm", False) else "否"
    confirm_input = input(f"需要确认 [{confirm_str}]: ").strip().lower()
    if confirm_input in ["y", "yes", "是"]:
        cmd["confirm"] = True
    elif confirm_input in ["n", "no", "否"]:
        cmd["confirm"] = False

    save_commands(config)
    print(f"\n✅ 指令 '{name}' 已更新")


def show_help():
    """显示帮助"""
    print("""
📖 AI Project Lab 自定义指令管理工具

用法: python manage_commands.py [命令]

命令:
  list      列出所有自定义指令
  add       添加新指令
  remove    删除指令
  edit      编辑指令
  help      显示此帮助信息

示例:
  # 添加一个新指令
  python manage_commands.py add
  
  # 查看所有指令
  python manage_commands.py list
  
  # 删除指令
  python manage_commands.py remove

配置文件位置:
  config/commands.json

内置指令:
  • 清空session - 清空当前会话
  • kimi - 切换到Kimi K2.5模型
  • deepseek - 切换到Deepseek模型
  • git 提交 - 执行Git提交
  • 启动服务器 - 启动服务器
""")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1].lower()
    config = load_commands()

    if command == "list":
        list_commands(config)
    elif command == "add":
        add_command(config)
    elif command == "remove":
        remove_command(config)
    elif command == "edit":
        edit_command(config)
    elif command in ["help", "-h", "--help"]:
        show_help()
    else:
        print(f"❌ 未知命令: {command}")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
