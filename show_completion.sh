#!/bin/bash
#
# AI Project Lab 自动启动和隧道切换系统 - 安装完成总结

clear
echo "=========================================="
echo "🎉 自动启动系统安装完成！"
echo "=========================================="
echo ""

cd /home/user/workspace/ai-project

# 显示当前状态
echo "📊 当前系统状态:"
echo "----------------------------------------"
./manage.sh status
echo ""

# 显示已安装的功能
echo "✅ 已安装的功能:"
echo "----------------------------------------"
echo "1. 服务器自启动"
echo "   - crontab每分钟检查服务器状态"
echo "   - 服务器停止时自动重启"
echo "   - 日志: logs/cron.log"
echo ""
echo "2. 快捷命令"
echo "   source ~/.bashrc 后可以使用:"
echo "   • aip-start    - 启动服务"
echo "   • aip-stop     - 停止服务"
echo "   • aip-restart  - 重启服务"
echo "   • aip-status   - 查看状态"
echo "   • aip-log      - 查看日志"
echo ""
echo "3. 管理脚本"
echo "   ./manage.sh - 交互式管理菜单"
echo ""

# 显示文件
echo "📁 创建的文件:"
echo "----------------------------------------"
echo "• auto_recovery.sh      - 自动恢复脚本"
echo "• manage.sh             - 管理脚本（推荐）"
echo "• install_autostart.sh  - 自动启动安装"
echo "• ai-project.service    - systemd服务文件"
echo "• crontab.config        - crontab配置"
echo "• AUTOSTART_README.md   - 详细文档"
echo ""

# 下一步
echo "🚀 下一步操作:"
echo "----------------------------------------"
echo "1. 加载快捷命令:"
echo "   source ~/.bashrc"
echo ""
echo "2. 启动服务（如未启动）:"
echo "   aip-start"
echo "   或"
echo "   ./manage.sh start"
echo ""
echo "3. 查看状态:"
echo "   aip-status"
echo ""
echo "4. 启动隧道（公网访问）:"
echo "   需要手动安装并配置ngrok:"
echo "   • ngrok config add-authtoken YOUR_TOKEN"
echo "   • 然后运行: ./manage.sh tunnel"
echo ""
echo "5. 配置Feishu:"
echo "   获取Webhook URL后配置到Feishu"
echo ""

# 重要提示
echo "⚠️  重要提示:"
echo "----------------------------------------"
echo "• 服务器PID文件: logs/pids/server.pid"
echo "• 隧道PID文件: logs/pids/tunnel.pid"
echo "• 当前URL文件: logs/current_tunnel_url.txt"
echo "• 所有日志都在 logs/ 目录"
echo "• crontab会自动保持服务器运行"
echo ""

# 故障排除
echo "🔧 故障排除:"
echo "----------------------------------------"
echo "查看日志:"
echo "  tail -f logs/server.log      # 服务器日志"
echo "  tail -f logs/cron.log        # 自动启动日志"
echo "  tail -f logs/auto_recovery.log # 恢复日志"
echo ""
echo "手动控制:"
echo "  ./manage.sh                  # 交互式菜单"
echo "  ./manage.sh start           # 启动"
echo "  ./manage.sh stop            # 停止"
echo "  ./manage.sh restart         # 重启"
echo ""

echo "=========================================="
echo "✨ 系统已就绪！"
echo "=========================================="
echo ""
echo "详细文档请查看:"
echo "  cat AUTOSTART_README.md"
echo ""
echo "立即开始:"
echo "  source ~/.bashrc && aip-status"
echo ""