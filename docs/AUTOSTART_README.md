# AI Project Lab 自动启动和隧道切换系统

## 🎯 功能特性

### 1. 服务器自启动 ✅
- 服务器意外停止时自动检测并重启
- 支持多种启动方式（crontab/systemd）
- PID文件管理，避免重复启动

### 2. 隧道自动切换 ✅
- 智能检测隧道可用性
- 自动在ngrok、localtunnel之间切换
- 支持添加更多隧道工具
- 自动保存和更新Webhook URL

### 3. 简单管理 ✅
- 一键启动/停止/重启
- 实时状态查看
- 日志自动轮转

## 📦 安装

### 方法1: 使用crontab（推荐，无需root）

```bash
cd /home/user/workspace/ai-project
./install_autostart.sh
# 选择 1) 使用crontab
```

### 方法2: 使用systemd（需要root）

```bash
cd /home/user/workspace/ai-project
sudo ./install_autostart.sh
# 选择 2) 使用systemd
```

### 方法3: 仅创建快捷命令

```bash
cd /home/user/workspace/ai-project
./install_autostart.sh shortcuts
source ~/.bashrc
```

## 🚀 使用方法

### 方式1: 管理脚本（推荐）

```bash
cd /home/user/workspace/ai-project
./manage.sh
```

交互式菜单，选择操作：
- 1) 启动服务（服务器+隧道）
- 2) 停止服务
- 3) 重启服务
- 4) 查看状态
- 5) 查看日志
- 6) 仅启动隧道
- 7) 停止隧道

### 方式2: 快捷命令

安装后可以使用以下命令：

```bash
aip-start      # 启动服务
aip-stop       # 停止服务
aip-restart    # 重启服务
aip-status     # 查看状态
aip-log        # 查看日志
aip-tunnel     # 启动隧道
```

### 方式3: 直接命令

```bash
# 启动
./manage.sh start

# 停止
./manage.sh stop

# 重启
./manage.sh restart

# 状态
./manage.sh status

# 仅启动隧道
./manage.sh tunnel
```

## 📊 状态检查

```bash
./manage.sh status
```

输出示例：
```
==========================================
AI Project Lab 状态
==========================================

✅ 服务器: 运行中
   PID: 12345
   地址: http://127.0.0.1:8000

✅ 公网隧道: 可用 (ngrok)
   URL: https://xxxx.ngrok-free.dev
   Webhook: https://xxxx.ngrok-free.dev/feishu/webhook/opencode

==========================================
```

## 🌐 隧道自动切换

### 工作原理

1. **定期检查**：每5分钟检查当前隧道可用性
2. **自动切换**：如果当前隧道不可用，自动尝试备用隧道
3. **优先级**：
   - 第一优先：ngrok
   - 第二优先：localtunnel
   - 第三优先：expose（如已安装）

### 支持的隧道工具

1. **ngrok**（推荐）
   - 安装：`sudo apt install ngrok` 或从官网下载
   - 配置：`ngrok config add-authtoken YOUR_TOKEN`
   - 特点：稳定，URL固定

2. **localtunnel**
   - 安装：`npm install -g localtunnel`
   - 特点：免费，无需注册
   - 缺点：URL每次变化

3. **expose**（可选）
   - 安装：`npm install -g expose`
   - 特点：类似ngrok

### 当前URL查看

```bash
cat /home/user/workspace/ai-project/logs/current_tunnel_url.txt
```

## 📁 文件说明

```
/home/user/workspace/ai-project/
├── auto_recovery.sh        # 自动恢复脚本（底层）
├── manage.sh               # 管理脚本（推荐）
├── install_autostart.sh    # 安装脚本
├── install_services.sh     # systemd服务安装
├── ai-project.service      # systemd主服务
├── ai-project-tunnel.service  # systemd隧道服务
├── crontab.config          # crontab配置示例
├── logs/
│   ├── server.log          # 服务器日志
│   ├── ngrok.log          # ngrok日志
│   ├── localtunnel.log    # localtunnel日志
│   ├── auto_recovery.log  # 自动恢复日志
│   ├── cron.log           # 定时任务日志
 │   ├── current_tunnel_url.txt    # 当前隧道URL
 │   └── current_tunnel_type.txt   # 当前隧道类型
```

## 🔧 故障排除

### 服务器无法启动

```bash
# 检查日志
tail -100 /home/user/workspace/ai-project/logs/server.log

# 检查端口占用
lsof -i :8000

# 手动启动查看错误
cd /home/user/workspace/ai-project
source .venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### 隧道无法启动

```bash
# 检查ngrok
curl http://127.0.0.1:4040/api/tunnels

# 检查localtunnel
cat /home/user/workspace/ai-project/logs/localtunnel.log

# 手动启动隧道测试
cd /home/user/workspace/ai-project
ngrok http 8000
# 或
lt --port 8000
```

### 权限错误

```bash
# 确保脚本可执行
chmod +x /home/user/workspace/ai-project/*.sh

# 检查PID目录权限
mkdir -p /home/user/workspace/ai-project/logs/pids
```

## 📝 手动配置crontab

如果不想使用安装脚本，可以手动配置：

```bash
crontab -e
```

添加以下内容：

```cron
# AI Project Lab自动启动
* * * * * cd /home/user/workspace/ai-project && flock -n /tmp/ai-project-autostart.lock -c './manage.sh start' >> /home/user/workspace/ai-project/logs/cron.log 2>&1
```

## 🔄 更新和卸载

### 更新脚本

```bash
cd /home/user/workspace/ai-project
git pull  # 如果有git仓库
# 或者手动替换脚本
```

### 卸载自动启动

**crontab方式：**
```bash
crontab -e
# 删除包含"ai-project"的行
```

**systemd方式：**
```bash
sudo systemctl stop ai-project ai-project-tunnel
sudo systemctl disable ai-project ai-project-tunnel
sudo rm /etc/systemd/system/ai-project*.service
sudo systemctl daemon-reload
```

### 完全清理

```bash
cd /home/user/workspace/ai-project
./manage.sh stop
rm -f logs/current_tunnel_url.txt
rm -f logs/current_tunnel_type.txt
rm -rf logs/pids
```

## 💡 提示

1. **首次启动后**，查看Webhook URL：
   ```bash
   ./manage.sh status
   ```

2. **更新Feishu配置**时，使用显示的URL

3. **监控实时日志**：
   ```bash
   tail -f /home/user/workspace/ai-project/logs/server.log
   ```

4. **定期检查**自动恢复日志：
   ```bash
   tail -f /home/user/workspace/ai-project/logs/auto_recovery.log
   ```

5. **服务器重启后**，服务会自动启动（如果安装了自动启动）

## 🎉 现在可以使用了！

```bash
# 1. 启动服务
./manage.sh start

# 2. 查看状态和URL
./manage.sh status

# 3. 配置Feishu使用显示的Webhook URL
# 4. 开始使用！
```

## 📞 技术支持

如有问题，请查看：
- 服务器日志：`logs/server.log`
- 自动恢复日志：`logs/auto_recovery.log`
