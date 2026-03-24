#!/bin/bash
#
# AI Project Lab 服务安装脚本
# 安装systemd服务实现自动启动和监控

set -e

PROJECT_DIR="/home/user/workspace/ai-project"
SERVICE_USER="akliedrak"

echo "=========================================="
echo "AI Project Lab 服务安装"
echo "=========================================="
echo ""

# 检查是否以root运行
if [ "$EUID" -ne 0 ]; then 
    echo "❌ 请使用 sudo 运行此脚本"
    echo "   sudo $0"
    exit 1
fi

# 安装服务
echo "📦 安装系统服务..."

cp "$PROJECT_DIR/ai-project.service" /etc/systemd/system/
cp "$PROJECT_DIR/ai-project-tunnel.service" /etc/systemd/system/

# 重新加载systemd
systemctl daemon-reload

echo ""
echo "✅ 服务已安装"
echo ""

# 启动服务
echo "🚀 启动服务..."

systemctl enable ai-project.service
systemctl start ai-project.service

sleep 3

if systemctl is-active --quiet ai-project.service; then
    echo "✅ 主服务已启动"
else
    echo "❌ 主服务启动失败"
    echo "查看日志: journalctl -u ai-project.service"
    exit 1
fi

# 启动隧道服务
systemctl enable ai-project-tunnel.service
systemctl start ai-project-tunnel.service

echo ""
echo "=========================================="
echo "✅ 安装完成！"
echo "=========================================="
echo ""
echo "服务状态:"
echo "  主服务:   systemctl status ai-project.service"
echo "  隧道服务: systemctl status ai-project-tunnel.service"
echo ""
echo "查看日志:"
echo "  主服务:   journalctl -u ai-project.service -f"
echo "  隧道服务: journalctl -u ai-project-tunnel.service -f"
echo ""
echo "常用命令:"
echo "  启动:   sudo systemctl start ai-project.service"
echo "  停止:   sudo systemctl stop ai-project.service"
echo "  重启:   sudo systemctl restart ai-project.service"
echo "  查看状态: sudo systemctl status ai-project.service"
echo ""
echo "当前URL:"
sleep 2
if [ -f "$PROJECT_DIR/logs/current_tunnel_url.txt" ]; then
    URL=$(cat "$PROJECT_DIR/logs/current_tunnel_url.txt")
    echo "  🌐 $URL"
    echo "  🔗 Webhook: $URL/feishu/webhook/opencode"
else
    echo "  ⏳ 隧道正在启动中，稍后再查看..."
fi
echo ""

# 创建快捷命令
echo "创建快捷命令..."
cat > /usr/local/bin/aip-status << 'EOF'
#!/bin/bash
echo "=========================================="
echo "AI Project Lab 状态"
echo "=========================================="
echo ""
echo "主服务:"
systemctl status ai-project.service --no-pager -l | head -10
echo ""
echo "隧道服务:"
systemctl status ai-project-tunnel.service --no-pager -l | head -10
echo ""
echo "当前URL:"
if [ -f /home/user/workspace/ai-project/logs/current_tunnel_url.txt ]; then
    cat /home/user/workspace/ai-project/logs/current_tunnel_url.txt
fi
echo ""
echo "=========================================="
EOF
chmod +x /usr/local/bin/aip-status

cat > /usr/local/bin/aip-log << 'EOF'
#!/bin/bash
journalctl -u ai-project.service -f
EOF
chmod +x /usr/local/bin/aip-log

cat > /usr/local/bin/aip-restart << 'EOF'
#!/bin/bash
sudo systemctl restart ai-project.service ai-project-tunnel.service
echo "✅ 服务已重启"
EOF
chmod +x /usr/local/bin/aip-restart

echo ""
echo "快捷命令已创建:"
echo "  aip-status  - 查看服务状态"
echo "  aip-log     - 查看主服务日志"
echo "  aip-restart - 重启所有服务"
echo ""