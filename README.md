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
- **Permission control with passphrase**: Use a secret passphrase in messages to grant elevated permissions for sensitive operations.

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

#### WebSocket mode (Recommended)

WebSocket mode uses a persistent connection to Feishu — **no public URL required**.

```bash
# Start with WebSocket support
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# Or in the project directory
./venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Verify WebSocket is connected:
```bash
curl http://localhost:8000/health
# Expected: {"ok":true,"multi_agent_system":true}
```

#### Webhook mode

Webhook mode requires a public URL for Feishu to push events to.

```bash
vibebridge start
```

Configure the Feishu webhook URL: `http://your-public-ip:8000/im/feishu/webhook`

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
@VibeBridge /openrouter write a Python script with GPT-4o
```

---

## 🏗️ Architecture

```
Feishu Message
      ↓
FeishuAdapter (webhook / websocket)
      ↓
Session Manager
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
- **Permission passphrase**: Messages containing a secret passphrase bypass security checks for elevated permissions.

---

## 📋 Provider Support Matrix

| Provider | Status | How it works |
|----------|--------|--------------|
| **OpenCode** | ✅ Full | Spawns `opencode run --format json` with streaming output. |
| **OpenRouter** | ✅ Full | Connects to OpenRouter API with 100+ models support. |
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
  openrouter:
    enabled: false
    api_key: "${OPENROUTER_API_KEY}"
    default_model: "openai/gpt-4o"
    base_url: "https://openrouter.ai/api/v1"

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

### Feishu Developer Console Setup (WebSocket mode)

1. Go to [Feishu Open Platform](https://open.feishu.cn/app) → your app → **Event Subscriptions**
2. Enable **"使用长连接接收消息"** (Use long connection to receive messages)
3. Subscribe to the following events:
   - `im.message.receive_v1` — receive messages
   - `p2.card.action.trigger` — card button clicks (optional)
4. **No Request URL configuration needed** — WebSocket handles everything
5. Publish the app version to make it active

### Switching between WebSocket and Webhook

| Feature | WebSocket | Webhook |
|---------|-----------|---------|
| Public URL required | ❌ No | ✅ Yes |
| Setup complexity | Low | Medium (need tunnel/proxy) |
| Real-time cards | ✅ Full support | ✅ Full support |
| Recommended for | Local dev, personal use | Production server |

To switch modes, update `~/.config/vibebridge/config.yaml`:

```yaml
feishu:
  mode: websocket   # or webhook
```

Then restart the server.

---

## 🛡️ Security & Permissions

VibeBridge provides multiple security layers to prevent accidental damage:

### Permission Passphrase System
- **Default mode**: All commands go through constitution checks to prevent destructive operations.
- **Elevated permissions**: Include a secret passphrase in your message to bypass security checks for sensitive operations.
- **Environment variable**: Set `FEISHU_PERMIT_PASSWORD` to define your passphrase.

### Security Features
- **Constitution checks**: OpenCode's built-in safety rules are applied by default.
- **WebSocket mode optimizations**: Real-time progress cards show up to 400 lines of output.
- **Clean output filtering**: Tool call lines and intermediate steps are filtered from final results.
- **Table rendering**: Markdown tables in output are automatically rendered in Feishu cards.

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

```
pytest
```

---

## 🌐 OpenRouter Integration

VibeBridge now supports OpenRouter API with access to 100+ AI models including GPT-4o, Claude 3.5, Gemini, Llama, and more.

### Quick Start with OpenRouter

1. Get your API key from [OpenRouter](https://openrouter.ai/)
2. Set environment variable:
   ```bash
   export OPENROUTER_API_KEY=your_key_here
   ```
3. Test all available models:
   ```bash
   vibebridge test-openrouter
   ```
4. Use in chat:
   ```
   @VibeBridge /openrouter write a Python script to analyze data
   ```

### Features
- ✅ Test all 100+ models with one command
- ✅ Real-time streaming responses
- ✅ Automatic model availability checking
- ✅ Results saved to JSON for analysis
- ✅ Integrated with approval system

See [docs/OPENROUTER_README.md](docs/OPENROUTER_README.md) for detailed documentation.

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

---

## 🤝 Contributing

Issues and PRs are welcome! If you want to add a new Provider (e.g., Cline, Continue) or IM Adapter (Slack, Discord), please open an issue first to discuss the interface.
