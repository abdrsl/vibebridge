# 固定 URL 解决方案指南

## 问题
当前使用 serveo.net 提供的免费隧道，每次重启后 URL 都会变化，需要手动更新飞书 webhook 配置。

## 解决方案

### 方案 1: Ngrok (推荐，稳定)
Ngrok 提供稳定的隧道服务，付费版支持自定义域名。

#### 免费版
- 随机子域名，每次启动可能变化
- 有限制（连接数、带宽）
- 无需注册即可使用

#### 付费版 ($8/月起)
- 固定自定义子域名 (如 `yourapp.ngrok.io`)
- 更多功能：IP 白名单、流量分析等

#### 设置步骤
1. **安装 ngrok**
   ```bash
   # Linux
   curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
   echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
   sudo apt update && sudo apt install ngrok

   # 或使用 snap
   sudo snap install ngrok
   ```

2. **认证 ngrok** (获取 token)
   ```bash
   ngrok config add-authtoken YOUR_AUTH_TOKEN
   ```

3. **创建 ngrok 配置文件** `ngrok.yml`
   ```yaml
   version: "2"
   authtoken: YOUR_AUTH_TOKEN
   tunnels:
     ai-product-lab:
       proto: http
       addr: 8000
       # 付费功能: 自定义域名
       # domain: yourapp.ngrok.io
   ```

4. **修改隧道管理器** 使用 ngrok
   更新 `app/tunnel_manager.py` 中的命令：
   ```python
   cmd = ["ngrok", "http", "8000"]
   ```

5. **提取 URL** 从 ngrok API
   Ngrok 提供本地 API 获取隧道信息：
   ```bash
   curl http://localhost:4040/api/tunnels
   ```

#### 自动更新脚本
创建 `scripts/start_ngrok.py` 管理 ngrok 隧道和自动通知。

---

### 方案 2: Cloudflare Tunnel (完全免费，需要域名)
Cloudflare Tunnel 通过 Cloudflare 网络创建安全隧道，支持自定义域名。

#### 优势
- 完全免费
- 使用自己的域名
- 集成 Cloudflare 安全功能
- 稳定可靠

#### 设置步骤
1. **安装 cloudflared**
   ```bash
   # Linux
   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
   sudo dpkg -i cloudflared-linux-amd64.deb

   # 或使用包管理器
   sudo snap install cloudflared
   ```

2. **登录 Cloudflare**
   ```bash
   cloudflared tunnel login
   ```

3. **创建隧道**
   ```bash
   cloudflared tunnel create ai-product-lab
   ```

4. **配置 DNS 记录**
   ```bash
   cloudflared tunnel route dns ai-product-lab your-app.your-domain.com
   ```

5. **创建配置文件** `~/.cloudflared/config.yml`
   ```yaml
   tunnel: YOUR_TUNNEL_ID
   credentials-file: /home/user/.cloudflared/YOUR_TUNNEL_ID.json
   
   ingress:
     - hostname: your-app.your-domain.com
       service: http://localhost:8000
     - service: http_status:404
   ```

6. **启动隧道**
   ```bash
   cloudflared tunnel run ai-product-lab
   ```

7. **修改隧道管理器** 支持 Cloudflare Tunnel
   更新 `app/tunnel_manager.py` 使用 cloudflared 命令。

---

### 方案 3: 自有服务器 + 动态 DNS
如果您有自己的服务器或 VPS，可以设置固定 IP 或动态 DNS。

#### 步骤
1. **VPS 设置** (如 DigitalOcean, Linode, AWS EC2)
   - 购买 VPS (最低 $5/月)
   - 设置防火墙开放端口 80/443

