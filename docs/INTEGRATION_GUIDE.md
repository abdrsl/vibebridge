# OpenClaw/OpenCode 统一审批系统集成方案

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        飞书平台                               │
│  ┌──────────────┐              ┌──────────────┐            │
│  │  机器人A      │              │  机器人B      │            │
│  │  (Webhook)   │              │  (WebSocket) │            │
│  │              │              │              │            │
│  │ 发送审批消息  │              │ 实时交互      │            │
│  └──────┬───────┘              └──────┬───────┘            │
└─────────┼─────────────────────────────┼───────────────────┘
          │                             │
          │ Webhook回调                  │ WebSocket
          │                             │
          ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│              opencode-feishu-bridge 服务器                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              approval_manager.py                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │  │
│  │  │ Web Server  │  │ WebSocket   │  │ 审批管理器    │ │  │
│  │  │ (HTTP API)  │  │ Server      │  │              │ │  │
│  │  │             │  │             │  │ - 创建审批   │ │  │
│  │  │ /api/       │  │ /ws/        │  │ - 状态管理   │ │  │
│  │  │ /webhook/   │  │ approval    │  │ - 超时处理   │ │  │
│  │  └─────────────┘  └──────┬──────┘  └──────────────┘ │  │
│  └──────────────────────────┼──────────────────────────┘  │
└─────────────────────────────┼─────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              │ WebSocket                     │ Webhook
              │                               │
              ▼                               ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│      OpenClaw           │      │      OpenCode           │
│  ┌───────────────────┐  │      │  ┌───────────────────┐  │
│  │ approval-bridge-  │  │      │  │ 直接调用 HTTP API │  │
│  │ client.sh         │  │      │  │                   │  │
│  │                   │  │      │  │ POST /api/        │  │
│  │ - WebSocket 连接   │  │      │  │ approval/create   │  │
│  │ - 实时接收结果     │  │      │  │                   │  │
│  └───────────────────┘  │      │  └───────────────────┘  │
└─────────────────────────┘      └─────────────────────────┘
```

---

## 📦 文件清单

### opencode-feishu-bridge 项目新增
```
opencode-feishu-bridge/
├── approval_manager.py          ✅ 审批管理核心模块
├── main.py                      (需要集成 approval_manager)
└── config.yaml                  (需要添加审批配置)
```

### MyCompany 项目新增/更新
```
MyCompany/.scripts/
├── approval-bridge-client.sh    ✅ OpenClaw WebSocket 客户端
└── approval-opencode-bridge.sh  (可选，HTTP fallback)

MyCompany/.config/
└── bridge-integration.conf      ✅ 桥接配置
```

---

## 🔧 配置步骤

### 1. 在 opencode-feishu-bridge 中集成

**修改 main.py，添加审批管理器：**

```python
from approval_manager import ApprovalManager, ApprovalWebHandler, ApprovalWebSocketHandler

# 初始化
approval_manager = ApprovalManager(
    feishu_webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",  # 机器人A
    feishu_secret="your-secret"
)

# 添加路由
app.router.add_post("/api/approval/create", web_handler.handle_create_approval)
app.router.add_get("/api/approval/{approval_id}", web_handler.handle_get_approval)
app.router.add_get("/api/approval/pending", web_handler.handle_list_pending)
app.router.add_post("/webhook/feishu", web_handler.handle_feishu_webhook)
app.router.add_get("/ws/approval", ws_handler.handle)
```

### 2. 配置飞书机器人

**机器人A (Webhook - 发送审批消息)：**
- 类型：自定义机器人
- 功能：接收审批请求，发送卡片消息
- Webhook URL：配置到 approval_manager

**机器人B (WebSocket - OpenClaw 交互)：**
- 类型：企业自建应用
- 功能：与 OpenClaw WebSocket 连接
- 事件订阅：配置回调 URL

### 3. 配置 OpenClaw

**创建配置文件：**

```bash
# MyCompany/.config/bridge-integration.conf
BRIDGE_WS_URL=ws://localhost:8000/ws/approval
BRIDGE_HTTP_URL=http://localhost:8000
FEISHU_USER_ID=ou_REDACTED_OPEN_ID
```

**初始化：**

```bash
cd /home/user/workspace/MyCompany
./.scripts/approval-bridge-client.sh init
```

---

## 🚀 使用流程

### OpenClaw 场景（WebSocket）

```bash
# 1. OpenClaw 检测到高风险操作
# 2. 通过 WebSocket 发送审批请求
./.scripts/approval-bridge-client.sh create \
    "ou_REDACTED_OPEN_ID" \
    "git push origin main" \
    "提交代码到主分支" \
    "high"

