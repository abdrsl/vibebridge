#!/usr/bin/env python3
"""
测试文件发送功能
"""

import asyncio
import os
from pathlib import Path
from src.legacy.temp_file_manager import temp_file_manager
from src.legacy.file_sender import file_sender, send_html_to_feishu
from src.legacy.simple_skill_manager import get_simple_skill_manager


async def test_temp_file_manager():
    """测试临时文件管理器"""
    print("测试临时文件管理器")
    print("=" * 60)

    # 创建临时文件
    content = "这是一个测试文件内容\n第二行内容"
    temp_file = temp_file_manager.create_temp_file(
        content=content, extension=".txt", prefix="test_"
    )

    print(f"创建的临时文件: {temp_file}")
    print(f"文件存在: {temp_file.exists()}")

    # 获取文件信息
    file_info = temp_file_manager.get_file_info(temp_file)
    print(f"文件信息: {file_info}")

    # 读取文件内容
    read_content = temp_file_manager.read_file(temp_file)
    print(f"文件内容: {read_content}")

    # 列出文件
    files = temp_file_manager.list_files()
    print(f"临时目录中的文件数量: {len(files)}")

    # 清理文件
    deleted = temp_file_manager.delete_file(temp_file)
    print(f"文件已删除: {deleted}")

    print()


async def test_file_sender():
    """测试文件发送器"""
    print("测试文件发送器")
    print("=" * 60)

    # 创建测试HTML文件
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>测试页面</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            h1 { color: #4361ee; }
        </style>
    </head>
    <body>
        <h1>测试HTML页面</h1>
        <p>这是一个测试页面，用于验证文件发送功能。</p>
        <p>时间: 2025-03-22</p>
    </body>
    </html>
    """

    # 创建临时HTML文件
    temp_file = temp_file_manager.create_temp_file(
        content=html_content, extension=".html", prefix="test_html_"
    )

    print(f"创建的HTML文件: {temp_file}")

    # 测试发送文件（需要配置飞书环境变量）
    feishu_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID")
    if feishu_chat_id:
        print(f"飞书群聊ID: {feishu_chat_id}")

        # 发送文件
        result = await file_sender.send_file_to_feishu(
            file_path=temp_file,
            receive_id=feishu_chat_id,
            file_name="test_page.html",
            delete_after_send=False,  # 测试时不删除
        )

        print(f"发送结果: {result}")

        if "error" in result:
            print(f"发送失败: {result['error']}")
        else:
            print("文件发送成功！")

            # 清理文件
            temp_file_manager.delete_file(temp_file)
            print("临时文件已清理")
    else:
        print("未配置飞书群聊ID，跳过实际发送测试")
        print("请设置 FEISHU_DEFAULT_CHAT_ID 环境变量")

        # 模拟发送
        print("模拟发送结果: 成功")

        # 清理文件
        temp_file_manager.delete_file(temp_file)
        print("临时文件已清理")

    print()


def test_simple_skill_manager():
    """测试简单技能管理器"""
    print("测试简单技能管理器")
    print("=" * 60)

    manager = get_simple_skill_manager()

    # 测试宪法检查
    test_input = "请帮我创建一个漂亮的HTML个人网页"
    print(f"测试宪法检查: {test_input}")
    constitution_result = manager.check_constitution(test_input)
    print(f"  是否有违规: {constitution_result['has_violations']}")
    print(f"  是否有警告: {constitution_result['has_warnings']}")

    # 测试会话名称生成
    session_name = manager.generate_session_name(test_input)
    print(f"  生成的会话名称: {session_name}")

    # 测试创建临时文件技能
    print("\n测试创建临时文件技能:")
    create_result = manager.execute_skill(
        "create_temp_file",
        {"content": "测试技能执行", "extension": ".txt", "prefix": "skill_test_"},
    )
    print(f"  结果: {create_result}")

    if create_result.get("success"):
        # 测试列出文件技能
        list_result = manager.execute_skill("list_temp_files", {})
        print(f"  临时文件数量: {list_result.get('count', 0)}")

        # 清理测试文件
        if "file_path" in create_result:
            temp_file_manager.delete_file(create_result["file_path"])
            print("  测试文件已清理")

    # 测试发送文件技能（需要飞书配置）
    feishu_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID")
    if feishu_chat_id:
        print("\n测试发送文件技能:")
        send_result = manager.execute_skill(
            "send_file",
            {
                "content": "<h1>测试HTML</h1><p>来自技能管理器的测试</p>",
                "filename": "skill_test.html",
                "receive_id": feishu_chat_id,
                "file_type": "html",
            },
        )
        print(f"  结果: {send_result}")
    else:
        print("\n未配置飞书，跳过发送文件技能测试")

    print()


async def test_html_send():
    """测试HTML发送快捷函数"""
    print("测试HTML发送快捷函数")
    print("=" * 60)

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>快捷测试</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .container { background: #f5f7ff; padding: 30px; border-radius: 10px; }
            h1 { color: #4361ee; text-align: center; }
            .features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 30px 0; }
            .feature { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>OpenCode 文件发送功能测试</h1>
            <p>这是一个通过快捷函数发送的HTML测试页面。</p>
            
            <div class="features">
                <div class="feature">
                    <h3>📁 临时文件管理</h3>
                    <p>自动创建、管理和清理临时文件</p>
                </div>
                <div class="feature">
                    <h3>📤 飞书集成</h3>
                    <p>支持发送各种文件到飞书群聊</p>
                </div>
                <div class="feature">
                    <h3>⚡ 技能系统</h3>
                    <p>通过技能管理器统一管理功能</p>
                </div>
            </div>
            
            <p>测试时间: 2025-03-22</p>
        </div>
    </body>
    </html>
    """

    feishu_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID")
    if feishu_chat_id:
        print(f"飞书群聊ID: {feishu_chat_id}")

        result = await send_html_to_feishu(
            html_content=html_content,
            filename="opencode_test.html",
            receive_id=feishu_chat_id,
        )

        print(f"发送结果: {result}")

        if "error" in result:
            print(f"发送失败: {result['error']}")
        else:
            print("HTML文件发送成功！")
    else:
        print("未配置飞书群聊ID，跳过实际发送测试")
        print("HTML内容预览（前200字符）:")
        print(html_content[:200] + "...")

    print()


def main():
    """主函数"""
    print("OpenCode 文件发送功能测试套件")
    print("=" * 60)

    # 确保临时目录存在
    temp_dir = Path("tmp")
    temp_dir.mkdir(exist_ok=True)
    print(f"临时目录: {temp_dir.absolute()}")

    # 运行测试
    asyncio.run(test_temp_file_manager())
    asyncio.run(test_file_sender())
    test_simple_skill_manager()
    asyncio.run(test_html_send())

    # 清理旧文件
    print("清理旧文件")
    print("=" * 60)
    deleted_count = temp_file_manager.cleanup_old_files(
        max_age_hours=1
    )  # 清理1小时前的文件
    print(f"清理了 {deleted_count} 个旧文件")

    print("\n" + "=" * 60)
    print("测试完成！")

    # 显示配置说明
    print("\n配置说明:")
    print("1. 设置飞书环境变量:")
    print("   export FEISHU_APP_ID=your_app_id")
    print("   export FEISHU_APP_SECRET=your_app_secret")
    print("   export FEISHU_DEFAULT_CHAT_ID=your_chat_id")
    print("\n2. 临时文件目录: tmp/")
    print("3. 技能管理器已加载文件发送功能")


if __name__ == "__main__":
    main()
