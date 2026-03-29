#!/bin/bash
#
# 安装OpenCode-Feishu Bridge自动启动

PROJECT_DIR="/home/user/workspace/opencode-feishu-bridge"

echo "=========================================="
echo "安装 OpenCode-Feishu Bridge 自动启动"
echo "=========================================="
echo ""

# 方法1: 使用crontab（推荐）
install_crontab() {
    echo "📦 方法1: 使用crontab安装自动启动..."
    echo ""
    
    # 检查crontab是否已有配置
    if crontab -l 2>/dev/null | grep -q "ai-project-autostart"; then
        echo "⚠️  crontab中已存在配置"
        echo "   如需重新安装，请先运行: ./uninstall_autostart.sh"
        return 1
    fi
    
    # 添加到crontab
    (crontab -l 2>/dev/null; echo ""; echo "# OpenCode-Feishu Bridge自动启动"; echo "* * * * * cd $PROJECT_DIR && flock -n /tmp/opencode-feishu-bridge-autostart.lock -c './manage.sh start' >> $PROJECT_DIR/logs/cron.log 2>&1") | crontab -
    
    echo "✅ 已添加到crontab"
    echo "   每分钟检查服务器状态"
    echo ""
    echo "查看crontab:"
    echo "   crontab -l"
}

# 方法2: 使用systemd（需要root）
install_systemd() {
    if [ "$EUID" -ne 0 ]; then
        echo "❌ 安装systemd服务需要root权限"
        echo "   请使用: sudo $0 systemd"
        return 1
    fi
    
    echo "📦 方法2: 使用systemd安装服务..."
    echo ""
    
    ./install_services.sh
}

# 显示菜单
show_menu() {
    echo "选择安装方式:"
    echo ""
    echo "1) 使用crontab（推荐，无需root）"
    echo "   - 每分钟检查服务器状态"
    echo "   - 服务器停止时自动重启"
    echo ""
    echo "2) 使用systemd（需要root）"
    echo "   - 系统级服务管理"
    echo "   - 更可靠的自动重启"
    echo "   - 支持journalctl日志"
    echo ""
    echo "3) 仅创建快捷命令"
    echo "   - 不安装自动启动"
    echo "   - 创建aip-start等命令"
    echo ""
    echo "0) 退出"
    echo ""
}

# 创建快捷命令
create_shortcuts() {
    echo "🔗 创建快捷命令..."
    
    # 添加到.bashrc
    if ! grep -q "aip-start()" ~/.bashrc 2>/dev/null; then
        cat >> ~/.bashrc << EOF

# OpenCode-Feishu Bridge 快捷命令
aip-start() { cd $PROJECT_DIR && ./manage.sh start; }
aip-stop() { cd $PROJECT_DIR && ./manage.sh stop; }
aip-restart() { cd $PROJECT_DIR && ./manage.sh restart; }
aip-status() { cd $PROJECT_DIR && ./manage.sh status; }
aip-log() { tail -f $PROJECT_DIR/logs/server.log; }
aip-tunnel() { cd $PROJECT_DIR && ./manage.sh tunnel; }
EOF
        echo "✅ 快捷命令已添加到 ~/.bashrc"
        echo "   请运行: source ~/.bashrc"
    else
        echo "✅ 快捷命令已存在"
    fi
    
    echo ""
    echo "快捷命令列表:"
    echo "  aip-start    - 启动服务"
    echo "  aip-stop     - 停止服务"
    echo "  aip-restart  - 重启服务"
    echo "  aip-status   - 查看状态"
    echo "  aip-log      - 查看日志"
    echo "  aip-tunnel   - 启动隧道"
}

# 主程序
case "${1:-menu}" in
    crontab|1)
        install_crontab
        create_shortcuts
        echo ""
        echo "=========================================="
        echo "✅ 安装完成！"
        echo "=========================================="
        echo ""
        echo "使用方法:"
        echo "  1. 手动管理: cd $PROJECT_DIR && ./manage.sh"
        echo "  2. 快捷命令: aip-start, aip-status, ..."
        echo "  3. 自动启动: crontab每分钟自动检查"
        echo ""
        echo "查看日志:"
        echo "  $PROJECT_DIR/logs/server.log"
        echo "  $PROJECT_DIR/logs/cron.log"
        ;;
    systemd|2)
        install_systemd
        ;;
    shortcuts|3)
        create_shortcuts
        echo ""
        echo "✅ 快捷命令已创建"
        echo "   请运行: source ~/.bashrc"
        ;;
    menu|"")
        show_menu
        echo -n "请选择 [0-3]: "
        read choice
        case $choice in
            1) $0 crontab ;;
            2) $0 systemd ;;
            3) $0 shortcuts ;;
            0) exit 0 ;;
            *) echo "无效选择"; exit 1 ;;
        esac
        ;;
    *)
        echo "用法: $0 [crontab|systemd|shortcuts|menu]"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "提示:"
echo "=========================================="
echo "首次启动请运行:"
echo "  cd $PROJECT_DIR && ./manage.sh start"
echo ""
echo "或使用快捷命令:"
echo "  aip-start"
echo "=========================================="