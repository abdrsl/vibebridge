# AGENTS.md - VibeBridge 架构说明

## Project Overview

VibeBridge 是一个 FastAPI -based AI coding agent IM gateway，整合 Feishu (飞书) 与本地 AI 编程工具。

**当前核心架构** (v1.2.0): `TaskOrchestrator` + `ProviderRouter` + `IM Adapter`

```
Feishu Message
      ↓
IM Adapter (Feishu WebSocket / Webhook)
      ↓
TaskOrchestrator
      ↓
ProviderRouter
      ↓
┌─────────┬─────────┬─────────┬─────────┐
│OpenCode │  Kimi   │ Claude  │OpenRouter│
│Provider │Provider │Provider │Provider │
└─────────┴─────────┴─────────┴─────────┘
      ↓
Streaming result cards back to Feishu
```

## 架构演进

### 当前架构 (v1.2.0) ✅ 活跃使用

**核心组件**:

| 组件 | 文件 | 职责 |
|------|------|------|
| **TaskOrchestrator** | `src/vibebridge/tasks.py` | 任务调度、流式消费、卡片管理、授权重试 |
| **ProviderRouter** | `src/vibebridge/router.py` | Provider 注册、切换命令解析、消息路由 |
| **BaseProvider** | `src/vibebridge/providers/base.py` | Provider 抽象接口（create_task, stream_task, cancel_task, health_check） |
| **FeishuMultiBotManager** | `src/vibebridge/im/feishu.py` | 多机器人管理、卡片发送/更新、文件上传 |
| **ConstitutionalGuard** | `src/vibebridge/constitution_guard.py` | 危险命令拦截、授权解析 |
| **SessionManager** | `src/vibebridge/session.py` | 会话创建、provider 偏好、authorized_operations |

### 遗留架构 (v1.0.x) 📦 保留兼容

**6-Agent 多智能体系统** 代码仍保留在 `src/agents/` 和 `src/system.py` 中，但主入口 `src/main.py` 已迁移到新的 TaskOrchestrator 架构。

| Agent | 文件 | 状态 |
|-------|------|------|
| **Coordinator** | `src/agents/coordinator.py` | 遗留 |
| **OpenCode Agent** | `src/agents/opencode_agent.py` | 遗留 |
| **Feishu Agent** | `src/agents/feishu_agent.py` | 遗留 |
| **LLM Agent** | `src/agents/llm_agent.py` | 遗留 |
| **Memory Agent** | `src/agents/memory_agent.py` | 遗留 |
| **Skill Agent** | `src/agents/skill_agent.py` | 遗留 |

## 目录结构

```
src/
├── main.py                          # FastAPI 入口（ lifespan 管理）
├── server.py                        # 路由注册、服务启动
├── system.py                        # 遗留：多智能体系统管理器
├── vibebridge/
│   ├── main.py                      # 新版入口（provider 初始化）
│   ├── tasks.py                     # TaskOrchestrator（核心）
│   ├── router.py                    # ProviderRouter
│   ├── session.py                   # Session 模型与管理
│   ├── constitution_guard.py        # 危险命令拦截
│   ├── approval.py                  # 审批系统
│   ├── history.py                   # 对话历史管理
│   ├── gateway.py                   # 遗留网关逻辑
│   ├── agent_bridge.py              # 遗留 AgentBridge
│   ├── config.py                    # 配置加载
│   ├── cards/                       # 卡片渲染器
│   │   ├── start.py
│   │   ├── progress.py
│   │   ├── result.py
│   │   └── error.py
│   ├── providers/                   # Provider 实现
│   │   ├── base.py                  # 抽象基类
│   │   ├── opencode.py              # OpenCode CLI（含 session 连续性）
│   │   ├── kimi.py                  # Kimi Code CLI
│   │   ├── claude.py                # Claude Code CLI
│   │   └── openrouter.py            # OpenRouter API
│   ├── im/                          # IM 适配器
│   │   ├── base.py                  # BaseIMAdapter 接口
│   │   └── feishu.py                # Feishu 实现
│   ├── routes/                      # API 路由
│   │   ├── dashboard.py
│   │   ├── feishu.py
│   │   ├── internal.py
│   │   └── system.py
│   ├── admin/                       # Web 管理后台
│   │   └── router.py + templates/
│   ├── message_bus/                 # 遗留：消息总线
│   │   └── bus.py
│   └── legacy/                      # 遗留模块兼容层
│       ├── feishu_client.py
│       ├── feishu_webhook_handler.py
│       ├── opencode_integration.py
│       ├── session_manager.py
│       └── task_store.py
└── agents/                          # 遗留：6-agent 实现
    ├── base.py
    ├── coordinator.py
    ├── opencode_agent.py
    ├── feishu_agent.py
    ├── llm_agent.py
    ├── memory_agent.py
    └── skill_agent.py
```

