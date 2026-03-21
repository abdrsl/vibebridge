# Feishu Webhook Setup

## Current Tunnel Status

✅ **Tunnel is running** with serveo.net (free SSH tunnel)

- **Tunnel URL**: `https://01ce114b53941352-112-96-54-27.serveousercontent.com`
- **Webhook Endpoint**: `https://01ce114b53941352-112-96-54-27.serveousercontent.com/feishu/webhook/opencode`
- **Response Time**: ~1.9-2.0 seconds (within Feishu's 3-second limit)
- **Encryption**: **DISABLED** (Recommended for initial setup due to decryption issues)
- **Status**: **FULLY OPERATIONAL** ✅ (URL verification successful + Live message processing verified)

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
    - **URL**: `https://01ce114b53941352-112-96-54-27.serveousercontent.com/feishu/webhook/opencode`
   - **Verification Token**: `z3V8Qc6B3NqXjaKpP5rL9sT2uV1yW4x7A0D4F6H9K2M`
    - **Encrypt Key**: `z8V8Qc6B3NqXjwKpP5rL9sT2uV1yW4x7A0D3F6H9K2M`
    - **Important**: Disable encryption in Feishu console for now (toggle "启用加密" to OFF)
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

### Current Tunnel (localhost.run)

```bash
# Check tunnel status
ps aux | grep localhost.run

# View tunnel logs
tail -f logs/lhr_tunnel.log

# Restart tunnel (if needed)
pkill -f "localhost.run"
cd /home/user/workspace/ai-project
ssh -o StrictHostKeyChecking=no -R 80:localhost:8000 nokey@localhost.run > logs/lhr_tunnel.log 2>&1 &
```

**Note**: localhost.run domains are temporary and change each time you restart the tunnel. The current URL will remain valid as long as the SSH connection stays active.

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
cd /home/user/workspace/ai-project
pkill -f "uvicorn" 2>/dev/null || true
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > logs/server_final.log 2>&1 &
```

**Step 4: Test URL Verification (Unencrypted)**
```bash
curl -X POST https://01ce114b53941352-112-96-54-27.serveousercontent.com/feishu/webhook/opencode \
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

**Current Tunnel URL**: `https://01ce114b53941352-112-96-54-27.serveousercontent.com`

**To restart tunnel and get new URL:**

```bash
cd /home/user/workspace/ai-project
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

## Files Reference

- `app/main.py` - Webhook endpoint (`/feishu/webhook/opencode`)
- `app/feishu_crypto.py` - Encryption/decryption utilities
- `app/feishu_client.py` - Feishu API client and card builders
- `app/opencode_integration.py` - OpenCode task execution
- `app/task_store.py` - JSON file-based task storage
- `TUNNEL_SETUP.md` - Detailed tunnel comparison guide
- `start_ngrok.sh` - Ngrok setup script