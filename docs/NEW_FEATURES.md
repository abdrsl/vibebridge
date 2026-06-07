# 🔧 新增功能文档 (v1.2.0)

> **注意**: 本文档描述 v1.2.0 版本的实际功能。旧版 `app/` 目录中的模块已在架构重构中迁移或移除。

## 📋 新增功能概述

### 1. 多 Provider 架构 ✅
- **目的**: 支持 OpenCode、Kimi、Claude、OpenRouter 动态切换
- **实现**: `src/vibebridge/router.py` (ProviderRouter)
- **切换方式**: 在 Feishu 中发送 `/kimi`, `/claude`, `/opencode`, `/openrouter`
- **持久化**: 每个 chat 的 provider 偏好保存在 session 中

### 2. Constitutional Guard（宪法守卫）✅
- **目的**: 拦截危险命令，防止误操作
- **实现**: `src/vibebridge/constitution_guard.py`
- **拦截规则**: rm -rf, git push --force, drop database, dd, sudo, curl | bash 等
- **授权方式**: 发送 `mysecret <命令>` 进行会话级授权

### 3. 单卡片流式更新 ✅
- **目的**: 避免任务执行过程中发送大量消息
- **实现**: `src/vibebridge/tasks.py` (_update_card)
- **机制**: 创建任务时发送开始卡片，后续通过 message_id PATCH 更新同一张卡片
- **卡片类型**: 开始卡片 → 进度卡片 → 结果/错误卡片

### 4. OpenCode Session 连续性 ✅
- **目的**: 保持多轮对话上下文
- **实现**: `src/vibebridge/providers/opencode.py`
- **机制**:
  - 首次对话：不传入 `--session`，从 `step_start` 事件捕获 sessionID
  - 后续对话：使用 `--session <id> --continue` 续接上下文
- **映射存储**: 按 VibeBridge session_id → OpenCode session_id 映射

### 5. 非 JSON 错误诊断 ✅
- **目的**: OpenCode 在 JSON 模式下 API 出错时 message 字段为空
- **实现**: `src/vibebridge/providers/opencode.py` (non_json_lines 收集)
- **检测模式**:
  - `Insufficient Balance` → "DeepSeek API 余额不足，请充值后重试"
  - `AI_APICallError` → 提取具体 API 错误信息
  - `ECONNREFUSED` / `timeout` → 网络相关错误

## 📁 核心文件说明

```
src/vibebridge/
├── router.py              # Provider 路由（/kimi, /claude 等切换命令）
├── tasks.py               # TaskOrchestrator（核心任务调度）
├── constitution_guard.py  # 危险命令拦截与授权
├── providers/
│   ├── opencode.py        # OpenCode provider（session 连续性）
│   ├── kimi.py            # Kimi provider
│   ├── claude.py          # Claude provider
│   └── openrouter.py      # OpenRouter provider
├── cards/
│   ├── start.py           # 开始卡片
│   ├── progress.py        # 进度卡片
│   ├── result.py          # 结果卡片
│   └── error.py           # 错误卡片
├── im/
│   └── feishu.py          # Feishu 多机器人管理器
└── session.py             # 会话模型（含 authorized_operations）
```

## 🚀 使用方法

### Provider 切换

在 Feishu 中直接发送：

```
/kimi
```

回复：
> ✅ 已切换到 **Kimi** 模式
> 下次发送消息时将使用 Kimi 执行。

### 危险命令授权

当 OpenCode 尝试执行危险命令时：

> ⛔ **检测到危险操作：删除文件/目录（强制/递归）**
> ```
> rm -rf dist/
> ```
> 如需授权执行，请发送：`mysecret rm -rf dist/`

发送授权：
```
mysecret rm -rf dist/
```

回复：
> ✅ 已授权操作：`rm -rf dist/`
> 当前 session 后续执行此操作将不再拦截。
> 🔄 正在重新执行上次的指令...

### systemd 服务管理

```bash
# 启动服务
systemctl --user start vibebridge

# 查看状态
systemctl --user status vibebridge

# 重启服务
systemctl --user restart vibebridge

# 查看日志
journalctl --user -u vibebridge -f
```

## 📊 功能详解

### Provider Router

**工作原理**:
1. 收到消息时检查是否以 `/` 开头
2. 匹配 provider 名称：`/kimi`, `/claude`, `/opencode`, `/openrouter`
3. 更新 session 的 provider 偏好
4. 后续消息默认使用该 provider

**代码示例**:
```python
from vibebridge.router import ProviderRouter

router = ProviderRouter()
router.register("opencode", opencode_provider)
router.register("kimi", kimi_provider)

# 解析消息
target = router.is_switch_command("/kimi")  # 返回 "kimi"
provider, prompt = router.resolve("hello", session.provider)
```

### Constitutional Guard

**危险命令检测**:
```python
from vibebridge.constitution_guard import is_dangerous_command

is_danger, desc = is_dangerous_command("rm -rf /")
# is_danger = True
# desc = "删除文件/目录（强制/递归）"
```

**授权检查**:
```python
from vibebridge.constitution_guard import parse_auth_message

cmd = parse_auth_message("mysecret rm -rf dist/")
# cmd = "rm -rf dist/"
```

### 卡片流式更新

**发送并追踪卡片**:
```python
# 发送卡片并获取 message_id
ok, msg_id = await bot.send_card_with_id(chat_id, card)

# 后续更新同一张卡片
await bot.update_card(msg_id, new_card)
```

## 🔧 配置

### Provider 配置 (`~/.config/vibebridge/config.yaml`)

```yaml
agents:
  default_provider: opencode
  opencode:
    enabled: true
    binary: auto
    model: deepseek/deepseek-reasoner
    default_workdir: ~/workspace
  kimi:
    enabled: false
    acp_url: http://127.0.0.1:9876
  claude:
    enabled: false
    binary: auto
  openrouter:
    enabled: false
    api_key: "${OPENROUTER_API_KEY}"
    default_model: "openai/gpt-4o"
```

### 环境变量

```bash
# Feishu
export FEISHU_APP_ID=cli_xxx
export FEISHU_APP_SECRET=xxx
export FEISHU_ENCRYPT_KEY=xxx
export FEISHU_VERIFICATION_TOKEN=xxx

# Provider API Keys（按需配置）
export DEEPSEEK_API_KEY=xxx
export KIMI_API_KEY=xxx
export OPENROUTER_API_KEY=xxx
```