## API Endpoints

### 核心端点

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | 系统状态 |
| GET | `/health` | 健康检查（含 provider 状态） |
| POST | `/feishu/webhook` | Feishu Webhook 回调 |

### 管理后台

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin` | Web 管理后台首页 |
| GET | `/admin/dashboard` | 仪表盘 |
| GET | `/admin/agents` | Agent 管理 |
| GET | `/admin/tasks` | 任务列表 |
| GET | `/admin/bots` | 机器人管理 |
| GET | `/admin/keys` | API 密钥管理 |

### 遗留端点（仍可用）

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/opencode/tasks` | 创建 OpenCode 任务 |
| GET | `/opencode/tasks` | 列出任务 |
| GET | `/opencode/tasks/{task_id}` | 获取任务详情 |
| GET | `/opencode/tasks/{task_id}/stream` | SSE 流式进度 |
| POST | `/opencode/tasks/{task_id}/abort` | 中止任务 |

## 核心设计原则

1. **Provider 插件化**: 新 provider 只需实现 BaseProvider 接口即可接入
2. **单卡片流式更新**: 一张卡片从任务开始更新到结束，避免消息刷屏
3. **Session 连续性**: 多轮对话自动保持上下文（OpenCode session 映射）
4. **安全拦截**: 危险命令实时拦截，需显式授权
5. **向后兼容**: 遗留模块保留在 `src/legacy/` 和 `src/agents/`，不影响新架构

## 添加新 Provider

1. 在 `src/vibebridge/providers/` 创建新文件，继承 `BaseProvider`
2. 实现 `create_task()`, `stream_task()`, `cancel_task()`, `health_check()`
3. 在 `src/vibebridge/main.py` 中注册到 `ProviderRouter`
4. 在 `src/vibebridge/router.py` 的 `_provider_map` 中添加切换别名

## 环境变量

必需：
- `FEISHU_APP_ID` - Feishu 应用 ID
- `FEISHU_APP_SECRET` - Feishu 应用密钥
- `FEISHU_ENCRYPT_KEY` - 飞书事件加密密钥
- `FEISHU_VERIFICATION_TOKEN` - 飞书验证令牌

Provider 按需配置：
- `DEEPSEEK_API_KEY` - DeepSeek API（OpenCode 默认使用）
- `KIMI_API_KEY` - Kimi API
- `OPENROUTER_API_KEY` - OpenRouter API

## Quick Start

```bash
# 启动服务（systemd user service，推荐）
systemctl --user start vibebridge
systemctl --user enable vibebridge

# 或手动启动
python -m uvicorn vibebridge.server:app --host 0.0.0.0 --port 9000

# 查看日志
journalctl --user -u vibebridge -f

# 健康检查
curl http://127.0.0.1:9000/health
```

## Troubleshooting

### Provider 不可用
- 检查 provider 健康状态：`curl http://127.0.0.1:9000/health`
- 检查对应 CLI 是否安装：`opencode --version`
- 检查 API 密钥是否配置正确

### Feishu 消息无响应
- 检查 WebSocket 连接状态：`journalctl --user -u vibebridge | grep "WebSocket"`
- 检查 app_id / app_secret 是否正确
- 确认飞书开发者平台事件订阅已配置

### Import Errors
- 确保 `PYTHONPATH` 包含 `src/` 目录
- 检查 `.venv` 虚拟环境是否激活
