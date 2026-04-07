# 审核机器人C - 部署和使用指南

## 🎯 功能概述

审核机器人C是OpenCode-Feishu Bridge的审批系统，实现：
- **推送审核请求** → 发送飞书卡片消息
- **接收审批结果** ← 通过飞书按钮或文字回复
- **状态管理** → 跟踪所有审批请求

## 📁 文件结构

```
src/approval/
├── __init__.py          # 模块导出
├── manager.py           # 审批管理核心
├── feishu_handler.py    # 飞书交互处理
└── routes.py           # API路由
```

## 🚀 部署步骤

### 1. 配置环境变量

在 `.env` 文件中添加：

```bash
# 飞书审批机器人配置
FEISHU_APPROVAL_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
```

### 2. 启动服务

```bash
cd /home/user/workspace/opencode-feishu-bridge
source .venv/bin/activate
python -m src.main
```

### 3. 测试API

```bash
# 创建审批请求
curl -X POST http://localhost:8000/api/approval/create \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "ou_REDACTED_OPEN_ID",
    "command": "git push origin main",
    "description": "提交代码到主分支",
    "risk_level": "high"
  }'

# 查询审批状态
curl http://localhost:8000/api/approval/APR-xxxxxx

# 列出待审批
curl http://localhost:8000/api/approval/pending/list
```

## 💬 飞书交互方式

### 方式1：卡片按钮（推荐）

机器人C发送的卡片包含两个按钮：
- ✅ **批准** - 点击即可批准
- ❌ **拒绝** - 点击即可拒绝

### 方式2：文字回复

在飞书中直接回复：
```
批准 APR-123456
拒绝 APR-123456 理由：需要测试
```

## 🔌 API端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/approval/create` | POST | 创建审批请求 |
| `/api/approval/{id}` | GET | 查询审批状态 |
| `/api/approval/pending/list` | GET | 列出待审批 |
| `/api/approval/approve` | POST | API方式批准 |
| `/api/approval/reject` | POST | API方式拒绝 |
| `/webhook/feishu/approval` | POST | 飞书回调 |

## 🧪 测试

运行测试脚本：

```bash
python test_approval_system.py
```

## 🔧 故障排查

### 飞书消息发送失败
- 检查 `FEISHU_APPROVAL_WEBHOOK_URL` 是否正确
- 确认Webhook机器人有发送权限

### 回调不生效
- 检查飞书事件订阅配置
- 确认 `/webhook/feishu/approval` 可访问

### API返回404
- 确认服务已启动
- 检查路由是否正确注册

## 📋 下一步

1. ✅ 完成基础审批系统
2. 🔄 集成飞书Bot API（替代Webhook）
3. 🔄 添加审批超时处理
4. 🔄 添加审批历史记录
5. 🔄 集成OpenClaw WebSocket

## 📝 使用示例

### OpenClaw 场景

```python
# OpenClaw 检测到高风险操作
# 调用审批系统
response = requests.post("http://localhost:8000/api/approval/create", json={
    "user_id": "ou_REDACTED_OPEN_ID",
    "command": "rm -rf /important/data",
    "description": "删除重要数据",
    "risk_level": "critical"
})

approval_id = response.json()["approval_id"]

# 等待审批结果...
# 用户在飞书中点击"批准"或"拒绝"

# 查询结果
result = requests.get(f"http://localhost:8000/api/approval/{approval_id}")
if result.json()["approval"]["status"] == "approved":
    # 继续执行
    pass
```

### OpenCode 场景

```python
# OpenCode 部署前审批
approval = create_approval(
    user_id="ou_xxx",
    command="deploy production",
    description="部署到生产环境",
    risk_level="high",
    callback_url="http://opencode:8080/callback"
)

# 等待飞书审批...
# 审批完成后自动回调OpenCode
```
