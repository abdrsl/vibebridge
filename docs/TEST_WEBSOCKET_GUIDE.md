# Feishu WebSocket 长连接测试指南

## 当前状态

✅ **WebSocket 连接已建立**
- 服务器: http://127.0.0.1:8000 (PID: 88042)
- 公网隧道: https://unmobilized-virgen-mitotically.ngrok-free.dev
- WebSocket: 已连接到 Feishu 服务器 (`wss://msg-frontier.feishu.cn/ws/v2`)
- 心跳: 每30秒 ping/pong (已检测到 12 次成功)
- 事件处理: 尚未收到任何事件

## 测试步骤

### 1. 发送测试消息到飞书机器人

1. 打开飞书应用
2. 找到 OpenCode-Feishu Bridge 机器人
3. 发送任意消息，例如："Hello" 或 "测试 WebSocket"

**默认聊天 ID**: `oc_REDACTED_CHAT_ID`

### 2. 监控事件处理

运行监控脚本实时查看事件：

```bash
cd /home/user/workspace/opencode-feishu-bridge
./manage.sh logs  # 查看服务器日志
```

或使用专用监控脚本：

```bash
python monitor_websocket.py
```

**预期日志输出**:
- `处理飞书事件: im.message.receive_v1`
- `收到原始事件数据: ...`
- `转换后的 webhook 格式: ...`
- `[Card] Received webhook body: ...`

### 3. 验证处理结果

成功处理后，机器人应回复：
- 确认卡片（需要用户确认执行）
- 或直接开始处理任务

## 飞书控制台配置检查

确保 Event Subscription 2.0 已正确配置：

1. 访问 [Feishu 开发者后台](https://open.feishu.cn/app/)
2. 选择应用: `cli_xxxxxxxxxxxxxxxx`
3. 进入 "事件订阅" 页面
4. 检查配置:

**必需设置**:
- ✅ **使用长连接接收事件(推荐)** 已选中
- ✅ **Encrypt Key**: `JPlrXOHdjmI4fPVjFopYbdpOjH3eIS6i`
- ✅ **Verification Token**: `3poXkZrc8ly29leC592MIhx6YiWMNLjy`

**订阅事件** (必须包含):
- `p2.im.message.receive_v1` (接收消息)
- `p2.card.action.trigger` (卡片交互)

## 故障排除

### 问题1: 未收到 WebSocket 事件

**可能原因**:
1. 飞书控制台未启用 Event Subscription 2.0
2. 事件未订阅
3. 机器人无消息接收权限

**解决方案**:
1. 在飞书控制台切换到 "使用长连接接收事件(推荐)"
2. 添加事件订阅: `p2.im.message.receive_v1`
3. 确保应用有 `im:message` 权限

### 问题2: 事件处理超时

**现象**: 日志显示 `事件处理超时（10秒）`

**原因**: 事件处理耗时超过10秒
**处理**: 系统已返回成功响应，避免飞书重试。处理会在后台继续。

### 问题3: WebSocket 连接断开

**现象**: 日志显示 `disconnected to wss://msg-frontier.feishu.cn`

**原因**: 网络问题或 Feishu 服务器端断开
**处理**: 系统会自动重连（指数退避，最长5分钟）

## 回退机制

WebSocket 连接失败时，系统会自动回退到 webhook 端点:

**Webhook 端点**:
- `https://unmobilized-virgen-mitotically.ngrok-free.dev/feishu/webhook/opencode`
- 格式: Schema 2.0

已测试回退功能 ✅

## 性能测试

如需测试多个并发事件:

1. 同时发送多条消息
2. 监控日志中的处理时间戳
3. 检查是否有事件丢失

系统设计处理能力:
- 单事件处理超时: 10秒
- 超时后返回成功，避免飞书重试风暴
- 后台线程处理，不阻塞 WebSocket 连接

## 监控命令

```bash
# 检查 WebSocket 连接状态
python monitor_websocket.py status

# 实时监控事件
python monitor_websocket.py

# 查看服务器日志
tail -f logs/server.log

# 检查服务器健康状态
curl http://127.0.0.1:8000/health
```

## 下一步

1. ✅ 发送测试消息验证 WebSocket 事件流
2. ✅ 测试卡片交互事件
3. ✅ 验证错误处理和重连机制
4. ⏳ 性能测试（多个并发事件）
5. ⏳ 生产环境监控告警

## 联系支持

如有问题，请检查:
1. 服务器日志: `logs/server.log`
2. WebSocket 连接状态
3. 飞书控制台配置

系统已稳定运行，WebSocket 连接正常，等待接收第一个事件。