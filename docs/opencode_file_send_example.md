# OpenCode 文件发送功能使用指南

## 概述

OpenCode现在支持将临时文件发送到飞书。这对于发送HTML页面、配置文件、数据文件等非项目文件非常有用。

## 核心组件

### 1. 临时文件管理器 (`app/temp_file_manager.py`)
- 自动管理 `tmp/` 目录中的临时文件
- 支持创建、读取、删除文件
- 自动清理旧文件

### 2. 文件发送器 (`app/file_sender.py`)
- 发送文件到飞书
- 支持HTML、文本、JSON等多种格式
- 批量发送功能

### 3. 技能管理器 (`app/simple_skill_manager.py`)
- 统一技能接口
- 内置文件发送技能
- 宪法检查和会话命名

## 使用方法

### 方法1：通过技能系统（推荐）

在OpenCode任务中，可以使用技能系统发送文件：

```python
# 在OpenCode任务中
{
  "skill": "send_file",
  "params": {
    "content": "<html><body>Hello World</body></html>",
    "filename": "hello.html",
    "file_type": "html",
    "receive_id": "飞书群聊ID（可选）"
  }
}
```

### 方法2：直接调用API

```python
from app.file_sender import send_html_to_feishu
import asyncio

html_content = """
<!DOCTYPE html>
<html>
<body>
    <h1>测试页面</h1>
</body>
</html>
"""

# 发送HTML文件
result = asyncio.run(send_html_to_feishu(
    html_content=html_content,
    filename="test.html",
    receive_id="飞书群聊ID"
))
```

### 方法3：通过OpenCode任务

当用户请求创建HTML页面时，OpenCode可以：

1. 创建HTML文件
2. 保存到临时目录
3. 通过技能发送到飞书

## 示例：创建并发送个人网页

用户请求："@_user_1 请你做一个漂亮的html个人网页发过来"

OpenCode可以执行以下步骤：

```python
# 1. 创建HTML内容
html = create_personal_website_html()

# 2. 使用技能发送到飞书
skill_result = execute_skill("send_html", {
    "content": html,
    "filename": "personal_website.html",
    "file_type": "html"
})

# 3. 返回结果给用户
if skill_result.get("success"):
    return "✅ 个人网页已创建并发送到飞书！"
else:
    return f"❌ 发送失败: {skill_result.get('error')}"
```

## 环境变量配置

```bash
# 飞书配置
export FEISHU_APP_ID=your_app_id
export FEISHU_APP_SECRET=your_app_secret
export FEISHU_DEFAULT_CHAT_ID=your_chat_id

# 临时目录配置（可选）
export TEMP_DIR=/path/to/tmp  # 默认: project_root/tmp
```

## 文件类型支持

- **HTML文件** (`.html`): 自动识别为text/html
- **文本文件** (`.txt`, `.md`, `.py`等): 自动识别为text/plain
- **JSON文件** (`.json`): 自动识别为application/json
- **其他文件**: 根据扩展名和内容自动识别

## 自动清理

临时文件会自动管理：
- 发送成功后自动删除（可配置）
- 定期清理超过24小时的旧文件
- 支持手动清理

## 错误处理

系统提供完整的错误处理：
- 文件不存在错误
- 飞书API错误
- 网络超时错误
- 权限错误

## 测试工具

提供了测试脚本：
```bash
# 运行完整测试
python test_file_send.py

# 运行示例
python example_opencode_file_send.py
```

## 集成到现有系统

### 1. 更新OpenCode集成
已更新 `app/opencode_integration.py` 支持技能系统。

### 2. 扩展飞书客户端
已扩展 `app/feishu_client.py` 支持文件上传。

### 3. 更新文档
已更新 `AGENTS.md` 记录新功能。

## 注意事项

1. **文件大小限制**: 飞书API有文件大小限制（通常10MB）
2. **频率限制**: 注意飞书API调用频率限制
3. **安全性**: 临时文件可能包含敏感信息，确保适当清理
4. **网络稳定性**: 大文件上传可能需要重试机制

## 未来扩展

1. **更多文件类型**: 支持图片、PDF、Office文档等
2. **压缩支持**: 自动压缩大文件
3. **进度显示**: 大文件上传进度显示
4. **断点续传**: 支持上传中断后恢复
5. **云存储集成**: 支持其他云存储服务

## 总结

OpenCode的文件发送功能使得AI助手能够：
- 创建并发送各种类型的文件
- 自动管理临时文件生命周期
- 通过技能系统统一接口
- 与飞书深度集成

这大大扩展了OpenCode的应用场景，使其不仅限于代码开发，还能处理各种文件生成和分享任务。