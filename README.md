# VibeBridge

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **The missing IM gateway for local AI coding agents.**

Deploy an AI coding agent to your team chat in 60 seconds. VibeBridge connects **Feishu (Lark)** to your local vibe-coding tools — OpenCode, Kimi Code CLI, Claude Code, and OpenClaw — so you can write, review, and deploy code directly from a chat message.

---

## ✨ Why VibeBridge?

- **Remote coding from your phone**: `@VibeBridge write a Python script to backup my DB` while you're on the subway.
- **Team collaboration**: Product managers and designers can request simple changes in a Feishu group, and the agent executes them automatically.
- **Multi-tool freedom**: Switch between OpenCode, Kimi, Claude, or OpenClaw with a simple command prefix (`/kimi`, `/claude`, `/openc`).
- **Approval gate for risky ops**: Built-in rule-based approval system prevents destructive commands from running without human consent.

---

## 🚀 Quick Start

### One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/akliedrak/vibebridge/main/install.sh | bash
```

### Configure

```bash
vibebridge init
# Interactive prompts for Feishu App ID, Secret, Encrypt Key, etc.
```

Or automated (CI-friendly):

```bash
export FEISHU_APP_ID=cli_xxx
export FEISHU_APP_SECRET=xxx
export FEISHU_ENCRYPT_KEY=xxx
export FEISHU_VERIFICATION_TOKEN=xxx
vibebridge init --non-interactive
```

### Start the server

```bash
# Foreground mode (good for testing)
vibebridge start

# Or install as a systemd user service for auto-start on boot
vibebridge start --install
```

### Chat with your agent

In Feishu, simply send:

```
@VibeBridge write a FastAPI hello-world app and run it
```

Switch providers on the fly:

```
@VibeBridge /kimi refactor this function to use async/await
@VibeBridge /claude design a PostgreSQL schema for an e-commerce site
@VibeBridge /openclaw check my project status
```

---

## 🏗️ Architecture

```
Feishu Message
      ↓
FeishuAdapter (webhook / websocket)
      ↓
Session Manager + Approval Engine
      ↓
Provider Router
      ↓
┌─────────┬─────────┬─────────┬─────────┐
│OpenCode │  Kimi   │ Claude  │OpenClaw │
│Provider │Provider │Provider │Provider │
└─────────┴─────────┴─────────┴─────────┘
      ↓
Streaming result cards back to Feishu
```

- **Providers**: Pluggable adapters for each local AI coding tool.
- **IM Adapters**: Currently Feishu (Lark). Slack / Discord adapters can be added by implementing `BaseIMAdapter`.
- **Approval Engine**: Regex-based risk rules. High/critical commands trigger an interactive approval card before execution.

---

## 📋 Provider Support Matrix

| Provider | Status | How it works |
|----------|--------|--------------|
| **OpenCode** | ✅ Full | Spawns `opencode run --format json` with streaming output. |
| **OpenClaw** | ✅ Health + Basic | Connects to local OpenClaw Gateway HTTP API. |
| **Kimi Code CLI** | 🚧 Partial | Requires `kimi acp` running; bridge talks via ACP/MCP protocol. |
| **Claude Code** | 🚧 Partial | Health check only; execution layer coming soon. |

---

## ⚙️ Configuration

VibeBridge stores its config in `~/.config/vibebridge/config.yaml`.

Example:

```yaml
feishu:
  app_id: "${FEISHU_APP_ID}"
  app_secret: "${FEISHU_APP_SECRET}"
  encrypt_key: "${FEISHU_ENCRYPT_KEY}"
  verification_token: "${FEISHU_VERIFICATION_TOKEN}"
  mode: websocket  # or webhook

agents:
  default_provider: opencode
  opencode:
    enabled: true
    binary: auto
    model: deepseek/deepseek-chat
    default_workdir: ~/workspace
  openclaw:
    enabled: true
    gateway_url: http://127.0.0.1:18789
  kimi:
    enabled: false
    acp_url: http://127.0.0.1:9876
  claude:
    enabled: false
    binary: auto

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

Environment variables are automatically loaded from `.env` in the working directory.

---

## 🛡️ Security & Approval

VibeBridge includes a lightweight approval system to prevent accidental damage:

- **Low risk**: Auto-execute (e.g., `write a script`).
- **Medium risk**: Notify but allow (e.g., `install a package`).
- **High / Critical risk**: Pause execution and send an approval card to Feishu. The command only runs after a human clicks **Approve**.

---

## 🐳 Docker (Optional)

```bash
docker-compose up
```

See `docker-compose.yml` for details.

---

## 🛠️ Development

```bash
git clone https://github.com/akliedrak/vibebridge.git
cd vibebridge
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

---

## 🤝 Contributing

Issues and PRs are welcome! If you want to add a new Provider (e.g., Cline, Continue) or IM Adapter (Slack, Discord), please open an issue first to discuss the interface.
