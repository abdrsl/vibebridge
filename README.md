# OpenCode v2 测试项目

这是一个用于测试 OpenCode v2 格式的简单项目。

## 项目结构

```
ai-project/
├── app/
│   ├── main.py
│   ├── opencode_integration.py
│   ├── feishu_client.py
│   ├── task_store.py
│   ├── task_parser.py
│   └── llm.py
├── data/
│   └── tasks/
├── tests/
├── requirements.txt
└── README.md
```

## 功能特性

- **OpenCode CLI 集成**: 执行 AI 驱动的代码开发任务
- **Feishu 飞书集成**: 接收 webhook 消息并发送结果
- **任务管理**: 创建、跟踪和监控 OpenCode 任务
- **实时进度**: 通过 SSE 流获取实时更新
- **任务存储**: JSON 文件存储任务状态

## 快速开始

1. 安装依赖:
   ```bash
   pip install -r requirements.txt
   ```

2. 设置环境变量:
   ```bash
   export FEISHU_APP_ID=your_app_id
   export FEISHU_APP_SECRET=your_app_secret
   ```

3. 启动服务器:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. 创建 OpenCode 任务:
   ```bash
   curl -X POST http://127.0.0.1:8000/opencode/tasks \
     -H "Content-Type: application/json" \
     -d '{"message": "请创建一个简单的Python脚本"}'
   ```

## API 端点

### OpenCode 任务管理
- `POST /opencode/tasks` - 创建新任务
- `GET /opencode/tasks` - 列出所有任务
- `GET /opencode/tasks/{task_id}` - 获取任务详情
- `GET /opencode/tasks/{task_id}/stream` - SSE 流获取实时进度
- `POST /opencode/tasks/{task_id}/abort` - 中止运行中的任务

### Feishu 集成
- `POST /feishu/webhook` - 原始 webhook (DeepSeek LLM)
- `POST /feishu/webhook/opencode` - 新 webhook (OpenCode Agent)

## 任务状态

任务状态遵循以下流程:
- `pending` → `running` → `completed`/`failed`

## 依赖项

- FastAPI
- Uvicorn
- Pydantic
- Requests
- OpenCode CLI

## 许可证

MIT