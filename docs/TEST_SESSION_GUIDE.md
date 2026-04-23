# OpenCode Feishu Bridge - 测试Session创建指南

## 概述

本文档介绍如何创建和管理OpenCode Feishu Bridge的测试session。Session用于跟踪飞书对话状态，管理用户与OpenCode的交互。

## 快速开始

### 1. 创建测试session

使用简单的命令行工具创建测试session：

```bash
# 创建默认测试session
python3 create_test_session_simple.py create

# 创建自定义session
python3 create_test_session_simple.py create my_chat_id my_user_id "任务描述"
```

示例：
```bash
python3 create_test_session_simple.py create demo_chat demo_user "测试OpenCode集成"
```

### 2. 列出所有sessions

```bash
python3 create_test_session_simple.py list
```

### 3. 查看特定session详情

```bash
python3 create_test_session_simple.py show <session_id>
```

示例：
```bash
python3 create_test_session_simple.py show fs_1775480984_74b6b914
```

## Session结构

一个session包含以下信息：

- **session_id**: 唯一标识符 (格式: `fs_<timestamp>_<random>`)
- **chat_id**: 飞书聊天ID
- **user_id**: 用户ID
- **status**: 状态 (pending, confirmed, running, completed, failed, cancelled, expired)
- **current_task_id**: 当前任务ID
- **messages**: 对话历史
- **metadata**: 元数据
- **timestamps**: 创建时间、更新时间、过期时间

## Session状态说明

| 状态 | 说明 | 图标 |
|------|------|------|
| PENDING | 等待用户确认 | ⏳ |
| CONFIRMED | 用户已确认，准备执行 | ✅ |
| RUNNING | 任务执行中 | 🔄 |
| COMPLETED | 任务完成 | 🏁 |
| FAILED | 任务失败 | ❌ |
| CANCELLED | 用户取消 | 🚫 |
| EXPIRED | Session过期 | ⏰ |

## 数据存储

Session数据保存在 `data/sessions/` 目录下，每个session一个JSON文件：

```
data/sessions/
├── fs_1775480895_f5637439.json
├── fs_1775480984_74b6b914.json
└── ...
```

## 高级使用

### 使用Python API

```python
import asyncio
from src.legacy.session_manager import get_session_manager, SessionStatus

async def create_session():
    manager = get_session_manager()
    
    # 创建session
    session = await manager.get_or_create_session(
        chat_id="test_chat",
        user_id="test_user",
    )
    
    # 添加消息
    await manager.add_message_to_session(
        session.session_id,
        "user",
        "任务描述",
        message_id="msg_001"
    )
    
    # 更新状态
    await manager.update_session(
        session.session_id,
        status=SessionStatus.CONFIRMED,
        task_id="task_001"
    )
    
    return session

# 运行
session = asyncio.run(create_session())
print(f"Session ID: {session.session_id}")
```

### 运行完整测试套件

```bash
# 运行session管理器测试
python3 tests/test_session_manager.py

# 或者直接运行模块
cd /home/user/workspace/vibebridge
python3 -m tests.test_session_manager
```

## 清理过期session

Session默认1小时后过期。可以手动清理：

```python
from src.legacy.session_manager import get_session_manager

async def cleanup():
    manager = get_session_manager()
    cleaned = await manager.cleanup_expired_sessions()
    print(f"清理了 {cleaned} 个过期session")

asyncio.run(cleanup())
```

## 故障排除

### 1. 找不到模块

确保在项目根目录运行，并添加src到Python路径：

```bash
cd /home/user/workspace/vibebridge
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
```

### 2. Session文件损坏

如果session文件损坏，可以手动删除：

```bash
rm data/sessions/<session_id>.json
```

### 3. 状态不更新

检查session是否已过期。过期session不会被更新。

## 相关文件

- `src/legacy/session_manager.py` - Session管理器实现
- `tests/test_session_manager.py` - 完整测试套件
- `create_test_session_simple.py` - 简单命令行工具
- `create_test_session.py` - 详细测试脚本
- `create_session_interactive.py` - 交互式工具（需要终端输入支持）

## 下一步

1. 将session与OpenCode任务集成
2. 实现飞书卡片交互
3. 添加session持久化到数据库
4. 实现session恢复功能