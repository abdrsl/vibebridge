# AGENTS.md - OpenCode-Feishu Bridge Multi-Agent Architecture

## Project Overview

This is a FastAPI-based AI coding agent service with a modular multi-agent architecture, integrating:
- **Feishu (飞书)**: Receives webhook messages and sends back results via Feishu Agent
- **OpenCode CLI**: Executes AI-powered code development tasks via OpenCode Agent
- **Multi-Agent System**: Coordinated system of 6 specialized agents
- **Legacy Compatibility**: Backward compatibility with original modules in `src/legacy/`

## Architecture

```
Feishu → FastAPI (Webhook) → Multi-Agent System → Agent Coordination → Results → Feishu
```

### Multi-Agent System Components

| Agent | Purpose | Capabilities |
|-------|---------|--------------|
| **Coordinator** | Orchestrates agent communication | Message routing, task delegation |
| **OpenCode Agent** | Executes OpenCode CLI tasks | Task creation, progress tracking, skill execution |
| **Feishu Agent** | Handles Feishu API communication | Send cards, send text, file uploads |
| **LLM Agent** | Processes natural language requests | DeepSeek API integration, prompt engineering |
| **Memory Agent** | Maintains conversation context | Session storage, knowledge retention |
| **Skill Agent** | Manages executable skills | Skill loading, execution, file sending |

### Directory Structure

```
src/
├── main.py                 # FastAPI application with lifespan management
├── system.py              # Multi-agent system manager
├── message_bus/           # Inter-agent communication
│   └── bus.py            # Message bus implementation
├── agents/                # Agent implementations
│   ├── coordinator.py     # Coordinator agent
│   ├── opencode_agent.py  # OpenCode integration agent
│   ├── feishu_agent.py    # Feishu API agent
│   ├── llm_agent.py       # LLM processing agent
│   ├── memory_agent.py    # Memory management agent
│   └── skill_agent.py     # Skill execution agent
└── legacy/                # Legacy modules for compatibility
    ├── feishu_client.py   # Original Feishu client
    ├── opencode_integration.py # OpenCode task management
    ├── llm.py             # Direct LLM API calls
    ├── task_store.py      # JSON file-based task storage
    ├── task_parser.py     # Feishu payload parsing
    ├── session_manager.py # Session management
    ├── secure_config.py   # Encrypted configuration
    └── ... (other legacy modules)
```

### Key Design Principles

1. **Modularity**: Each agent handles a specific concern
2. **Loose Coupling**: Agents communicate via message bus
3. **Backward Compatibility**: Legacy modules preserved in `src/legacy/`
4. **Gradual Migration**: Endpoints can use agents or legacy code
5. **Extensibility**: New agents can be added without breaking existing system

## API Endpoints

### Multi-Agent System Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | System status and version |
| GET | `/health` | Health check with multi-agent status |
| GET | `/system/status` | Detailed agent status and capabilities |

### OpenCode Task Management (Legacy-Compatible)

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
| POST | `/feishu/webhook` | Legacy webhook (DeepSeek LLM fallback) |
| POST | `/feishu/webhook/opencode` | OpenCode integration webhook |

## Agent Communication

### Message Types

```python
class MessageType(Enum):
    # System messages
    REGISTER = "register"
    REGISTRATION_CONFIRMED = "registration_confirmed"
    # Task messages
    TASK_CREATE = "task_create"
    TASK_RESULT = "task_result"
    TASK_PROGRESS = "task_progress"
    # Feishu messages
    SEND_CARD = "send_card"
    SEND_TEXT = "send_text"
    # LLM messages
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    # Memory messages
    STORE_MEMORY = "store_memory"
    RETRIEVE_MEMORY = "retrieve_memory"
    # Skill messages
    EXECUTE_SKILL = "execute_skill"
    SKILL_RESULT = "skill_result"
    # Custom messages
    CUSTOM = "custom"
```

### Message Flow Example

1. Webhook receives Feishu message
2. FastAPI routes to `/feishu/webhook`
3. Endpoint checks multi-agent system status
4. If system running: sends `LLM_REQUEST` to LLM Agent
5. LLM Agent processes, sends `LLM_RESPONSE` to Coordinator
6. Coordinator routes response to Feishu Agent via `SEND_CARD`
7. Feishu Agent uses legacy `feishu_client` to send card
8. Results stored via Memory Agent

## Migration Status

### ✅ Completed
- Multi-agent system implementation (`src/system.py`)
- Message bus for inter-agent communication
- All 6 agent implementations
- Main application migration (`app/main.py` → `src/main.py`)
- Legacy modules moved to `src/legacy/` with updated imports
- Health endpoint fix (asyncio event loop issue)

### 🔄 In Progress
- Test suite updates for new import paths
- Endpoint migration to use agent messaging
- Documentation updates

### 📋 Planned
- Full migration from legacy to agent-based endpoints
- Enhanced agent capabilities
- Performance monitoring
- Deployment automation

## Development Guidelines

### Adding a New Agent

1. Create agent class in `src/agents/` inheriting from `BaseAgent`
2. Implement required methods: `start()`, `stop()`, capability handlers
3. Register with message bus in `__init__`
4. Add to `src/system.py` agent creation
5. Update documentation

### Message Handling

```python
async def handle_message_type(self, message: Message):
    # Process message
    result = await self.process_payload(message.payload)
    
    # Send response
    await self.send_message(
        MessageType.RESPONSE_TYPE,
        recipient=message.sender,
        payload={"result": result}
    )
```

### Testing

```bash
# Run multi-agent system test
python test_multi_agent_start.py

# Run API tests
pytest tests/test_api.py

# Run specific test
pytest tests/test_api.py::test_root -xvs
```

## Environment Variables

Required for multi-agent system:
- `FEISHU_APP_ID` - Feishu application ID (for Feishu Agent)
- `FEISHU_APP_SECRET` - Feishu application secret (encrypted)
- `DEEPSEEK_API_KEY` - DeepSeek API key (encrypted, for LLM Agent)
- `DEEPSEEK_BASE_URL` - DeepSeek API base URL
- `DEEPSEEK_MODEL` - DeepSeek model name

## Quick Start

```bash
# Start the server with multi-agent system
./manage.sh start

# Check system status
curl http://127.0.0.1:8000/system/status

# Create OpenCode task
curl -X POST http://127.0.0.1:8000/opencode/tasks \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a README.md file"}'
```

## Troubleshooting

### Multi-Agent System Not Starting
- Check logs in `logs/server.log`
- Verify environment variables are set
- Check if OpenCode CLI is installed: `opencode --version`

### Health Endpoint Errors
- Ensure `asyncio.get_event_loop()` is not called in synchronous context
- Use `time.time()` instead for timestamps

### Import Errors
- Verify `src/legacy/__init__.py` exists
- Check all import paths updated from `app.` to `src.legacy.`