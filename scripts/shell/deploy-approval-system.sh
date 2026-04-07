#!/bin/bash
# OpenClaw/OpenCode 审批系统集成部署脚本
# 一键部署到 opencode-feishu-bridge

set -e

echo "╔═══════════════════════════════════════════════════╗"
echo "║     OpenClaw/OpenCode 审批系统集成部署           ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# 路径配置
BRIDGE_DIR="/home/user/workspace/opencode-feishu-bridge"
MYCOMPANY_DIR="/home/user/workspace/MyCompany"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查目录
if [ ! -d "$BRIDGE_DIR" ]; then
    echo "❌ 错误: 找不到桥接项目目录: $BRIDGE_DIR"
    exit 1
fi

if [ ! -d "$MYCOMPANY_DIR" ]; then
    echo "❌ 错误: 找不到 MyCompany 目录: $MYCOMPANY_DIR"
    exit 1
fi

echo "📁 桥接项目目录: $BRIDGE_DIR"
echo "📁 MyCompany 目录: $MYCOMPANY_DIR"
echo ""

# ============================================
# 步骤 1: 复制核心文件到桥接项目
# ============================================
echo "📋 步骤 1/5: 部署核心文件..."

# 检查文件是否存在
if [ ! -f "$BRIDGE_DIR/approval_manager.py" ]; then
    echo "   ⚠️  approval_manager.py 不存在，请确保已创建"
    exit 1
fi

if [ ! -f "$BRIDGE_DIR/approval_integration.py" ]; then
    echo "   ⚠️  approval_integration.py 不存在，请确保已创建"
    exit 1
fi

echo "   ✅ 核心文件已就位"
echo ""

# ============================================
# 步骤 2: 创建配置文件
# ============================================
echo "📋 步骤 2/5: 创建配置文件..."

CONFIG_FILE="$BRIDGE_DIR/config.yaml"

if [ -f "$CONFIG_FILE" ]; then
    echo "   ⚠️  配置文件已存在，备份到 config.yaml.backup"
    cp "$CONFIG_FILE" "$CONFIG_FILE.backup"
fi

# 从模板创建配置
cat > "$CONFIG_FILE" << 'EOF'
# OpenClaw/OpenCode 审批系统配置
# 自动生成于 $(date)

feishu_bot_a:
  webhook_url: "${FEISHU_BOT_A_WEBHOOK}"
  secret: "${FEISHU_BOT_A_SECRET}"
  enabled: true

approval_server:
  host: "0.0.0.0"
  port: 8000
  ws_endpoint: "/ws/approval"
  api_prefix: "/api/approval"
  webhook_endpoint: "/webhook/feishu"
  notify_mode: "webhook"

openclaw_integration:
  enabled: true
  whitelist:
    - "ou_REDACTED_OPEN_ID"

logging:
  level: "INFO"
EOF

echo "   ✅ 配置文件已创建: $CONFIG_FILE"
echo ""

# ============================================
# 步骤 3: 检查依赖
# ============================================
echo "📋 步骤 3/5: 检查 Python 依赖..."

cd "$BRIDGE_DIR"

# 检查 aiohttp
if ! python3 -c "import aiohttp" 2>/dev/null; then
    echo "   📦 安装 aiohttp..."
    pip3 install aiohttp -q
fi

# 检查 websockets
if ! python3 -c "import websockets" 2>/dev/null; then
    echo "   📦 安装 websockets..."
    pip3 install websockets -q
fi

# 检查 PyYAML
if ! python3 -c "import yaml" 2>/dev/null; then
    echo "   📦 安装 PyYAML..."
    pip3 install pyyaml -q
fi

echo "   ✅ 依赖检查完成"
echo ""

# ============================================
# 步骤 4: 配置 MyCompany 客户端
# ============================================
echo "📋 步骤 4/5: 配置 MyCompany 客户端..."

# 确保客户端脚本存在
CLIENT_SCRIPT="$MYCOMPANY_DIR/.scripts/approval-bridge-client.sh"
if [ -f "$CLIENT_SCRIPT" ]; then
    chmod +x "$CLIENT_SCRIPT"
    echo "   ✅ 客户端脚本已配置"
else
    echo "   ⚠️  客户端脚本不存在: $CLIENT_SCRIPT"
fi

# 创建环境变量配置
cat > "$MYCOMPANY_DIR/.config/bridge-integration.conf" << EOF
# OpenClaw/OpenCode 桥接集成配置
# 自动生成于 $(date)

BRIDGE_WS_URL=ws://localhost:8000/ws/approval
BRIDGE_HTTP_URL=http://localhost:8000
FEISHU_USER_ID=ou_REDACTED_OPEN_ID

# 审批通知模式: webhook | terminal | auto
APPROVAL_NOTIFY_MODE=webhook
EOF

echo "   ✅ 客户端配置已创建"
echo ""

# ============================================
# 步骤 5: 生成集成代码片段
# ============================================
echo "📋 步骤 5/5: 生成集成代码..."

cat > "$BRIDGE_DIR/INTEGRATE_TO_MAIN.py" << 'EOF'
# 将此代码添加到 main.py 中

# 导入审批系统集成
from approval_integration import setup_approval_system

# 在创建 app 后调用
app = web.Application()

# ... 其他初始化代码 ...

# 设置审批系统
approval_manager = setup_approval_system(app)

# 如果需要访问 approval_manager
# 可以保存到 app 中
app['approval_manager'] = approval_manager

# ... 启动服务器 ...
EOF

echo "   ✅ 集成代码片段已生成: $BRIDGE_DIR/INTEGRATE_TO_MAIN.py"
echo ""

# ============================================
# 部署完成
# ============================================
echo "╔═══════════════════════════════════════════════════╗"
echo "║              🎉 部署完成！                        ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
echo "📋 下一步操作:"
echo ""
echo "1. 配置环境变量:"
echo "   编辑 $MYCOMPANY_DIR/.secrets/feishu.env"
echo "   添加:"
echo "   FEISHU_BOT_A_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
echo "   FEISHU_BOT_A_SECRET=your-secret"
echo ""
echo "2. 修改 main.py:"
echo "   参考 $BRIDGE_DIR/INTEGRATE_TO_MAIN.py"
echo ""
echo "3. 启动桥接服务器:"
echo "   cd $BRIDGE_DIR"
echo "   python -m src.main"
echo ""
echo "4. 测试审批系统:"
echo "   cd $MYCOMPANY_DIR"
echo "   ./.scripts/approval-bridge-client.sh check-bridge"
echo ""
echo "📚 详细文档:"
echo "   $BRIDGE_DIR/INTEGRATION_GUIDE.md"
echo "   $BRIDGE_DIR/config.yaml.example"
echo ""
