# Feishu 设置指南

## 模式选择

VibeBridge 支持两种与飞书通信的方式：

| 特性 | WebSocket (推荐) | Webhook |
|------|------------------|---------|
| 公网 URL 需要 | ❌ 不需要 | ✅ 需要 |
| 设置复杂度 | 低 | 中等（需要隧道/代理） |
| 实时卡片 | ✅ 完整支持 | ✅ 完整支持 |
| 适用场景 | 本地开发、个人使用 | 生产服务器 |

当前默认模式：**WebSocket**

---

## WebSocket 模式设置（推荐）

### 1. 登录飞书开发者平台

- 访问 [https://open.feishu.cn/app](https://open.feishu.cn/app)
- 选择你的应用

### 2. 配置事件订阅

1. 在左侧菜单点击 **"事件订阅"**
2. 启用 **"使用长连接接收消息"** (Use long connection to receive messages)
3. **不需要配置 Request URL** — WebSocket 会处理一切

### 3. 订阅事件

在 **"订阅事件"** 中添加：

- `im.message.receive_v1` — 接收消息
- `im.message.message_read_v1` (可选) — 消息已读

### 4. 开启权限

进入 **"权限管理"** 页面，开启以下权限：

- `im:message` — 发送和接收消息
- `im:message:send_as_bot` — 以机器人身份发送消息
- `im:chat:readonly` — 读取群信息（可选）

### 5. 发布应用

- 进入 **"版本管理与发布"**
- 点击 **"创建版本"**
- 填写版本信息后发布

### 6. 启动 VibeBridge

```bash
# systemd user service 方式（推荐）
systemctl --user start vibebridge
systemctl --user enable vibebridge

# 查看 WebSocket 连接状态
journalctl --user -u vibebridge -f | grep "WebSocket\|connected"
```

### 7. 验证连接

```bash
curl http://localhost:9000/health
# 预期输出: {"ok":true,"providers":{"opencode":true,...}}
```

在飞书中 @机器人发送 `hello`，应收到回复。

---

## Webhook 模式设置

如需要使用 Webhook 模式（例如部署在有公网 IP 的服务器上）：

### 1. 配置 Request URL

1. 在飞书开发者平台 **"事件订阅"** 中关闭 **"使用长连接接收消息"**
2. 在 **"Request URL"** 中填入你的公网地址：
   ```
   https://your-domain.com/feishu/webhook
   ```
3. 配置 **Verification Token** 和 **Encrypt Key**（与 `.env` 中的值一致）

### 2. 订阅事件和权限

与 WebSocket 模式相同，订阅 `im.message.receive_v1` 并开启 `im:message` 权限。

### 3. 切换 VibeBridge 模式

```bash
# 编辑设置
nano config/settings.json
```

修改为：
```json
{
  "feishu_mode": "webhook",
  "websocket_enabled": false
}
```

重启服务：
```bash
systemctl --user restart vibebridge
```

---

## 隧道工具（Webhook 模式需要）

如果你在本地开发且没有公网 IP，可以使用隧道工具：

### ngrok

```bash
# 安装 ngrok
# 配置 authtoken
ngrok config add-authtoken YOUR_TOKEN

# 启动隧道
ngrok http 9000
```

### Cloudflare Tunnel

```bash
# 安装 cloudflared
cloudflared tunnel --url http://localhost:9000
```

### Serveo.net

```bash
ssh -o StrictHostKeyChecking=no -R 80:localhost:9000 serveo.net
```

---

## 测试

### 手动测试（URL 验证）

```bash
curl -X POST https://your-domain.com/feishu/webhook \
  -H "Content-Type: application/json" \
  -d '{"token": "your_verification_token", "challenge": "test_challenge", "type": "url_verification"}'
```

预期响应：
```json
{"challenge":"test_challenge"}
```

### 消息测试

在飞书中 @机器人发送任意消息，观察日志：

```bash
journalctl --user -u vibebridge -f
```

---

## 故障排除

### 1. WebSocket 无法连接
- 检查 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 是否正确
- 检查应用是否已发布
- 查看日志中的连接错误信息

### 2. 飞书验证失败
- 确保 Verification Token 完全匹配（区分大小写）
- webhook URL 必须能从公网访问
- 检查服务器日志中的解密错误

### 3. 响应时间超过 3 秒
- 免费隧道服务可能有延迟波动
- 考虑使用 ngrok 或 Cloudflare Tunnel
- 优化代码（已内置后台任务处理）

### 4. 加密错误
- 确保 `FEISHU_ENCRYPT_KEY` 在 `.env` 中恰好 43 个字符（base64）
- 飞书控制台中的加密密钥必须与服务端一致

### 5. "Challenge code 没有返回"
- 加密密钥不匹配
- 飞书控制台加密未启用/禁用，但服务端期望相反
- 解密失败

**解决步骤**：
1. 检查飞书平台配置，确保加密状态与服务端一致
2. 确认 `.env` 中的 `FEISHU_ENCRYPT_KEY` 正确
3. 查看服务端日志确认解密是否成功
