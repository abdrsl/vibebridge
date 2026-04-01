# OpenCode-Feishu Bridge Multi-Agent System

[![Version](https://img.shields.io/badge/version-1.0.1-blue)](./docs/VERSION.md) [![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

一个基于FastAPI的AI编程代理服务，采用模块化多智能体架构，集成飞书和OpenCode CLI。

## 🏗️ 系统架构

```
飞书 → FastAPI (Webhook/WebSocket) → 多智能体系统 → 智能体协调 → 结果 → 飞书
```

### 核心架构特点

- **多智能体系统**: 6个专门智能体协调工作，通过消息总线通信
- **双模式通信**: 支持Webhook（事件驱动）和WebSocket（长连接）两种方式
- **模块化设计**: 智能体可独立开发、测试和部署
- **向后兼容**: 保留完整的legacy模块，确保平滑升级

### 智能体组件

| 智能体 | 用途 | 能力 |
|-------|------|------|
| **协调器** | 协调智能体通信 | 消息路由、任务委派、错误处理 |
| **OpenCode代理** | 执行OpenCode CLI任务 | 任务创建、进度跟踪、技能执行、实时流 |
| **飞书代理** | 处理飞书API通信 | 发送卡片、发送文本、文件上传、Webhook处理 |
| **LLM代理** | 处理自然语言请求 | DeepSeek API集成、提示工程、多模型支持 |
| **内存代理** | 维护对话上下文 | 会话存储、知识保留、上下文管理 |
| **技能代理** | 管理可执行技能 | 技能加载、执行、文件发送、技能注册 |

## ✨ 核心功能

### 多智能体系统
- **🤖 6个专门智能体**: 协调器、OpenCode代理、飞书代理、LLM代理、内存代理、技能代理
- **🔌 消息总线通信**: 基于发布-订阅模式的智能体间通信
- **🔄 异步处理**: 全异步架构，支持高并发请求

### 飞书集成
- **📱 双模式通信**: Webhook（事件驱动）和WebSocket（长连接）支持
- **🔐 加密通信**: AES-192加密，支持飞书事件订阅加密/解密
- **🎨 交互式卡片**: 丰富的卡片模板（开始、进度、结果、错误、帮助）
- **📎 文件支持**: 支持文件上传和下载

### OpenCode集成
- **🔧 OpenCode CLI集成**: 完整的OpenCode CLI命令支持
- **📋 任务管理**: 创建、跟踪、监控、中止OpenCode任务
- **🔄 实时进度**: Server-Sent Events (SSE)流式更新
- **🧠 技能系统**: 可扩展的技能库，支持自定义命令

### 安全与可靠性
- **🔒 环境加密**: 敏感配置支持加密存储
- **⏱️ 速率限制**: API端点速率限制保护
- **💾 会话管理**: 基于Redis的会话存储
- **📊 健康监控**: 完整的系统健康检查端点

### 开发与部署
- **🐳 Docker支持**: 完整的Docker和Docker Compose配置
- **📦 依赖管理**: 生产环境和开发环境分离
- **🔧 管理脚本**: 完整的启动、停止、监控脚本
- **🌐 隧道支持**: ngrok和localtunnel自动隧道管理

## 📋 自定义命令支持

系统支持多种自定义命令，可通过飞书消息直接调用：

### 会话管理
- `清空session` - 清空当前会话，重置对话上下文
- `查看session` - 查看当前会话状态和历史

### 模型管理
- `kimi` - 切换到Kimi模型（Moonshot API）
- `deepseek` - 切换到Deepseek模型
- `模型` - 显示当前可用模型列表
- `切换模型 [模型名]` - 切换到指定模型

### 开发命令
- `启动服务器` - 启动本地开发服务器
- `git 提交 [消息]` - 执行Git提交操作
- `运行测试` - 运行项目测试套件
- `检查代码` - 运行代码质量检查

### 系统命令
- `系统状态` - 查看多智能体系统状态
- `健康检查` - 执行系统健康检查
- `重启服务` - 重启服务进程
- `查看日志` - 查看最近日志

### 文件操作
- `发送文件 [路径]` - 发送指定文件到飞书
- `查看文件` - 查看可用的文件列表
- `清理文件` - 清理临时文件

> 注：更多自定义命令可通过扩展技能系统添加

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 环境变量

创建`.env`文件：

```bash
# Feishu 应用配置
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret

# Feishu Webhook 加密配置
FEISHU_ENCRYPT_KEY=your_encrypt_key          # 飞书控制台中的"Encrypt Key"
FEISHU_VERIFICATION_TOKEN=your_verification_token  # 飞书控制台中的"Verification Token"

# LLM API 配置
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 隧道配置 (可选)
TUNNEL_TYPE=ngrok  # 或 localtunnel
NGROK_AUTHTOKEN=your_ngrok_authtoken  # ngrok v3+ 认证令牌
```

### 安全配置（加密）

敏感环境变量（如API密钥、应用密钥）支持加密存储。系统使用`src/legacy/secure_config.py`自动解密以`_ENC`后缀的变量（例如`FEISHU_APP_SECRET_ENC`）。加密功能需要设置主密钥（`AI_MASTER_KEY`环境变量或`~/.ai-product-lab/master.key`文件）。详情请参阅[docs/SECURITY.md](docs/SECURITY.md)。

### 配置检查

运行配置检查脚本验证系统就绪状态：

```bash
python scripts/check_feishu_config.py
```

该脚本将显示当前隧道URL、加密状态，并生成详细的Feishu控制台配置步骤。

### 启动服务

```bash
# 使用管理脚本（推荐）
./manage.sh start

# 使用启动脚本
./start_all.sh

# 直接运行
python src/main.py

# 使用Docker
docker-compose up

# 开发模式（带热重载）
./manage.sh dev
```

### 检查系统状态

```bash
curl http://127.0.0.1:8000/system/status
```

### 创建OpenCode任务

```bash
curl -X POST http://127.0.0.1:8000/opencode/tasks \
  -H "Content-Type: application/json" \
  -d '{"message": "创建一个简单的Python脚本"}'
```

### Feishu Webhook 配置

> **提示**: 运行 `python check_feishu_config.py` 获取当前隧道URL和确切的配置值。

1. **登录飞书开发者控制台**: [https://open.feishu.cn/app](https://open.feishu.cn/app)
2. **配置事件订阅**:
   - **请求URL**: `https://your-tunnel-url/feishu/webhook/opencode`
   - **Verification Token**: 使用 `.env` 中的 `FEISHU_VERIFICATION_TOKEN`
   - **Encrypt Key**: 使用 `.env` 中的 `FEISHU_ENCRYPT_KEY`
   - **启用加密**: 开启加密功能
3. **订阅事件**: `im.message.receive_v1` (接收消息)
4. **权限配置**: 启用 `im:message` 和 `im:message:send_as_bot` 权限

> 详细配置指南请参考 [docs/FEISHU_SETUP.md](docs/FEISHU_SETUP.md)

## 📡 API端点

### 多智能体系统端点

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| GET | `/` | 系统状态和版本信息 | 公开 |
| GET | `/health` | 健康检查（含多智能体状态） | 公开 |
| GET | `/system/status` | 详细的智能体状态和能力 | 公开 |
| GET | `/agents` | 列出所有智能体及其状态 | 公开 |

### OpenCode任务管理（向后兼容）

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| POST | `/opencode/tasks` | 创建新的OpenCode任务 | API密钥 |
| GET | `/opencode/tasks` | 列出所有OpenCode任务 | API密钥 |
| GET | `/opencode/tasks/{task_id}` | 获取任务详情 | API密钥 |
| GET | `/opencode/tasks/{task_id}/stream` | SSE流（实时进度） | API密钥 |
| POST | `/opencode/tasks/{task_id}/abort` | 中止运行中的任务 | API密钥 |
| DELETE | `/opencode/tasks/{task_id}` | 删除任务 | API密钥 |

### 飞书集成

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| POST | `/feishu/webhook` | 遗留Webhook（DeepSeek LLM回退） | 飞书验证 |
| POST | `/feishu/webhook/opencode` | OpenCode集成Webhook | 飞书验证 |
| GET | `/feishu/websocket` | WebSocket长连接端点 | 飞书验证 |
| POST | `/feishu/send/card` | 发送飞书卡片消息 | API密钥 |
| POST | `/feishu/send/text` | 发送飞书文本消息 | API密钥 |

### 会话管理

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| GET | `/sessions` | 获取所有会话 | API密钥 |
| GET | `/sessions/{session_id}` | 获取会话详情 | API密钥 |
| DELETE | `/sessions/{session_id}` | 删除会话 | API密钥 |
| POST | `/sessions/{session_id}/clear` | 清空会话内容 | API密钥 |

### 技能管理

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| GET | `/skills` | 列出所有可用技能 | API密钥 |
| POST | `/skills/execute` | 执行指定技能 | API密钥 |
| POST | `/skills/register` | 注册新技能 | API密钥 |
| DELETE | `/skills/{skill_name}` | 删除技能 | API密钥 |

## 🛠️ 开发指南

### 添加新智能体

1. 在`src/agents/`中创建继承自`BaseAgent`的智能体类
2. 实现必需的方法：`start()`、`stop()`、能力处理器
3. 在`__init__`中注册到消息总线
4. 添加到`src/system.py`的智能体创建中
5. 更新文档

### 消息处理示例

```python
async def handle_message_type(self, message: Message):
    # 处理消息
    result = await self.process_payload(message.payload)
    
    # 发送响应
    await self.send_message(
        MessageType.RESPONSE_TYPE,
        recipient=message.sender,
        payload={"result": result}
    )
```

## 🧪 测试

### 运行测试套件

```bash
# 运行所有测试
pytest

# 运行特定测试类别
pytest tests/test_api.py              # API端点测试
pytest tests/test_multi_agent_start.py # 多智能体系统测试
pytest tests/test_websocket.py        # WebSocket测试
pytest tests/test_encrypted_webhook.py # 加密Webhook测试

# 带详细输出
pytest -v
pytest -xvs                           # 详细输出，失败时停止

# 测试覆盖率
pytest --cov=src --cov-report=html
```

### 测试分类

- **单元测试**: 测试单个模块功能
- **集成测试**: 测试模块间集成
- **API测试**: 测试REST API端点
- **飞书集成测试**: 测试飞书Webhook和卡片
- **OpenCode集成测试**: 测试OpenCode任务管理
- **安全测试**: 测试加密和认证功能

### 测试数据

测试数据位于`tests/fixtures/`目录，包含：
- 飞书Webhook模拟数据
- 加密测试数据
- OpenCode任务模拟数据
- 卡片模板测试数据

## 📚 相关文档

### 核心文档
- [docs/AGENTS.md](docs/AGENTS.md) - 详细的智能体架构文档
- [docs/FEISHU_SETUP.md](docs/FEISHU_SETUP.md) - 飞书设置和配置指南
- [docs/SECURITY.md](docs/SECURITY.md) - 安全配置和加密指南

### 部署文档
- [docs/TUNNEL_SETUP.md](docs/TUNNEL_SETUP.md) - 隧道设置指南（ngrok/localtunnel）
- [docs/AUTOSTART_README.md](docs/AUTOSTART_README.md) - 自动启动和隧道系统
- [Dockerfile](Dockerfile) - Docker容器配置
- [docker-compose.yml](docker-compose.yml) - Docker Compose配置

### 功能文档
- [docs/COMMANDS_README.md](docs/COMMANDS_README.md) - 自定义指令系统
- [docs/COMPLETION_SUMMARY.md](docs/COMPLETION_SUMMARY.md) - 功能完成总结
- [docs/NEW_FEATURES.md](docs/NEW_FEATURES.md) - 新功能介绍
- [docs/SESSION_MANAGEMENT_SUMMARY.md](docs/SESSION_MANAGEMENT_SUMMARY.md) - 会话管理总结

### 开发文档
- [docs/FEISHU_PRIVATE_CHAT_SETUP.md](docs/FEISHU_PRIVATE_CHAT_SETUP.md) - 飞书私聊设置
- [docs/FIXED_URL_SOLUTIONS.md](docs/FIXED_URL_SOLUTIONS.md) - 固定URL解决方案
- [docs/TEST_WEBSOCKET_GUIDE.md](docs/TEST_WEBSOCKET_GUIDE.md) - WebSocket测试指南
- [docs/opencode_file_send_example.md](docs/opencode_file_send_example.md) - OpenCode文件发送示例

### 配置示例
- [.env.example](.env.example) - 环境变量配置示例
- [config/settings.json](config/settings.json) - 应用设置配置
- [config/commands.json](config/commands.json) - 命令配置

## 🏷️ 版本管理

### 当前版本: v1.0.1

**版本历史**:
- **v1.0.1**: 加密功能增强，支持Feishu事件订阅加密/解密
- **v1.0.0**: 基础稳定版本，包含6个自定义命令和完整的多智能体系统

## 📁 项目结构

```
opencode-feishu-bridge/
├── src/                           # 源代码目录
│   ├── agents/                    # 多智能体系统（6个智能体）
│   │   ├── base.py               # 智能体基类
│   │   ├── coordinator.py        # 协调器智能体
│   │   ├── opencode_agent.py     # OpenCode智能体
│   │   ├── feishu_agent.py       # 飞书智能体
│   │   ├── llm_agent.py          # LLM智能体
│   │   ├── memory_agent.py       # 内存智能体
│   │   └── skill_agent.py        # 技能智能体
│   ├── legacy/                    # 向后兼容模块
│   │   ├── feishu_client.py      # 飞书客户端
│   │   ├── opencode_integration.py # OpenCode集成
│   │   ├── llm.py                # LLM接口
│   │   ├── task_store.py         # 任务存储
│   │   ├── secure_config.py      # 安全配置
│   │   └── ...（共20个文件）
│   ├── message_bus/              # 消息总线系统
│   │   ├── bus.py               # 消息总线实现
│   │   └── __init__.py
│   ├── config/                   # 运行时配置
│   ├── main.py                   # FastAPI主应用（563行）
│   ├── system.py                 # 系统初始化
│   ├── feishu_websocket.py       # WebSocket支持
│   └── __init__.py
├── tests/                        # 测试文件（20+个测试）
│   ├── test_api.py              # API测试
│   ├── test_multi_agent_start.py # 多智能体测试
│   ├── test_websocket.py        # WebSocket测试
│   ├── test_encrypted_webhook.py # 加密Webhook测试
│   └── ...（共24个测试文件）
├── config/                       # 应用配置
│   ├── settings.json            # 系统设置
│   └── commands.json            # 命令配置
├── docs/                         # 文档（14个文档文件）
├── examples/                     # 示例代码
├── scripts/                      # 工具脚本
│   ├── check_feishu_config.py   # 配置检查脚本
│   └── tunnel_monitor.py        # 隧道监控脚本
├── deploy/                       # 部署配置
├── logs/                         # 日志目录
├── data/                         # 数据存储
│   ├── tasks/                   # 任务数据
│   └── sessions/                # 会话数据
├── skills/                       # 技能定义
├── infra/                        # 基础设施配置
├── tmp/                          # 临时文件目录
├── .env.example                  # 环境变量示例
├── requirements.txt              # Python依赖（生产）
├── requirements-dev.txt          # Python依赖（开发）
├── requirements.lock.txt         # 依赖锁文件
├── Dockerfile                    # Docker配置
├── docker-compose.yml            # Docker Compose配置
├── manage.sh                     # 管理脚本（8241字节）
├── start_all.sh                  # 启动脚本
└── README.md                     # 项目说明
```

## 📄 许可证

MIT