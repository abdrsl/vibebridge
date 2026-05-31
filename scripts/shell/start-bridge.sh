#!/bin/bash
# Feishu Bridge 启动脚本（Python 版本）
# 用于 VibeBridge 多 Agent 系统

set -e

echo "🚀 启动 Feishu Bridge..."
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 切换到脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行 install.sh"
    exit 1
fi

# 加载 API Keys
echo "📡 加载 API Keys..."
# API keys are loaded from environment or .env file by the application
echo "✅ 使用环境变量和 .env 文件加载 API Keys"

# 激活虚拟环境并启动 Bridge
echo ""
echo "🎯 启动 Bridge..."
source venv/bin/activate

# 使用 nohup 后台运行
LOG_FILE="$SCRIPT_DIR/logs/bridge-$(date +%Y%m%d).log"
mkdir -p "$SCRIPT_DIR/logs"

echo "日志文件: $LOG_FILE"

# 启动方式1: 使用 vibebridge 命令（如果已安装）
if venv/bin/vibebridge --help >/dev/null 2>&1; then
    echo "使用 vibebridge 命令启动..."
    nohup venv/bin/vibebridge start > "$LOG_FILE" 2>&1 &
# 启动方式2: 直接运行 main.py
elif [ -f "src/main.py" ]; then
    echo "使用 main.py 启动..."
    nohup python src/main.py > "$LOG_FILE" 2>&1 &
# 启动方式3: 使用 python -m
elif [ -d "src/vibebridge" ]; then
    echo "使用 python -m 启动..."
    nohup python -m vibebridge > "$LOG_FILE" 2>&1 &
else
    echo "❌ 未找到启动入口"
    exit 1
fi

BRIDGE_PID=$!
echo $BRIDGE_PID > /tmp/feishu-bridge.pid

echo ""
echo "Bridge PID: $BRIDGE_PID"

# 等待启动验证
sleep 5

if ps -p $BRIDGE_PID > /dev/null 2>&1; then
    echo "✅ Bridge 启动成功"
    echo ""
    echo "查看日志:"
    tail -20 "$LOG_FILE"
else
    echo "❌ Bridge 启动失败"
    echo ""
    echo "查看错误日志:"
    tail -50 "$LOG_FILE"
    exit 1
fi

echo ""
echo "========================================"
echo "✅ Feishu Bridge 启动完成"
echo "========================================"
echo ""
echo "管理命令:"
echo "  查看状态: ps -p $BRIDGE_PID"
echo "  查看日志: tail -f $LOG_FILE"
echo "  停止服务: kill $BRIDGE_PID"
echo ""