2. **配置反向代理** (Nginx)
   ```nginx
   server {
       listen 80;
       server_name your-app.your-domain.com;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **设置 SSL** (Let's Encrypt)
   ```bash
   sudo certbot --nginx -d your-app.your-domain.com
   ```

4. **使用 SSH 隧道** 从本地到 VPS
   ```bash
   ssh -R 8000:localhost:8000 user@your-server.com
   ```

5. **固定 URL**: `https://your-app.your-domain.com`

---

## 集成到现有系统

### 修改隧道管理器支持多种后端
创建可配置的隧道后端：

```python
# config/tunnel_config.py
TUNNEL_BACKEND = "serveo"  # serveo, ngrok, cloudflare, custom

# 后端配置
BACKEND_CONFIGS = {
    "serveo": {
        "command": ["ssh", "-o", "StrictHostKeyChecking=no", "-R", "80:localhost:8000", "serveo.net"],
        "url_pattern": r"https://[a-zA-Z0-9-]+\.serveousercontent\.com",
    },
    "ngrok": {
        "command": ["ngrok", "http", "8000"],
        "api_url": "http://localhost:4040/api/tunnels",
        "url_extract": lambda data: data["tunnels"][0]["public_url"],
    },
    "cloudflare": {
        "command": ["cloudflared", "tunnel", "--url", "http://localhost:8000"],
        "url_pattern": r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com",
    },
}
```

### 自动切换脚本
创建 `scripts/setup_tunnel.py` 引导用户选择方案：

```python
#!/usr/bin/env python3
"""
交互式隧道设置脚本
"""
import questionary

def setup_tunnel():
    choice = questionary.select(
        "选择隧道解决方案:",
        choices=[
            "serveo.net (免费，URL 变化)",
            "ngrok (免费版，URL 变化)",
            "ngrok (付费版，固定域名)",
            "Cloudflare Tunnel (免费，固定域名)",
            "自有服务器",
        ]
    ).ask()
    
    # 根据选择生成配置
    # ...
```

---

## 推荐方案

### 快速启动 (免费)
继续使用 serveo.net + 自动通知系统
- ✅ 完全免费
- ✅ 自动飞书通知
- ❌ URL 会变化

### 生产环境 (推荐)
**Cloudflare Tunnel** 或 **Ngrok 付费版**
- ✅ 固定 URL
- ✅ 稳定可靠  
- ✅ 安全功能
- ⚠️ 需要少量配置

### 企业级
**自有 VPS + Nginx + SSL**
- ✅ 完全控制
- ✅ 最佳性能
- ✅ 无第三方依赖
- ⚠️ 需要运维知识

---

## 实施计划

### 阶段 1: 自动通知 (已完成)
- ✅ 隧道管理器检测 URL 变化
- ✅ 自动发送飞书通知
- ✅ 启动脚本集成

### 阶段 2: 固定 URL 解决方案
1. 选择并配置固定 URL 方案
2. 修改隧道管理器支持新后端
3. 更新启动脚本和文档
4. 测试并切换

### 阶段 3: 监控和可靠性
1. 添加健康检查
2. 自动故障转移
3. 详细日志和报警

---

## 故障排除

### 常见问题
1. **隧道连接失败**
   - 检查网络连接
   - 验证 SSH 密钥
   - 尝试不同隧道服务

2. **飞书通知未发送**
   - 检查 FEISHU_APP_ID 和 FEISHU_APP_SECRET
   - 验证默认聊天 ID
   - 查看隧道管理器日志

3. **URL 提取失败**
   - 检查隧道日志格式
   - 更新正则表达式模式
   - 手动测试 URL 提取

### 日志位置
- 服务器日志: `logs/server.log`
- 隧道日志: `logs/tunnel.log`
- 隧道管理器: `logs/tunnel_manager.log`
- 上次 URL: `logs/last_tunnel_url.txt`

---

## 下一步
1. 选择适合的固定 URL 方案
2. 按照对应方案文档配置
3. 更新系统配置并测试
4. 更新飞书 webhook URL 为固定地址

如需帮助，请参考各方案官方文档或联系维护者。