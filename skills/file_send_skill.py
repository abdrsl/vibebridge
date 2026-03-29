"""
OpenCode技能：文件发送到飞书

这个技能允许OpenCode在执行任务时发送文件到飞书。
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from src.legacy.temp_file_manager import temp_file_manager
from src.legacy.file_sender import file_sender


class FileSendSkill:
    """文件发送技能"""

    def __init__(self):
        self.name = "file_send"
        self.description = "发送文件到飞书"
        self.required_params = ["content", "filename"]
        self.optional_params = ["receive_id", "file_type"]

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行文件发送

        Args:
            params: 包含以下参数：
                - content: 文件内容（字符串）
                - filename: 文件名（如 output.html, data.txt）
                - receive_id: 飞书群聊ID（可选）
                - file_type: 文件类型（html, text, json等，可选）

        Returns:
            执行结果
        """
        try:
            content = params.get("content")
            filename = params.get("filename")
            receive_id = params.get("receive_id")
            file_type = params.get("file_type")

            if not content:
                return {"error": "缺少content参数"}

            if not filename:
                # 根据内容类型生成默认文件名
                if file_type == "html":
                    filename = "output.html"
                elif file_type == "json":
                    filename = "data.json"
                else:
                    filename = "output.txt"

            # 确保文件名有正确的扩展名
            if file_type == "html" and not filename.endswith(".html"):
                filename = f"{filename}.html"
            elif file_type == "json" and not filename.endswith(".json"):
                filename = f"{filename}.json"

            # 创建临时文件
            extension = Path(filename).suffix
            temp_file = temp_file_manager.create_temp_file(
                content=content, extension=extension, prefix="opencode_"
            )

            # 发送文件到飞书
            import asyncio

            result = asyncio.run(
                file_sender.send_file_to_feishu(
                    file_path=temp_file,
                    receive_id=receive_id,
                    file_name=filename,
                    delete_after_send=True,
                )
            )

            if "error" in result:
                return {"error": f"发送失败: {result.get('error')}"}

            return {
                "success": True,
                "message": f"文件 '{filename}' 已发送到飞书",
                "file_size": len(content),
                "result": result.get("result", {}),
            }

        except Exception as e:
            return {"error": f"执行失败: {str(e)}"}

    def get_instructions(self) -> str:
        """获取技能使用说明"""
        return """
## 文件发送技能

这个技能允许你将文件发送到飞书。

### 使用方法：
在OpenCode任务中，当需要发送文件时，可以使用以下格式：

```json
{
  "skill": "file_send",
  "params": {
    "content": "文件内容",
    "filename": "output.html",
    "receive_id": "飞书群聊ID（可选）",
    "file_type": "html（可选）"
  }
}
```

### 参数说明：
- `content`: 文件内容（字符串）
- `filename`: 文件名（如 output.html, data.txt）
- `receive_id`: 飞书群聊ID（可选，使用默认配置）
- `file_type`: 文件类型（html, text, json等，可选）

### 示例：
1. 发送HTML文件：
```json
{
  "skill": "file_send",
  "params": {
    "content": "<html><body>Hello World</body></html>",
    "filename": "hello.html",
    "file_type": "html"
  }
}
```

2. 发送文本文件：
```json
{
  "skill": "file_send",
  "params": {
    "content": "这是一段文本内容",
    "filename": "output.txt"
  }
}
```

3. 发送JSON数据：
```json
{
  "skill": "file_send",
  "params": {
    "content": "{\"name\": \"test\", \"value\": 123}",
    "filename": "data.json",
    "file_type": "json"
  }
}
```
"""


# 技能注册
file_send_skill = FileSendSkill()


def register_skill(skill_manager):
    """注册技能到技能管理器"""
    skill_manager.register_skill(file_send_skill)
    print(f"[Skills] Registered file send skill: {file_send_skill.name}")
