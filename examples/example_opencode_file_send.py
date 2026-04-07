#!/usr/bin/env python3
"""
OpenCode文件发送示例

这个示例演示如何通过OpenCode任务发送文件到飞书。
"""

import asyncio
import json
import os
from pathlib import Path

from src.legacy.opencode_integration import opencode_manager
from src.legacy.simple_skill_manager import execute_skill
from src.legacy.temp_file_manager import temp_file_manager


async def example_send_html():
    """示例：发送HTML文件到飞书"""
    print("示例1: 发送HTML文件到飞书")
    print("=" * 60)

    # 创建HTML内容
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>OpenCode生成的个人网页</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 800px;
                margin: 40px auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #4361ee 0%, #3a0ca3 100%);
                color: white;
                padding: 40px;
                text-align: center;
            }
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
            }
            .header p {
                font-size: 1.2rem;
                opacity: 0.9;
            }
            .content {
                padding: 40px;
            }
            .section {
                margin-bottom: 30px;
            }
            .section h2 {
                color: #4361ee;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 2px solid #f0f0f0;
            }
            .skills {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            .skill {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 10px;
                border-left: 4px solid #4361ee;
            }
            .projects {
                display: grid;
                gap: 20px;
            }
            .project {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                border: 1px solid #e9ecef;
            }
            .footer {
                background: #f8f9fa;
                padding: 20px;
                text-align: center;
                border-top: 1px solid #e9ecef;
                color: #6c757d;
            }
            @media (max-width: 768px) {
                .container { margin: 20px; }
                .header { padding: 30px 20px; }
                .content { padding: 30px 20px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>张明 - 全栈开发者</h1>
                <p>专注于创造优雅、高效的Web解决方案</p>
            </div>
            
            <div class="content">
                <div class="section">
                    <h2>关于我</h2>
                    <p>拥有5年全栈开发经验，擅长将复杂需求转化为简洁的技术实现。热衷于学习新技术，追求代码质量和用户体验。</p>
                </div>
                
                <div class="section">
                    <h2>技术栈</h2>
                    <div class="skills">
                        <div class="skill">
                            <h3>前端</h3>
                            <p>React, Vue.js, TypeScript, HTML5, CSS3</p>
                        </div>
                        <div class="skill">
                            <h3>后端</h3>
                            <p>Node.js, Python, FastAPI, PostgreSQL</p>
                        </div>
                        <div class="skill">
                            <h3>DevOps</h3>
                            <p>Docker, AWS, CI/CD, Git</p>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>项目经验</h2>
                    <div class="projects">
                        <div class="project">
                            <h3>电商平台重构</h3>
                            <p>主导了大型电商平台的前后端重构，性能提升40%</p>
                        </div>
                        <div class="project">
                            <h3>实时数据分析系统</h3>
                            <p>构建了支持百万级并发实时数据处理系统</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <p>© 2025 张明 | 通过OpenCode生成</p>
            </div>
        </div>
    </body>
    </html>
    """

    # 使用技能管理器发送文件
    feishu_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID")

    if feishu_chat_id:
        print("使用技能管理器发送HTML文件...")
        result = execute_skill(
            "send_html",
            {
                "content": html_content,
                "filename": "personal_website.html",
                "receive_id": feishu_chat_id,
            },
        )

        print(f"发送结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print("未配置飞书群聊ID，跳过实际发送")
        print("HTML文件内容已准备好，可以手动发送")

        # 保存到文件供查看
        output_file = Path("example_personal_website.html")
        output_file.write_text(html_content, encoding="utf-8")
        print(f"HTML文件已保存到: {output_file.absolute()}")

    print()


async def example_opencode_task():
    """示例：通过OpenCode任务发送文件"""
    print("示例2: 通过OpenCode任务发送文件")
    print("=" * 60)

    # 创建一个OpenCode任务
    task_message = """
    请创建一个漂亮的个人简历HTML页面，包含以下内容：
    1. 姓名和职位标题
    2. 个人简介（3-4句话）
    3. 技能列表（前端、后端、工具等）
    4. 项目经验（2-3个项目）
    5. 联系方式
    
    页面要美观、响应式设计，使用现代CSS特性。
    创建完成后，请将HTML文件发送到飞书。
    """

    print(f"任务描述: {task_message[:100]}...")

    # 创建任务（这里只是演示，实际需要运行OpenCode）
    feishu_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID")

    if feishu_chat_id:
        print("创建OpenCode任务...")
        task_id = await opencode_manager.create_task(
            user_message=task_message,
            feishu_chat_id=feishu_chat_id,
        )

        print(f"任务ID: {task_id}")
        print("注意：实际执行需要启动OpenCode服务")
    else:
        print("未配置飞书群聊ID，跳过任务创建")

    print()


async def example_batch_files():
    """示例：批量发送多个文件"""
    print("示例3: 批量发送多个文件")
    print("=" * 60)

    # 创建多个测试文件
    files_content = [
        {
            "name": "readme.md",
            "content": """# 项目说明

这是一个示例项目，演示OpenCode文件发送功能。

## 功能特性
- 临时文件管理
- 飞书文件发送
- 技能系统集成
- 批量操作支持

## 使用方法
1. 配置飞书环境变量
2. 调用文件发送API
3. 查看发送结果

## 注意事项
- 临时文件会自动清理
- 支持各种文件类型
- 提供错误处理机制
""",
        },
        {
            "name": "config.json",
            "content": """{
  "project": "OpenCode File Sender",
  "version": "1.0.0",
  "features": [
    "temp_file_management",
    "feishu_integration",
    "skill_system",
    "batch_operations"
  ],
  "settings": {
    "auto_cleanup": true,
    "max_file_size": "10MB",
    "supported_formats": [".txt", ".html", ".json", ".md", ".py"]
  }
}""",
        },
        {
            "name": "example.py",
            "content": """#!/usr/bin/env python3
""",
        },
    ]

    print(f"创建 {len(files_content)} 个测试文件...")

    # 创建临时文件
    temp_files = []
    for file_info in files_content:
        temp_file = temp_file_manager.create_temp_file(
            content=file_info["content"],
            extension=Path(file_info["name"]).suffix,
            prefix="batch_",
        )
        temp_files.append(temp_file)
        print(f"  创建: {temp_file.name}")

    # 发送文件（需要飞书配置）
    feishu_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID")

    if feishu_chat_id:
        print(f"发送文件到飞书群聊: {feishu_chat_id}")

        from src.legacy.file_sender import file_sender

        results = await file_sender.send_multiple_files(
            file_paths=temp_files,
            receive_id=feishu_chat_id,
            delete_after_send=True,
        )

        print("发送结果:")
        for i, result in enumerate(results):
            filename = temp_files[i].name if i < len(temp_files) else "unknown"
            if "error" in result:
                print(f"  {filename}: ❌ {result['error']}")
            else:
                print(f"  {filename}: ✅ 发送成功")
    else:
        print("未配置飞书群聊ID，跳过实际发送")
        print("文件已创建在临时目录中")

    print()


def main():
    """主函数"""
    print("OpenCode 文件发送功能示例")
    print("=" * 60)

    # 检查配置
    feishu_app_id = os.getenv("FEISHU_APP_ID")
    feishu_app_secret = os.getenv("FEISHU_APP_SECRET")
    feishu_chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID")

    print("配置检查:")
    print(f"  FEISHU_APP_ID: {'✅ 已设置' if feishu_app_id else '❌ 未设置'}")
    print(f"  FEISHU_APP_SECRET: {'✅ 已设置' if feishu_app_secret else '❌ 未设置'}")
    print(f"  FEISHU_DEFAULT_CHAT_ID: {'✅ 已设置' if feishu_chat_id else '❌ 未设置'}")

    if not all([feishu_app_id, feishu_app_secret, feishu_chat_id]):
        print("\n⚠️  注意：未完全配置飞书环境变量，部分示例将跳过实际发送")
        print("请设置以下环境变量以启用完整功能:")
        print("  export FEISHU_APP_ID=your_app_id")
        print("  export FEISHU_APP_SECRET=your_app_secret")
        print("  export FEISHU_DEFAULT_CHAT_ID=your_chat_id")

    print("\n" + "=" * 60)

    # 运行示例
    asyncio.run(example_send_html())
    asyncio.run(example_opencode_task())
    asyncio.run(example_batch_files())

    print("=" * 60)
    print("示例演示完成！")

    # 显示使用说明
    print("\n使用说明:")
    print("1. 在OpenCode任务中，可以通过技能系统发送文件")
    print("2. 临时文件会自动管理，无需手动清理")
    print("3. 支持HTML、文本、JSON等多种文件格式")
    print("4. 可以通过API或技能管理器调用")

    print("\n代码位置:")
    print("  - 临时文件管理: app/temp_file_manager.py")
    print("  - 文件发送器: app/file_sender.py")
    print("  - 技能管理器: app/simple_skill_manager.py")
    print("  - 飞书客户端: app/feishu_client.py")


if __name__ == "__main__":
    main()
