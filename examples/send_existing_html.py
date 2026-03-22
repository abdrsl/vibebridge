#!/usr/bin/env python3
"""
发送现有HTML文件到飞书
"""

import asyncio
import os
from pathlib import Path
from app.file_sender import file_sender


async def send_existing_html():
    """发送现有的HTML文件到飞书"""
    print("发送现有HTML文件到飞书")
    print("=" * 60)

    # 检查文件是否存在
    html_file = Path("personal_website.html")
    if not html_file.exists():
        print(f"错误: 文件不存在: {html_file}")
        return

    print(f"找到HTML文件: {html_file}")
    print(f"文件大小: {html_file.stat().st_size} 字节")

    # 读取文件内容
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    print(f"文件内容长度: {len(html_content)} 字符")
    print(f"前100字符: {html_content[:100]}...")

    # 检查飞书配置
    feishu_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID")
    if not feishu_chat_id:
        print("错误: 未配置飞书群聊ID")
        print("请设置 FEISHU_DEFAULT_CHAT_ID 环境变量")
        return

    print(f"飞书群聊ID: {feishu_chat_id}")

    # 发送文件
    print("\n正在发送文件到飞书...")
    result = await file_sender.send_html_as_file(
        html_content=html_content,
        filename="个人网页.html",
        receive_id=feishu_chat_id,
        delete_after_send=False,  # 不删除，保留原文件
    )

    print(f"\n发送结果: {result}")

    if "error" in result:
        print(f"❌ 发送失败: {result['error']}")
    else:
        print("✅ 文件发送成功！")

        # 显示文件信息
        if "result" in result and "file_path" in result:
            print(f"📁 文件路径: {result['file_path']}")
            print(f"📄 文件名: {result['file_name']}")


def check_feishu_config():
    """检查飞书配置"""
    print("检查飞书配置")
    print("=" * 60)

    required_vars = ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_DEFAULT_CHAT_ID"]
    missing_vars = []

    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: 已设置")
        else:
            print(f"❌ {var}: 未设置")
            missing_vars.append(var)

    if missing_vars:
        print(f"\n⚠️  缺少配置变量: {', '.join(missing_vars)}")
        print("\n请设置以下环境变量:")
        for var in missing_vars:
            print(f"  export {var}=your_value")
        return False

    print("\n✅ 所有配置检查通过")
    return True


def main():
    """主函数"""
    print("OpenCode HTML文件发送演示")
    print("=" * 60)

    # 检查配置
    if not check_feishu_config():
        print("\n由于配置不完整，跳过实际发送")
        print("文件已准备好，配置完成后可重新运行")
        return

    print("\n" + "=" * 60)

    # 运行发送任务
    asyncio.run(send_existing_html())

    print("\n" + "=" * 60)
    print("演示完成！")

    # 显示使用说明
    print("\n使用说明:")
    print("1. 这个脚本演示了如何发送现有HTML文件到飞书")
    print("2. 文件 'personal_website.html' 会被发送")
    print("3. 发送后原文件保持不变")
    print("4. 临时文件会自动清理")

    print("\n在OpenCode任务中，可以这样使用:")
    print("""
# 读取现有文件
with open('personal_website.html', 'r') as f:
    html_content = f.read()

# 使用技能发送
skill_result = execute_skill("send_html", {
    "content": html_content,
    "filename": "个人网页.html"
})
    """)


if __name__ == "__main__":
    main()
