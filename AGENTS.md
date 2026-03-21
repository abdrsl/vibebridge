# AGENTS.md - AI Product Lab Project Context

## Project Overview

This is a FastAPI-based AI coding agent service that integrates with:
- **Feishu (飞书)**: Receives webhook messages and sends back results
- **OpenCode CLI**: Executes AI-powered code development tasks

## Architecture

```
Feishu → FastAPI (Webhook) → OpenCode CLI → Code Development → Feishu (Results)
```

### Core Modules

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI entry point, route registration |
| `app/opencode_integration.py` | Manages OpenCode CLI execution and task lifecycle |
| `app/feishu_client.py` | Feishu API client for sending messages and cards |
| `app/task_store.py` | JSON file-based task storage |
| `app/task_parser.py` | Parses Feishu webhook payloads |
| `app/llm.py` | Direct LLM API calls (DeepSeek) |

## API Endpoints

### OpenCode Task Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/opencode/tasks` | Create a new OpenCode task |
| GET | `/opencode/tasks` | List all OpenCode tasks |
| GET | `/opencode/tasks/{task_id}` | Get task details |
| GET | `/opencode/tasks/{task_id}/stream` | SSE stream for real-time progress |
| POST | `/opencode/tasks/{task_id}/abort` | Abort a running task |

### Feishu Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/feishu/webhook` | Original webhook (DeepSeek LLM) |
| POST | `/feishu/webhook/opencode` | New webhook (OpenCode Agent) |

## Data Storage

Tasks are stored as JSON files in `data/tasks/`.

## Environment Variables

Required for Feishu integration:
- `FEISHU_APP_ID` - Feishu application ID
- `FEISHU_APP_SECRET` - Feishu application secret

Required for OpenCode:
- OpenCode CLI must be installed and accessible in PATH
- LLM provider configured (OpenCode Zen, Anthropic, OpenAI, etc.)

## Development Guidelines

1. **Task Status Flow**: pending → running → completed/failed
2. **Feishu Notifications**: Progress and results are sent as interactive cards
3. **SSE Streaming**: Real-time updates available via `/opencode/tasks/{id}/stream`

## Testing

```bash
# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Create an OpenCode task
curl -X POST http://127.0.0.1:8000/opencode/tasks \
  -H "Content-Type: application/json" \
  -d '{"message": "请在 data/tasks 目录下创建一个 README.md 文件"}'

# Check task status
curl http://127.0.0.1:8000/opencode/tasks/oc_xxx

# Stream task progress
curl http://127.0.0.1:8000/opencode/tasks/oc_xxx/stream
```
