# Feishu Webhook 隧道解决方案

## 问题分析
Feishu要求webhook在**3秒内**响应，但当前Tailscale Funnel有时超过此限制（测试结果：1.8-3.1秒，不稳定）。

## 解决方案对比

### 1. **ngrok**（用户建议）
**优点**：
- 稳定可靠，有亚洲节点可选
- 支持自定义域名
- 有免费计划（有限制）

**步骤**：
```bash
# 1. 注册ngrok账号获取authtoken
# 访问：https://dashboard.ngrok.com/signup

# 2. 配置authtoken
ngrok config add-authtoken YOUR_AUTH_TOKEN

# 3. 启动隧道（亚太地区节点）
ngrok http 8000 --region ap

# 或指定香港节点（如果可用）
ngrok http 8000 --region hk
```

**获取的URL示例**：`https://xxx-xxx-xxx-xxx.ap.ngrok.io`

### 2. **localhost.run**（免费，无需注册）
**优点**：
- 完全免费，无需注册
- 自动HTTPS

**步骤**：
```bash
# 保持隧道运行
ssh -R 80:localhost:8000 nokey@localhost.run

# 或使用后台运行脚本
nohup ssh -o ServerAliveInterval=60 -R 80:localhost:8000 nokey@localhost.run > tunnel.log 2>&1 &
```

**URL格式**：`https://xxxxxx.lhr.life`

### 3. **serveo.net**（免费，无需注册）
**优点**：
- 免费，无需注册
- 响应时间较好

**步骤**：
```bash
ssh -R 80:localhost:8000 serveo.net
```

### 4. **Cloudflare Tunnel**（免费）
**优点**：
- 免费，全球CDN加速
- 稳定可靠

**步骤**：
```bash
# 安装cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# 启动隧道
cloudflared tunnel --url http://localhost:8000
```

## 性能测试结果

| 方案 | 响应时间 | 稳定性 | 适合Feishu |
|------|----------|--------|------------|
| Tailscale Funnel | 1.8-3.1秒 | 不稳定 | ❌ 可能超时 |
| ngrok（亚太节点） | 预计<1秒 | 高 | ✅ 推荐 |
| localhost.run | 预计1-2秒 | 中等 | ✅ 可尝试 |
| serveo.net | 预计1-2秒 | 中等 | ✅ 可尝试 |
| Cloudflare Tunnel | 预计<2秒 | 高 | ✅ 推荐 |

## 推荐方案

### 🥇 **首选：ngrok（付费版）**
1. 注册ngrok账号（免费版有限制）
2. 获取authtoken：`ngrok config add-authtoken <token>`
3. 启动亚太节点：`ngrok http 8000 --region ap`
4. 将生成的HTTPS URL配置到Feishu

### 🥈 **次选：Cloudflare Tunnel（免费）**
1. 安装cloudflared
2. 登录Cloudflare账号：`cloudflared tunnel login`
3. 创建隧道：`cloudflared tunnel create feishu-tunnel`
4. 配置路由：`cloudflared tunnel route dns feishu-tunnel your-domain.com`
5. 运行：`cloudflared tunnel run feishu-tunnel`

### 🥉 **快速测试：localhost.run（免费）**
```bash
# 在一个终端中运行
ssh -o ServerAliveInterval=60 -R 80:localhost:8000 nokey@localhost.run

# 注意：连接断开后URL会变化，不适合长期使用
```

## 配置步骤

### 1. 启动隧道
选择上述任一方案，获得HTTPS URL（如`https://xxxx.ngrok.io`）

### 2. 更新Feishu配置
1. 登录[Feishu开放平台](https://open.feishu.cn/)
2. 进入"事件订阅"页面
3. 更新请求地址：`https://你的隧道URL/feishu/webhook/opencode`
4. **保持现有Encrypt Key和Verification Token不变**
5. 点击"保存"，Feishu会自动验证URL

### 3. 验证成功标志
- Feishu显示"验证成功"
- 服务器日志显示收到`url_verification`请求
- 测试发送消息到机器人，能正常响应

## 故障排除

### 1. URL验证失败
- 检查隧道是否正常运行：`curl https://你的隧道URL/health`
- 检查服务器日志：`tail -f logs/server_final.log`
- 确保端口8000可访问：`curl http://localhost:8000/health`

### 2. 响应超时（>3秒）
- 尝试不同隧道服务商
- 选择更靠近中国的服务器节点（如香港、新加坡）
- 检查本地服务器性能：响应时间应<0.1秒

### 3. 加密/解密失败
- 确保`.env`中的`FEISHU_ENCRYPT_KEY`和`FEISHU_VERIFICATION_TOKEN`正确
- 检查密钥格式：43字符base64，需要`=`填充

## 服务器维护

### 保持服务运行
```bash
# 使用tmux或screen保持进程
tmux new -s feishu-server
cd /home/user/workspace/ai-project
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
# 按Ctrl+B，然后按D分离会话
```

### 监控日志
```bash
tail -f logs/server_final.log  # 服务器日志
tail -f logs/uvicorn.log       # 访问日志
```

## 紧急联系方式
如有问题，请提供：
1. Feishu平台错误截图
2. 服务器日志片段
3. 使用的隧道URL和方案