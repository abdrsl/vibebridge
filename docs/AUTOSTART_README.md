# VibeBridge 自动启动和部署指南

## 🎯 功能特性

### 1. systemd User Service ✅
- 服务器意外停止时自动重启
- 用户级服务，无需 root 权限
- 日志通过 journalctl 统一管理

### 2. WebSocket 长连接 ✅
- 无需公网 URL 或隧道
- 持久连接，自动重连
- 推荐用于本地开发和个人使用

### 3. 简单管理 ✅
- systemctl 标准命令管理
- 实时日志查看
- 一键启停

## 📦 安装

### 方法1: systemd user service（推荐）

```bash
# 创建 systemd user 目录
mkdir -p ~/.config/systemd/user

# 复制服务文件
cp deploy/vibebridge.service ~/.config/systemd/user/

# 注意：deploy/vibebridge.service 中的端口是 8000
# 如使用 9000 端口，请编辑服务文件修改 --port 参数

# 重新加载 systemd
systemctl --user daemon-reload

# 启用开机自启
systemctl --user enable vibebridge

# 启动服务
systemctl --user start vibebridge
```

服务文件示例 (`~/.config/systemd/user/vibebridge.service`)：

```ini
[Unit]
Description=VibeBridge — IM gateway for local AI coding agents
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=/home/akliedrak/workspace/vibebridge
Environment=PATH=/home/akliedrak/workspace/vibebridge/.venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/home/akliedrak/workspace/vibebridge/src
Environment=VIBEBRIDGE_PORT=9000
ExecStart=/home/akliedrak/workspace/vibebridge/.venv/bin/python -m uvicorn vibebridge.server:app --host 0.0.0.0 --port 9000
Restart=always
RestartSec=5
StandardOutput=append:/home/akliedrak/workspace/vibebridge/.logs/server.log
StandardError=append:/home/akliedrak/workspace/vibebridge/.logs/server.log

[Install]
WantedBy=default.target
```

### 方法2: crontab（备用）

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每分钟检查并启动）
* * * * * systemctl --user is-active vibebridge || systemctl --user start vibebridge
```

## 🚀 使用方法

### systemctl 标准命令

```bash
# 启动服务
systemctl --user start vibebridge

# 停止服务
systemctl --user stop vibebridge

# 重启服务
systemctl --user restart vibebridge

# 查看状态
systemctl --user status vibebridge

# 启用开机自启
systemctl --user enable vibebridge

# 禁用开机自启
systemctl --user disable vibebridge
```

### 日志查看

```bash
# 实时查看日志
journalctl --user -u vibebridge -f

# 查看最近 100 行
journalctl --user -u vibebridge -n 100

# 查看今天日志
journalctl --user -u vibebridge --since today

# 查看日志文件（如果配置了 StandardOutput）
tail -f .logs/server.log
```

### 健康检查

```bash
# 检查服务是否运行
curl http://localhost:9000/health

# 预期输出
{"ok":true,"providers":{"opencode":true,"kimi":true,"claude":true}}
```

## 📊 状态检查

```bash
systemctl --user status vibebridge
```

预期输出包含：
- `Active: active (running)` — 服务运行中
- `Loaded: enabled` — 已启用开机自启

## 🔧 配置文件

### 环境变量

创建 `.env` 文件：

```bash
# Feishu
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_ENCRYPT_KEY=xxx
FEISHU_VERIFICATION_TOKEN=xxx

# Provider API Keys（按需配置）
DEEPSEEK_API_KEY=xxx
KIMI_API_KEY=xxx
OPENROUTER_API_KEY=xxx
```

### 服务配置

编辑 `~/.config/systemd/user/vibebridge.service`：

```ini
[Service]
# 修改工作目录
WorkingDirectory=/your/path/to/vibebridge

# 修改端口
ExecStart=... --port 9000

# 修改环境变量
Environment=YOUR_KEY=your_value
```

修改后重载：

```bash
systemctl --user daemon-reload
systemctl --user restart vibebridge
```

## 📝 管理脚本 (manage.sh)

项目根目录提供 `manage.sh` 脚本作为 systemctl 的便捷封装：

```bash
./manage.sh           # 交互式菜单
./manage.sh start     # 启动服务
./manage.sh stop      # 停止服务
./manage.sh restart   # 重启服务
./manage.sh status    # 查看状态
./manage.sh log       # 查看日志
```

## 🔄 更新部署

### 更新代码后重启

```bash
cd /home/akliedrak/workspace/vibebridge
git pull

# 如果依赖有变化
pip install -e .

# 重启服务
systemctl --user restart vibebridge

# 验证
systemctl --user status vibebridge
curl http://localhost:9000/health
```

## 🛡️ 故障排除

### 服务无法启动

```bash
# 查看详细错误
journalctl --user -u vibebridge -n 50

# 常见原因：
# 1. 端口被占用：lsof -i :9000
# 2. .env 文件缺失或配置错误
# 3. Python 虚拟环境未正确设置
# 4. 权限问题：检查工作目录和日志目录权限
```

### 端口冲突

```bash
# 检查端口占用
lsof -i :9000

# 修改服务文件使用其他端口
# 编辑 ~/.config/systemd/user/vibebridge.service
# 将 --port 9000 改为 --port 其他端口
systemctl --user daemon-reload
systemctl --user restart vibebridge
```

### 日志目录权限

```bash
mkdir -p .logs
chmod 755 .logs
systemctl --user restart vibebridge
```

## 📁 目录结构

```
/home/akliedrak/workspace/vibebridge/
├── .logs/                    # 日志目录
├── .config/systemd/user/     # systemd 服务文件
│   └── vibebridge.service
├── deploy/                   # 部署模板
│   └── vibebridge.service
├── .env                      # 环境变量
├── src/vibebridge/           # 核心代码
└── docs/                     # 文档
```
