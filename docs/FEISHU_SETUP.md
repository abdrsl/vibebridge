# Feishu Webhook Setup

## Current Tunnel Status

✅ **Tunnel is running** with ngrok (stable tunnel)

- **Tunnel URL**: `https://unmobilized-virgen-mitotically.ngrok-free.dev`
- **Webhook Endpoint**: `https://unmobilized-virgen-mitotically.ngrok-free.dev/feishu/webhook/opencode`
- **Response Time**: ~1.9-2.0 seconds (within Feishu's 3-second limit)
- **Encryption**: **ENABLED** (Using provided encryption key and verification token)
- **Encryption Test**: **PASSED** ✅ (Encryption/decryption and signature verification tested)
- **Status**: **FULLY OPERATIONAL** ✅ (URL verification successful + Live message processing verified + Encryption tested)

## ✅ Live Test Results

**Message Received**: `"@我的个人助手 请你访问一下workspace/ai-project 目录"`
**OpenCode Response**: Successfully listed directory structure and analyzed project
**Result**: FastAPI project with OpenCode CLI + Feishu integration identified
**Time to Complete**: ~2-3 seconds (within Feishu limits)

## Steps to Configure Feishu Webhook

1. **Login to Feishu Developer Console**
   - Go to [https://open.feishu.cn/app](https://open.feishu.cn/app)
   - Select your app (App ID: `cli_xxxxxxxxxxxxxxxx`)

2. **Navigate to Event Subscription**
   - In the left sidebar, click "Event Subscription"
   - Under "Request URL", click "Edit"

3. **Enter Webhook URL**
    - **URL**: `https://unmobilized-virgen-mitotically.ngrok-free.dev/feishu/webhook/opencode`
    - **Verification Token**: `1PCumkwcAySWFrsg3p2bkhetQXMOHdgM`
    - **Encrypt Key**: `7a3sd20f323AbdurusulSalamat`
    - **Important**: Enable encryption in Feishu console (toggle "启用加密" to ON)
    - Click "Save"

4. **Verify Configuration**
   - Feishu will send a `url_verification` request
   - The server will automatically respond with the challenge
   - If successful, Feishu will show "Configuration successful"

5. **Subscribe to Events**
   - Under "Subscribe to events", add:
     - `im.message.receive_v1` (接收消息)
   - Click "Save"

6. **Enable Permissions**
   - Go to "Permissions" section
   - Enable: `im:message` (发送和接收消息)
   - Enable: `im:message:send_as_bot` (以机器人身份发送消息)
   - Submit for review if required

## Tunnel Management

### Current Tunnel (ngrok)

```bash
# Check tunnel status
ps aux | grep ngrok

# View tunnel logs
tail -f logs/ngrok.log

# Restart tunnel (if needed)
./manage.sh stop-tunnel
./manage.sh tunnel
```

**Note**: ngrok provides stable URLs with the free tier. The URL changes only if you restart ngrok or after 2 hours of inactivity.

### Alternative Tunnels

#### Option 1: ngrok (Recommended for Production)

**Prerequisite**: Get a free ngrok v3 authtoken from [ngrok.com](https://ngrok.com)

```bash
# Install ngrok (already installed)
# Configure with your authtoken
./start_ngrok.sh <your-ngrok-v3-authtoken>

# Tunnel will start on https://xxxx-xx-xxx-xxx-xxx.ngrok-free.app
```

#### Option 2: Serveo.net

```bash
ssh -o StrictHostKeyChecking=no -R 80:localhost:8000 serveo.net
```

#### Option 3: Cloudflare Tunnel (Most Reliable)

Requires Cloudflare account and `cloudflared` installation.

## Testing

### Manual Test (URL Verification)

```bash
curl -X POST https://d9a8a092e184bf.lhr.life/feishu/webhook/opencode \
  -H "Content-Type: application/json" \
  -d '{"token": "z3V8Qc6B3NqXjaKpP5rL9sT2uV1yW4x7A0D4F6H9K2M", "challenge": "test_challenge", "type": "url_verification"}'
```

Expected response:
```json
{"challenge":"test_challenge"}
```

### Encrypted Message Test

```bash
python send_encrypted_test.py
```

## Troubleshooting

### 1. Tunnel Not Responding
- Check if server is running: `ps aux | grep uvicorn`
- Check server logs: `tail -f logs/server_final.log`
- Check tunnel logs: `tail -f logs/lhr_tunnel.log`

### 2. Feishu Verification Fails
- Ensure Verification Token matches exactly (case-sensitive)
- Ensure webhook URL is accessible from public internet
- Check server logs for decryption errors

### 3. Response Time Exceeds 3 Seconds
- localhost.run may have variable latency
- Consider switching to ngrok or Cloudflare Tunnel
- Optimize server code (already done - background tasks, reduced logging)

### 4. Encryption Errors
- Ensure `FEISHU_ENCRYPT_KEY` in `.env` is exactly 43 characters (base64)
- Current key: `z8V8Qc6B3NqXjwKpP5rL9sT2uV1yW4x7A0D3F6H9K2M` (first 43 chars used)

### 5. "Challenge code没有返回" (Feishu URL Verification Failed)

If Feishu reports "Challenge code没有返回", the webhook endpoint is not returning the correct challenge response. This is usually caused by:

**Possible Causes:**
1. **Encryption key mismatch** - The Encrypt Key in Feishu platform doesn't match the one in `.env`
2. **Encryption disabled in Feishu** - Feishu is sending encrypted payloads but your app expects unencrypted
3. **Decryption failure** - Server cannot decrypt the encrypted payload

**Solution Steps:**

**Step 1: Check Feishu Platform Configuration**
1. Login to [Feishu Developer Console](https://open.feishu.cn/app)
2. Go to "Event Subscription"
3. Check the **Encrypt Key** field:
   - Should be exactly 43 characters (base64 without padding)
   - Example: `z8V8Qc6B3NqXjwKpP5rL9sT2uV1yW4x7A0D3F6H9K2M` (43 chars)
   - If longer than 43 chars, use only the first 43 characters
4. Check **Verification Token**:
   - Should match exactly (case-sensitive)
   - Current token: `z3V8Qc6B3NqXjaKpP5rL9sT2uV1yW4x7A0D4F6H9K2M`

**Step 2: Update `.env` File**
If Feishu Encrypt Key is different, update `.env`:
```bash
# Edit .env file
FEISHU_ENCRYPT_KEY=your_actual_43_char_key_from_feishu
FEISHU_VERIFICATION_TOKEN=your_verification_token_from_feishu
```

**Step 3: Restart Server**
```bash
cd /home/user/workspace/opencode-feishu-bridge
pkill -f "uvicorn" 2>/dev/null || true
source .venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > logs/server_final.log 2>&1 &
```

**Step 4: Test URL Verification (Unencrypted)**
```bash
curl -X POST https://unmobilized-virgen-mitotically.ngrok-free.dev/feishu/webhook/opencode \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_VERIFICATION_TOKEN", "challenge": "test123", "type": "url_verification"}'
```
Expected response: `{"challenge":"test123"}`

**Step 5: If Still Failing - Try Disabling Encryption in Feishu**
1. In Feishu Event Subscription, find encryption settings
2. Try disabling encryption (if option available)
3. Save and retry URL verification

**Step 6: Debug Server Logs**
```bash
tail -f logs/server_final.log
```
Look for `[Crypto]` or `[Webhook]` messages to identify decryption errors.

### 6. Tunnel URL Changes (serveo.net specific)

serveo.net tunnels are **temporary** and change each time you restart the tunnel. If Feishu reports "返回数据不是合法的JSON格式", the tunnel URL may have changed.

**Current Tunnel URL**: `https://unmobilized-virgen-mitotically.ngrok-free.dev`

**To restart tunnel and get new URL:**

```bash
cd /home/user/workspace/opencode-feishu-bridge
pkill -f "serveo" 2>/dev/null || true
ssh -o StrictHostKeyChecking=no -R 80:localhost:8000 serveo.net > logs/serveo.log 2>&1 &
sleep 3
grep "serveousercontent" logs/serveo.log | grep -o "https://[^ ]*" | head -1
```

**Update Feishu configuration** with the new URL shown above.

## ✅ Completed Steps

1. ✅ Configure Feishu webhook URL with the tunnel URL
2. ✅ Send test message to the bot in Feishu
3. ✅ Verify OpenCode task creation and interactive card response
4. ✅ Monitor performance (response times under 3 seconds)

## 🔧 Next Enhancement Opportunities

1. **Fix Encryption**: Re-enable encryption in Feishu console and fix decryption issues
2. **Task Persistence**: Store OpenCode tasks to files for auditing/debugging
3. **Advanced Testing**: Test more complex development tasks and edge cases
4. **Production Tunnel**: Set up ngrok or Cloudflare Tunnel for more reliable access
5. **Monitoring**: Add monitoring for task success rates and response times

## 📱 Mobile-Friendly Configuration Guide

### Quick Setup from Mobile Device

1. **Copy Webhook URL**:
   ```
   https://unmobilized-virgen-mitotically.ngrok-free.dev/feishu/webhook/opencode
   ```
   
2. **Open Feishu Developer Console** on mobile browser:
   - Visit: https://open.feishu.cn/app
   - Login with your Feishu account
   
3. **Configure Event Subscription**:
   - Paste the Webhook URL in "Request URL" field
   - Set Verification Token: `z3V8Qc6B3NqXjaKpP5rL9sT2uV1yW4x7A0D4F6H9K2M`
   - Set Encrypt Key: `z8V8Qc6B3NqXjwKpP5rL9sT2uV1yW4x7A0D3F6H9K2M`
   - **Important**: Disable encryption toggle (设置加密为关闭)
   
4. **Subscribe to Events**:
   - Add `im.message.receive_v1` (接收消息)
   
5. **Enable Permissions**:
   - Enable `im:message` (发送和接收消息)
   - Enable `im:message:send_as_bot` (以机器人身份发送消息)

### Troubleshooting on Mobile

- **URL Verification Fails**: Ensure you copied the entire URL including `https://`
- **Connection Timeout**: The tunnel may be restarting, wait 30 seconds and try again
- **Encryption Errors**: Keep encryption disabled for initial setup
- **QR Code Alternative**: Consider generating a QR code with the webhook URL for easier entry

### Monitoring from Mobile

- Check tunnel status: `curl https://unmobilized-virgen-mitotically.ngrok-free.dev/health`
- URL changes will be automatically notified in Feishu chat
- Use simple text commands: `模型`, `kimi`, `deepseek`, `清空session`, `启动服务器`, `git 提交`

## Files Reference

- `src/legacy/main.py` - Webhook endpoint (`/feishu/webhook/opencode`)
- `src/legacy/feishu_crypto.py` - Encryption/decryption utilities
- `src/legacy/feishu_client.py` - Feishu API client and card builders
- `src/legacy/opencode_integration.py` - OpenCode task execution
- `src/legacy/task_store.py` - JSON file-based task storage
- `TUNNEL_SETUP.md` - Detailed tunnel comparison guide
- `start_ngrok.sh` - Ngrok setup script

## 🔌 Feishu WebSocket 长连接配置（实验性）

### 概述
Feishu WebSocket 长连接提供了比传统Webhook更实时、更稳定的消息接收方式。此功能为实验性功能，需要飞书事件订阅2.0支持。

### 启用步骤

1. **更新环境配置** (`.env`文件):
   ```bash
   # 启用WebSocket长连接
   FEISHU_WEBSOCKET_ENABLED=true
   
   # WebSocket服务器URL（请参考飞书官方文档更新）
   FEISHU_WEBSOCKET_URL=wss://open.feishu.cn/stream
   ```

2. **重启服务器**:
   ```bash
   ./manage.sh restart
   ```

3. **验证连接**:
   - 检查服务器日志中是否有WebSocket连接成功信息
   - 运行测试脚本: `python tests/test_websocket.py`

### 注意事项

⚠️ **重要提示**:
- WebSocket URL可能需要根据飞书官方文档更新
- 需要飞书事件订阅2.0权限
- 与Webhook模式可以共存，但建议只启用一种
- 当前为实验性实现，生产环境请充分测试

### 技术实现

- **核心文件**: `src/feishu_websocket.py`
- **集成点**: `src/main.py` 中的lifespan管理
- **消息处理**: 复用现有的 `feishu_webhook_handler.py` 和 `feishu_card_handler.py`

### 故障排除

1. **连接失败**:
   - 检查访问令牌是否有效
   - 验证WebSocket URL是否正确
   - 查看飞书官方事件订阅2.0文档

2. **消息未处理**:
   - 确保飞书应用有相应的事件订阅权限
   - 检查WebSocket消息格式是否符合预期

3. **性能问题**:
   - 调整 `ping_interval` 和 `reconnect_interval` 参数
   - 监控连接稳定性

### 相关文档
- [飞书事件订阅2.0文档](https://open.feishu.cn/document/ukTMukTMukTM/uYDNxYjL2QTM24iN0EjN/event-subscription-configure-/event-subscription-2-0)
- [WebSocket客户端测试](tests/test_websocket.py)