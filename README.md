# AI Product Lab Multi-Agent System

一个基于FastAPI的AI编程代理服务，采用模块化多智能体架构，集成飞书和OpenCode CLI。

## 🏗️ 系统架构

```
飞书 → FastAPI (Webhook) → 多智能体系统 → 智能体协调 → 结果 → 飞书
```

### 智能体组件

| 智能体 | 用途 | 能力 |
|-------|------|------|
| **协调器** | 协调智能体通信 | 消息路由、任务委派 |
| **OpenCode代理** | 执行OpenCode CLI任务 | 任务创建、进度跟踪、技能执行 |
| **飞书代理** | 处理飞书API通信 | 发送卡片、发送文本、文件上传 |
| **LLM代理** | 处理自然语言请求 | DeepSeek API集成、提示工程 |
| **内存代理** | 维护对话上下文 | 会话存储、知识保留 |
| **技能代理** | 管理可执行技能 | 技能加载、执行、文件发送 |

## ✨ 核心功能

- **🤖 多智能体系统**: 6个专门智能体协调工作
- **📱 飞书集成**: 接收Webhook消息并通过飞书代理返回结果
- **🔐 加密通信**: 支持飞书事件订阅加密/解密，确保安全通信
- **🔧 OpenCode CLI集成**: 执行AI驱动的代码开发任务
- **🧠 向后兼容**: 保留`src/legacy/`中的原始模块
- **📋 任务管理**: 创建、跟踪和监控OpenCode任务
- **🔄 实时进度**: 通过Server-Sent Events (SSE)流获取实时更新
- **🎨 交互式卡片**: 使用飞书交互式卡片展示任务进度和结果
- **🌐 自动隧道**: 支持ngrok和localtunnel，自动监控和URL变更通知

## 📊 当前部署状态 (v1.0.1)

✅ **系统状态**: 完全运行中
- **服务器**: http://127.0.0.1:8000
- **公网隧道**: `https://unmobilized-virgen-mitotically.ngrok-free.dev`
- **Webhook端点**: `https://unmobilized-virgen-mitotically.ngrok-free.dev/feishu/webhook/opencode`
- **加密状态**: ✅ 已启用 (AES-192)
- **多智能体系统**: ✅ 6个智能体运行中
- **隧道监控**: ✅ 运行中，自动通知URL变更

📋 **自定义命令支持**:
- `清空session` - 清空当前会话
- `kimi` - 切换到Kimi模型
- `deepseek` - 切换到Deepseek模型
- `模型` - 显示可用模型
- `启动服务器` - 启动本地服务器
- `git 提交` - 执行Git提交

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
python check_feishu_config.py
```

该脚本将显示当前隧道URL、加密状态，并生成详细的Feishu控制台配置步骤。

### 启动服务

```bash
# 使用管理脚本
./manage.sh start

# 或直接运行
python src/main.py
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

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/` | 系统状态和版本 |
| GET | `/health` | 健康检查（含多智能体状态） |
| GET | `/system/status` | 详细的智能体状态和能力 |

### OpenCode任务管理（向后兼容）

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/opencode/tasks` | 创建新的OpenCode任务 |
| GET | `/opencode/tasks` | 列出所有OpenCode任务 |
| GET | `/opencode/tasks/{task_id}` | 获取任务详情 |
| GET | `/opencode/tasks/{task_id}/stream` | SSE流（实时进度） |
| POST | `/opencode/tasks/{task_id}/abort` | 中止运行中的任务 |

### 飞书集成

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/feishu/webhook` | 遗留Webhook（DeepSeek LLM回退） |
| POST | `/feishu/webhook/opencode` | OpenCode集成Webhook |

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

```bash
# 运行多智能体系统测试
python tests/test_multi_agent_start.py

# 运行API测试
pytest tests/test_api.py

# 运行特定测试
pytest tests/test_api.py::test_root -xvs
```

## 📚 相关文档

- [docs/AGENTS.md](docs/AGENTS.md) - 详细的智能体架构文档
- [docs/FEISHU_SETUP.md](docs/FEISHU_SETUP.md) - 飞书设置指南
- [docs/TUNNEL_SETUP.md](docs/TUNNEL_SETUP.md) - 隧道设置指南
- [docs/SECURITY.md](docs/SECURITY.md) - 安全配置指南
- [docs/AUTOSTART_README.md](docs/AUTOSTART_README.md) - 自动启动和隧道系统
- [docs/COMMANDS_README.md](docs/COMMANDS_README.md) - 自定义指令系统

## 🏷️ 版本管理

### 当前版本: v1.0.1

**版本历史**:
- **v1.0.1** (当前): 加密功能增强，支持Feishu事件订阅加密/解密
- **v1.0.0**: 基础稳定版本，包含6个自定义命令和完整的多智能体系统

**Git操作**:
```bash
# 查看当前版本
git tag

# 创建新标签
git tag v1.x.x

# 推送标签到远程
git push origin --tags

# 基于标签创建发布
git checkout v1.0.1
```

## 📄 许可证

MIT