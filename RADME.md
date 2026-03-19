```md
# ai-project

一个最小可运行的 FastAPI 服务，用于：

- 接收 `/feishu/webhook` 请求
- 从请求中提取文本任务
- 调用 LLM 生成结果
- 将任务保存到本地 `data/tasks/*.json`
- 提供任务列表与任务详情查询接口

---

## 功能概览

当前项目已经具备以下能力：

- FastAPI 服务启动与热重载
- 接收 webhook 请求
- 解析输入文本
- 调用 LLM 生成结果
- 将任务按 JSON 文件落盘
- 查看任务列表 `/tasks`
- 查看任务详情 `/tasks/{task_id}`
- 使用任务状态表示处理结果：
  - `queued`
  - `completed`
  - `failed`
  - `ignored`

---

## 项目结构

```text
ai-project/
├── app/
│   ├── llm.py
│   ├── main.py
│   ├── task_parser.py
│   └── task_store.py
├── data/
│   └── tasks/
├── infra/
│   ├── .env
│   └── docker-compose.yml
├── scripts/
│   └── test_deepseek.py
├── .env
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── requirements.lock.txt
└── test_playwright.py
```

---

## 环境要求

建议使用：

- Python 3.10+
- Linux / macOS / WSL

---

## 1. 安装与启动

### 进入项目目录

```bash
cd ~/workspace/ai-project
```

### 创建虚拟环境

如果还没有 `.venv`：

```bash
python3 -m venv .venv
```

### 激活虚拟环境

```bash
source .venv/bin/activate
```

### 安装依赖

```bash
pip install -r requirements.txt
```

---

## 2. 环境变量配置

项目通过 `.env` 读取配置。

如果还没有配置文件，可以从模板复制：

```bash
cp .env.example .env
```

然后根据你的实际情况填写 API Key 或模型配置。

例如你可能会配置：

```env
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

> 实际需要哪些变量，取决于 `app/llm.py` 中当前接入的是哪个模型服务。

---

## 3. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后可访问：

- 根路径：<http://127.0.0.1:8000>
- API 文档：<http://127.0.0.1:8000/docs>

---

## 4. 接口说明

### 4.1 健康检查 / 根路径

```http
GET /
```

示例：

```bash
curl http://127.0.0.1:8000/
```

---

### 4.2 接收 webhook

```http
POST /feishu/webhook
Content-Type: application/json
```

#### 最小测试请求

如果你只是想快速验证流程，可以直接发送：

```bash
curl -X POST http://127.0.0.1:8000/feishu/webhook \
  -H "Content-Type: application/json" \
  -d '{"text":"设计一个适合PETG打印的桌面线缆整理器，强调强度和易打印性"}'
```

#### 可能的返回结果

```json
{
  "ok": true,
  "source": "feishu",
  "parsed_text": "设计一个适合PETG打印的桌面线缆整理器，强调强度和易打印性",
  "task": {
    "task_type": "design_request",
    "raw_text": "设计一个适合PETG打印的桌面线缆整理器，强调强度和易打印性",
    "status": "completed"
  },
  "llm_result": "可以设计为带底座、双侧限位、圆角过渡、无支撑打印……",
  "task_id": "20260319_232554_c9df69ee",
  "saved": {
    "task_id": "20260319_232554_c9df69ee",
    "file_path": "data/tasks/20260319_232554_c9df69ee.json"
  }
}
```

---

### 4.3 查看任务列表

```http
GET /tasks
```

示例：

```bash
curl http://127.0.0.1:8000/tasks
```

示例返回：

```json
{
  "ok": true,
  "items": [
    {
      "task_id": "20260319_232554_c9df69ee",
      "source": "feishu",
      "parsed_text": "设计一个适合PETG打印的桌面线缆整理器，强调强度和易打印性",
      "task_type": "design_request",
      "status": "completed",
      "file_path": "data/tasks/20260319_232554_c9df69ee.json"
    }
  ]
}
```

#### 支持参数

- `limit`：返回条数，默认 20

示例：

```bash
curl "http://127.0.0.1:8000/tasks?limit=10"
```

---

### 4.4 查看任务详情

```http
GET /tasks/{task_id}
```

示例：

```bash
curl http://127.0.0.1:8000/tasks/20260319_232554_c9df69ee
```

示例返回：

```json
{
  "ok": true,
  "item": {
    "source": "feishu",
    "parsed_text": "设计一个适合PETG打印的桌面线缆整理器，强调强度和易打印性",
    "task": {
      "task_type": "design_request",
      "raw_text": "设计一个适合PETG打印的桌面线缆整理器，强调强度和易打印性",
      "status": "completed"
    },
    "llm_result": "可以设计为带底座、双侧限位、圆角过渡、无支撑打印……",
    "task_id": "20260319_232554_c9df69ee"
  }
}
```

---

## 5. 数据存储

任务数据保存在本地目录：

```text
data/tasks/
```

每次 webhook 处理后会生成一个 JSON 文件，例如：

```text
data/tasks/20260319_232554_c9df69ee.json
```

你也可以直接查看文件内容：

```bash
python -m json.tool data/tasks/20260319_232554_c9df69ee.json
```

---

## 6. 状态说明

当前任务状态含义如下：

| 状态 | 含义 |
|------|------|
| `queued` | 已识别为任务，但尚未完成处理 |
| `completed` | LLM 处理成功，结果已保存 |
| `failed` | LLM 处理失败 |
| `ignored` | 请求中没有可处理文本，或不属于有效任务 |

### 当前推荐语义

- 无文本输入 → `ignored`
- 有文本且 LLM 成功 → `completed`
- 有文本但 LLM 失败 → `failed`

---

## 7. 关键模块说明

### `app/main.py`

FastAPI 应用入口，负责：

- 注册路由
- 接收 webhook
- 调用解析逻辑
- 调用 LLM
- 保存任务结果

### `app/task_parser.py`

负责从 webhook body 中提取文本，并构造初始任务结构。

### `app/task_store.py`

负责：

- 创建任务目录
- 生成任务 ID
- 保存任务到 JSON 文件
- 获取任务详情
- 返回任务摘要列表

### `app/llm.py`

负责统一封装 LLM 调用逻辑。

---

## 8. 常用调试命令

### 查看任务目录

```bash
ls -lah data/tasks
```

### 格式化查看任务文件

```bash
python -m json.tool data/tasks/<task_id>.json
```

### 查看某个任务详情接口

```bash
curl http://127.0.0.1:8000/tasks/<task_id>
```

### 查看任务列表

```bash
curl http://127.0.0.1:8000/tasks
```

### 指定返回数量

```bash
curl "http://127.0.0.1:8000/tasks?limit=5"
```

---

## 9. 常见问题

### 1）`Address already in use`

启动 `uvicorn` 时如果看到：

```text
ERROR: [Errno 98] Address already in use
```

说明 8000 端口已经被占用，通常是之前的服务还在运行。

可以先找到进程：

```bash
lsof -i :8000
```

然后结束进程：

```bash
kill <PID>
```

再重新启动服务。

---

### 2）为什么旧任务状态是 `queued`，但又有 `llm_result`？

这通常是历史数据导致的。

早期逻辑里任务先被标记为 `queued`，后续虽然生成了 `llm_result`，但保存前没有把状态改为 `completed``。

这不是当前新逻辑还在出错，而是旧 JSON 文件保留了旧状态。

可以手动修正旧文件中的：

```json
"status": "queued"
```

为：

```json
"status": "completed"
```

---

### 3）为什么 `/tasks` 返回摘要，而 `/tasks/{task_id}` 返回完整内容？

这是刻意设计的：

- `/tasks`：适合列表页，只返回摘要，避免太长
- `/tasks/{task_id}`：适合详情页，返回完整 JSON

这样更清晰，也更符合 API 习惯。

---

## 10. 测试建议

当前可以先用最小方式做手工验证：

1. 启动服务
2. POST 一个 webhook
3. GET `/tasks`
4. GET `/tasks/{task_id}`
5. 查看 `data/tasks/*.json`

项目中也包含一些测试相关依赖：

- `pytest`
- `pytest-asyncio`
- `httpx`
- `playwright`

后续可以补充：

- API 单元测试
- webhook 集成测试
- LLM 调用 mock 测试

---

## 11. 后续可扩展方向

当前版本是一个“最小闭环”，后续可以继续扩展：

### 工程化
- 更规范的异常处理
- 统一响应结构
- 日志规范化
- 配置分层管理

### 数据层
- 从本地 JSON 升级到 PostgreSQL
- 使用 Redis 做队列或缓存
- 使用 Qdrant 做向量检索

### 任务处理
- 改为真正异步任务队列
- 增加重试机制
- 增加任务时间戳：`created_at` / `updated_at`

### 产品能力
- 更完整的 Feishu 事件兼容
- 多模型切换
- 任务分类与标签
- Web 管理界面

---

## 12. 一次性快速验证流程

如果你想快速从零跑通，可以按下面顺序执行：

```bash
cd ~/workspace/ai-project
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

另开一个终端：

```bash
cd ~/workspace/ai-project
source .venv/bin/activate

curl -X POST http://127.0.0.1:8000/feishu/webhook \
  -H "Content-Type: application/json" \
  -d '{"text":"设计一个适合PETG打印的桌面线缆整理器，强调强度和易打印性"}'

curl http://127.0.0.1:8000/tasks
curl http://127.0.0.1:8000/tasks/<task_id>
```

---

## 13. 当前阶段结论

本项目当前已经完成第一阶段目标：

- 服务可运行
- 接口可访问
- 请求可解析
- LLM 可调用
- 结果可保存
- 列表与详情可查看
- 新任务状态逻辑已闭环

也就是说，它已经是一个**可演示、可继续迭代的最小版本**。

---
```
