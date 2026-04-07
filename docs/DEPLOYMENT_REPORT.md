# OpenClaw/OpenCode 审批系统部署报告

**部署时间**: 2026-04-02 02:40:44  
**状态**: ✅ 完成

---

## 📁 部署的文件

### 桥接项目 (/home/user/workspace/opencode-feishu-bridge)

| 文件 | 状态 |
|------|------|
| approval_manager.py | ✅ |
| approval_integration.py | ✅ |
| approval_plugin.py | ✅ |
| integrate-approval.sh | ✅ |
| INTEGRATION_GUIDE.md | ✅ |

### MyCompany 项目 (/home/user/workspace/MyCompany)

| 文件 | 状态 |
|------|------|
| .scripts/approval-bridge-client.sh | ✅ |
| .scripts/approval-opencode-bridge.sh | ✅ |
| .config/bridge-integration.conf | ✅ |

---

## 🚀 启动步骤

### 1. 配置环境变量

编辑 `/home/user/workspace/MyCompany/.secrets/feishu.env`，添加：

```bash
# 飞书机器人A (发送审批消息)
FEISHU_BOT_A_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
FEISHU_BOT_A_SECRET=your-secret
```

### 2. 启动桥接服务器

```bash
cd /home/user/workspace/opencode-feishu-bridge
source /home/user/workspace/MyCompany/load-env.sh
python -m src.main
```

### 3. 测试审批系统

```bash
cd /home/user/workspace/MyCompany
./.scripts/approval-bridge-client.sh check-bridge
```

---

## 📡 API 端点

启动后，以下端点可用：

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/approval/create | POST | 创建审批请求 |
| /api/approval/{id} | GET | 查询审批状态 |
| /api/approval/pending | GET | 待审批列表 |
| /webhook/approval | POST | 飞书回调 |
| /ws/approval | WS | WebSocket连接 |

---

## 🧪 测试命令

```bash
# 测试 HTTP API
curl -X POST http://localhost:8000/api/approval/create \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "ou_REDACTED_OPEN_ID",
    "command": "git push origin main",
    "description": "测试审批",
    "risk_level": "high"
  }'

# 查询状态
curl http://localhost:8000/api/approval/xxx

# WebSocket 测试
websocat ws://localhost:8000/ws/approval
```

---

## 📝 后续配置

1. **配置飞书机器人A**
   - 获取 Webhook URL
   - 更新到 .secrets/feishu.env

2. **配置飞书回调**
   - 设置事件订阅 URL
   - 指向 http://your-server:8000/webhook/approval

3. **测试完整流程**
   - 创建审批请求
   - 在飞书中审批
   - 验证结果回调

---

## 📞 支持

- 详细文档: `/home/user/workspace/opencode-feishu-bridge/INTEGRATION_GUIDE.md`
- 部署总结: `/home/user/workspace/DEPLOYMENT_SUMMARY.md`

---

*部署完成时间: 2026-04-02 02:40:44*
