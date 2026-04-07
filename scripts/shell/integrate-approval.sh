#!/bin/bash
# 一键集成审批系统到 opencode-feishu-bridge
# 最小化修改，不破坏现有功能

set -e

BRIDGE_DIR="/home/user/workspace/opencode-feishu-bridge"
PLUGIN_FILE="$BRIDGE_DIR/approval_plugin.py"

echo "╔═══════════════════════════════════════════════════╗"
echo "║     一键集成审批系统                             ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# 检查插件文件
if [ ! -f "$PLUGIN_FILE" ]; then
    echo "❌ 错误: 找不到 $PLUGIN_FILE"
    exit 1
fi

echo "📁 桥接项目: $BRIDGE_DIR"
echo "📄 插件文件: $PLUGIN_FILE"
echo ""

# 查找 main.py
MAIN_PY=""
if [ -f "$BRIDGE_DIR/src/main.py" ]; then
    MAIN_PY="$BRIDGE_DIR/src/main.py"
elif [ -f "$BRIDGE_DIR/main.py" ]; then
    MAIN_PY="$BRIDGE_DIR/main.py"
else
    echo "❌ 错误: 找不到 main.py"
    exit 1
fi

echo "🎯 目标文件: $MAIN_PY"
echo ""

# 备份
echo "📋 步骤 1/3: 备份原文件..."
cp "$MAIN_PY" "$MAIN_PY.backup.$(date +%Y%m%d_%H%M%S)"
echo "   ✅ 已备份"
echo ""

# 检查是否已经集成
echo "📋 步骤 2/3: 检查现有集成..."
if grep -q "approval_plugin\|handle_create_approval" "$MAIN_PY"; then
    echo "   ⚠️  检测到已有审批系统集成"
    echo "   跳过集成（如需重新集成，请恢复备份）"
    exit 0
fi
echo "   ✅ 未检测到现有集成"
echo ""

# 集成代码
echo "📋 步骤 3/3: 集成审批系统..."

# 在文件末尾添加集成代码
cat >> "$MAIN_PY" << 'EOF'


# ============================================
# OpenClaw 审批系统集成（自动生成）
# ============================================

# 导入审批插件
import sys
sys.path.insert(0, str(Path(__file__).parent))

# 执行插件代码
exec(open(Path(__file__).parent / "approval_plugin.py").read())

print("✅ OpenClaw 审批系统已集成")
EOF

echo "   ✅ 集成完成"
echo ""

# 完成
echo "╔═══════════════════════════════════════════════════╗"
echo "║              🎉 集成完成！                       ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
echo "📋 新增功能:"
echo "   - POST /api/approval/create     创建审批请求"
echo "   - GET  /api/approval/{id}       查询审批状态"
echo "   - GET  /api/approval/pending    列出待审批"
echo "   - POST /webhook/approval        飞书回调"
echo "   - WS   /ws/approval             WebSocket连接"
echo ""
echo "🚀 启动服务:"
echo "   cd $BRIDGE_DIR"
echo "   python -m src.main"
echo ""
echo "🧪 测试:"
echo "   curl http://localhost:8000/api/approval/pending"
echo ""
