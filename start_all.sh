#!/bin/bash
#
# OpenCode-Feishu Bridge 完整启动脚本
# 启动服务器、隧道和监控服务

cd /home/user/workspace/opencode-feishu-bridge

echo "=========================================="
echo "🚀 OpenCode-Feishu Bridge 完整启动"
echo "=========================================="
echo ""

# 1. 检查并启动服务器
echo "📊 步骤1: 检查服务器..."
if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "   ✅ 服务器已在运行"
else
    echo "   🔄 启动服务器..."
    source .venv/bin/activate
    nohup python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > logs/server.log 2>&1 &
    sleep 5
    if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "   ✅ 服务器启动成功"
    else
        echo "   ❌ 服务器启动失败"
        exit 1
    fi
fi
echo ""

# 2. 启动隧道
echo "🌐 步骤2: 启动公网隧道..."
./manage.sh tunnel &
sleep 10

# 检查隧道是否启动
if [ -f logs/current_tunnel_url.txt ]; then
    URL=$(cat logs/current_tunnel_url.txt)
    echo "   ✅ 隧道已启动: $URL"
else
    echo "   ⚠️  隧道启动中，可能需要几秒钟..."
fi
echo ""

# 3. 启动隧道监控服务
echo "👁️  步骤3: 启动隧道监控服务..."
if pgrep -f "tunnel_monitor.py" > /dev/null; then
    echo "   ✅ 监控服务已在运行"
else
    source .venv/bin/activate
    nohup python scripts/tunnel_monitor.py > logs/tunnel_monitor.log 2>&1 &
    echo "   ✅ 监控服务已启动"
fi
echo ""

# 4. 显示状态
echo "=========================================="
echo "📋 系统状态"
echo "=========================================="
echo ""

# 服务器状态
if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "✅ 服务器: http://127.0.0.1:8000"
else
    echo "❌ 服务器: 不可用"
fi

# 隧道状态
if [ -f logs/current_tunnel_url.txt ]; then
    URL=$(cat logs/current_tunnel_url.txt)
    echo "✅ 公网URL: $URL"
    echo "🔗 Webhook: $URL/feishu/webhook/opencode"
else
    echo "⏳ 公网URL: 启动中..."
fi

# 进程状态
echo ""
echo "📊 进程:"
echo "   服务器PID: $(pgrep -f 'uvicorn src.main:app' | head -1)"
echo "   隧道PID: $(pgrep -f 'lt --port\|ngrok http' | head -1)"
echo "   监控PID: $(pgrep -f 'tunnel_monitor.py' | head -1)"

echo ""
echo "=========================================="
echo "✨ 启动完成！"
echo "=========================================="
echo ""
echo "📖 使用说明:"
echo "   1. 将Webhook URL配置到Feishu"
echo "   2. 发送消息测试连接"
echo "   3. URL变更时会自动通知Feishu"
echo ""
echo "🔧 管理命令:"
echo "   ./manage.sh status    - 查看状态"
echo "   ./manage.sh restart   - 重启服务"
echo "   ./manage.sh stop      - 停止服务"
echo ""
echo "📊 查看日志:"
echo "   tail -f logs/server.log"
echo "   tail -f logs/tunnel_monitor.log"
echo ""
echo "=========================================="