# 3. 桥接服务器通过 Webhook 发送消息到飞书（机器人A）
# 4. 用户在飞书中点击批准/拒绝
# 5. 飞书回调到桥接服务器
# 6. 桥接服务器通过 WebSocket 通知 OpenClaw
# 7. OpenClaw 收到结果，继续或终止操作
```

### OpenCode 场景（HTTP API）

```python
import requests

# 1. OpenCode 调用 HTTP API 创建审批
response = requests.post("http://localhost:8000/api/approval/create", json={
    "user_id": "ou_REDACTED_OPEN_ID",
    "command": "deploy production",
    "description": "部署到生产环境",
    "risk_level": "high",
    "source": "opencode",
    "callback_url": "http://opencode:8080/approval/callback"
})

approval_id = response.json()["approval_id"]

# 2. 等待回调或轮询状态
# 3. 飞书审批完成后，桥接服务器回调 OpenCode
```

---

## 📡 API 端点

### WebSocket 端点
```
ws://localhost:8000/ws/approval

消息格式:
- 创建审批: {"type": "create_approval", "user_id": "...", "command": "...", ...}
- 查询状态: {"type": "get_approval", "approval_id": "..."}
- 心跳: {"type": "ping"}
```

### HTTP API
```
POST /api/approval/create      # 创建审批请求
GET  /api/approval/{id}        # 查询审批状态
GET  /api/approval/pending     # 列出待审批
POST /webhook/feishu           # 飞书回调
```

---

## ✅ 检查清单

### 部署前
- [ ] 飞书机器人A已创建（Webhook）
- [ ] 飞书机器人B已创建（WebSocket/事件订阅）
- [ ] 获取机器人A的 Webhook URL 和 Secret
- [ ] 配置机器人B的事件订阅 URL

### 部署中
- [ ] 将 approval_manager.py 添加到 opencode-feishu-bridge
- [ ] 修改 main.py 集成审批路由
- [ ] 配置桥接服务器的环境变量
- [ ] 部署并启动桥接服务器

### 部署后
- [ ] 测试 WebSocket 连接
- [ ] 测试创建审批请求
- [ ] 测试飞书消息发送
- [ ] 测试飞书按钮回调
- [ ] 测试审批结果通知

---

## 🔍 故障排查

### WebSocket 连接失败
```bash
# 检查桥接服务器是否运行
curl http://localhost:8000/api/approval/pending

# 检查 WebSocket 端点
websocat ws://localhost:8000/ws/approval
```

### 飞书消息发送失败
```bash
# 检查 Webhook URL 和 Secret
# 查看桥接服务器日志
```

### 回调不生效
```bash
# 检查飞书事件订阅配置
# 确保桥接服务器可从公网访问（或使用内网穿透）
```

---

## 📝 下一步

1. **您需要我帮您：**
   - 修改 opencode-feishu-bridge 的 main.py 集成审批管理器？
   - 创建完整的部署脚本？
   - 配置飞书机器人的详细步骤？

2. **请确认：**
   - 桥接服务器运行的端口（默认8000）？
   - 飞书机器人A的 Webhook URL？
   - 是否需要内网穿透（如 ngrok）？

这样我们就可以完成完整的集成了！