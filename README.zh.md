# VibeBridge

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **本地 AI 编程代理缺失的 IM 网关。**

在 60 秒内将 AI 编程代理部署到团队聊天中。VibeBridge 将**飞书**与本地 vibe-coding 工具（OpenCode、Kimi Code CLI、Claude Code、OpenClaw）连接起来，让你可以直接从聊天消息中编写、审查和部署代码。

---

## ✨ 核心特性

- **手机远程写代码**：在地铁上@机器人让它帮你写脚本。
- **团队协作**：产品经理、设计师直接在飞书群里提需求，AI 自动执行并回传结果截图。
- **多工具自由切换**：用 `/kimi`、`/claude`、`/openc` 前缀随时切换底层 Agent。
- **审批安全闸门**：内置基于规则的风险审批系统，高风险命令需人工确认后才执行。
- **一键部署**：支持 systemd 自启动、Docker、一键安装脚本。

---

## 🚀 快速开始

### 一键安装

```bash
curl -fsSL https://raw.githubusercontent.com/akliedrak/vibebridge/main/install.sh | bash
```

### 配置

交互式配置：

```bash
vibebridge init
```

自动化配置（适合 CI/脚本）：

```bash
export FEISHU_APP_ID=cli_xxx
export FEISHU_APP_SECRET=xxx
export FEISHU_ENCRYPT_KEY=xxx
export FEISHU_VERIFICATION_TOKEN=xxx
vibebridge init --non-interactive
```

### 启动服务

```bash
# 前台调试模式
vibebridge start

# 注册为 systemd 用户服务，开机自启
vibebridge start --install
```

### 在飞书中使用

```
@VibeBridge 写一个 FastAPI Hello World 并运行它
```

切换 Provider：

```
@VibeBridge /kimi 把这段代码改成异步的
@VibeBridge /claude 设计一个电商网站的 Postgres 表结构
@VibeBridge /openclaw 查看我的项目状态
```

---

## 🏗️ 架构

```
飞书消息
      ↓
FeishuAdapter (Webhook / WebSocket)
      ↓
会话管理 + 审批引擎
      ↓
Provider Router
      ↓
┌─────────┬─────────┬─────────┬─────────┐
│OpenCode │  Kimi   │ Claude  │OpenClaw │
│Provider │Provider │Provider │Provider │
└─────────┴─────────┴─────────┴─────────┘
      ↓
流式结果卡片回传到飞书
```

---

## 📋 Provider 支持状态

| Provider | 状态 | 说明 |
|----------|------|------|
| **OpenCode** | ✅ 完整支持 | 调用 `opencode run --format json`，流式解析输出 |
| **OpenClaw** | ✅ 健康检查+基础 | 连接本地 OpenClaw Gateway HTTP API |
| **Kimi Code CLI** | 🚧 部分支持 | 需先启动 `kimi acp`，通过 ACP/MCP 协议通信 |
| **Claude Code** | 🚧 部分支持 | 目前仅健康检查，执行层待实现 |

---

## ⚙️ 飞书开发者后台配置

1. 登录 [飞书开发者后台](https://open.feishu.cn/app)
2. 创建企业自建应用
3. **事件订阅**：
   - 请求 URL: `http://你的服务器IP:8000/im/feishu/webhook`
   - Verification Token: 填入 `.env` 中的 `FEISHU_VERIFICATION_TOKEN`
   - Encrypt Key: 填入 `.env` 中的 `FEISHU_ENCRYPT_KEY`
   - 开启加密
4. **订阅事件**：添加 `im.message.receive_v1`
5. **权限管理**：开启 `im:message`、`im:message:send_as_bot`
6. 发布应用，添加到目标群组

---

## 🛡️ 审批系统

VibeBridge 内置轻量级审批规则，防止误操作：

```yaml
approval:
  enabled: true
  rules:
    - provider: "*"
      pattern: "rm\s+-rf|drop\s+table"
      level: critical
    - provider: "*"
      pattern: "git\s+push|deploy"
      level: high
```

- **low**: 自动执行
- **medium**: 通知但允许
- **high / critical**: 发送审批卡片到飞书，需人工点击"批准"后才执行

---

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)。

欢迎提交 Issue 和 PR！
