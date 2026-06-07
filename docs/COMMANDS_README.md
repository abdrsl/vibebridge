# 自定义指令系统

## 🎯 功能概述

自定义指令系统允许你通过 Feishu 发送特定文字来触发预设操作。

当前支持的指令：

| 指令 | 说明 | 需要确认 |
|------|------|----------|
| `清空session` | 清空当前所有活跃会话 | ❌ 否 |
| `kimi` | 切换到 Kimi 模式 | ❌ 否 |
| `deepseek` | 切换到 Deepseek 模式 | ❌ 否 |
| `git 提交` | 执行 git add/commit/push | ✅ 是 |
| `启动服务器` | 启动本地服务器 | ❌ 否 |
| `模型` | 显示可用模型和当前模型 | ❌ 否 |
| `hello` / `hi` | 打招呼 | ❌ 否 |
| `websocket模式` | 切换到 WebSocket 长连接模式 | ❌ 否 |
| `webhook模式` | 切换到 Webhook 回调模式 | ❌ 否 |

> **注意**: 这些指令配置在 `config/commands.json` 中，但当前版本的实际指令处理由 `TaskOrchestrator` 和 `ProviderRouter` 接管。`清空session`、`kimi`、`deepseek` 等切换功能已通过 `/kimi`、`/claude`、`/opencode`、`/openrouter` 命令实现，详见 `src/vibebridge/router.py`。

## 📁 配置文件

```
config/
├── commands.json           # 指令配置（旧版兼容，当前主要使用 router.py）
└── settings.json           # 系统设置（websocket/webhook 模式等）
```

## 🚀 使用方法

### 方式1: 通过 Feishu 发送 Provider 切换命令（推荐）

在 Feishu 中直接发送：

```
/kimi
```

或旧版指令（兼容性保留）：

```
kimi
```

### 方式2: 管理指令配置

直接编辑配置文件：

```bash
nano config/commands.json
```

## 🔧 配置文件详解

配置文件位置：`config/commands.json`

```json
{
  "version": "1.0",
  "commands": {
    "指令名称": {
      "action": "动作类型",
      "description": "描述",
      "confirm": false,
      "response": "响应消息"
    }
  },
  "models": {
    "模型ID": {
      "name": "显示名称",
      "provider": "提供商",
      "model_id": "API模型ID",
      "api_key_env": "API密钥环境变量名"
    }
  }
}
```

### 内置动作类型

1. **clear_session** - 清空会话
   - 关闭用户的所有活跃会话
   - 无需参数

2. **switch_model** - 切换模型（旧版，现由 ProviderRouter 处理）
   - 需要指定 `model` 参数
   - 可选值：`kimi-k2.5`, `deepseek-reasoner`, `default`

3. **git_commit** - Git 提交
   - 自动执行 git add .
   - 自动执行 git status
   - 自动执行 git commit
   - 自动执行 git push
   - 需要确认

4. **start_server** - 启动服务器
   - 检查服务器是否已在运行
   - 如未运行则启动
   - 等待启动完成并返回状态

5. **switch_feishu_mode** - 切换飞书连接模式
   - `websocket` - WebSocket 长连接模式（推荐）
   - `webhook` - Webhook 回调模式

## 📝 添加自定义指令示例

### 直接编辑配置文件

```bash
# 编辑配置文件
nano config/commands.json
```

添加：
```json
{
  "commands": {
    "查看状态": {
      "action": "custom",
      "description": "查看系统状态",
      "confirm": false,
      "response": "✅ 系统运行正常"
    }
  }
}
```

## 🎨 自定义响应消息

响应消息支持以下变量：
- `{user_name}` - 用户名
- `{chat_id}` - 聊天 ID
- `{timestamp}` - 时间戳

示例：
```json
{
  "response": "👋 你好 {user_name}！当前时间: {timestamp}"
}
```

## 🔍 指令处理流程

当前版本的指令处理流程：

```
Feishu 消息
    ↓
TaskOrchestrator.handle_message()
    ↓
ProviderRouter.is_switch_command()  ← 检测 /kimi, /claude 等
    ↓
如果是切换命令 → 更新 session.provider
    ↓
如果是普通消息 → 路由到对应 provider 执行
```

旧版 `config/commands.json` 中的指令配置保留用于向后兼容，但核心逻辑已由 `ProviderRouter` 和 `TaskOrchestrator` 接管。

## ⚠️ 注意事项

1. **Provider 切换优先**: `/kimi`、`/claude` 等切换命令优先于 `commands.json` 中的配置
2. **Session 级持久化**: 切换后的 provider 偏好保存在 session 中，同一聊天后续消息默认使用
3. ** Constitution Guard**: 危险操作仍需 `mysecret` 授权，不受指令配置影响

## 🔄 重启生效

修改配置后无需重启服务，配置会动态加载。

如需强制刷新：

```bash
systemctl --user restart vibebridge
```
