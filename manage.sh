#!/bin/bash
# VibeBridge 管理脚本 - systemctl 便捷封装

SERVICE_NAME="vibebridge"
PORT="${VIBEBRIDGE_PORT:-9000}"

show_help() {
    echo "VibeBridge 管理脚本"
    echo ""
    echo "用法: ./manage.sh [命令]"
    echo ""
    echo "命令:"
    echo "  start     启动服务"
    echo "  stop      停止服务"
    echo "  restart   重启服务"
    echo "  status    查看服务状态"
    echo "  log       查看实时日志"
    echo "  health    健康检查"
    echo "  enable    启用开机自启"
    echo "  disable   禁用开机自启"
    echo "  setup     安装 systemd 服务文件"
    echo ""
}

cmd_start() {
    echo "🚀 启动 VibeBridge..."
    systemctl --user start "$SERVICE_NAME"
    sleep 1
    systemctl --user status "$SERVICE_NAME" --no-pager
}

cmd_stop() {
    echo "🛑 停止 VibeBridge..."
    systemctl --user stop "$SERVICE_NAME"
    echo "✅ 已停止"
}

cmd_restart() {
    echo "🔄 重启 VibeBridge..."
    systemctl --user restart "$SERVICE_NAME"
    sleep 1
    systemctl --user status "$SERVICE_NAME" --no-pager
}

cmd_status() {
    systemctl --user status "$SERVICE_NAME" --no-pager
}

cmd_log() {
    echo "📋 查看日志 (Ctrl+C 退出)..."
    journalctl --user -u "$SERVICE_NAME" -f
}

cmd_health() {
    echo "🏥 健康检查..."
    response=$(curl -s "http://localhost:$PORT/health" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "✅ 服务正常"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    else
        echo "❌ 无法连接到 http://localhost:$PORT/health"
        echo "请检查服务是否运行: ./manage.sh status"
    fi
}

cmd_enable() {
    echo "🔌 启用开机自启..."
    systemctl --user enable "$SERVICE_NAME"
    echo "✅ 已启用"
}

cmd_disable() {
    echo "🔌 禁用开机自启..."
    systemctl --user disable "$SERVICE_NAME"
    echo "✅ 已禁用"
}

cmd_setup() {
    echo "⚙️ 安装 systemd user service..."
    mkdir -p ~/.config/systemd/user

    if [ -f "deploy/vibebridge.service" ]; then
        cp deploy/vibebridge.service ~/.config/systemd/user/
    else
        echo "❌ 未找到 deploy/vibebridge.service"
        exit 1
    fi

    # 修正 deploy 模板中的端口和路径
    sed -i "s|--port 8000|--port $PORT|g" ~/.config/systemd/user/vibebridge.service
    sed -i "s|/home/user/workspace/vibebridge|$(pwd)|g" ~/.config/systemd/user/vibebridge.service
    sed -i "s|/home/akliedrak/workspace/vibebridge|$(pwd)|g" ~/.config/systemd/user/vibebridge.service

    systemctl --user daemon-reload
    echo "✅ 安装完成"
    echo ""
    echo "下一步:"
    echo "  ./manage.sh start   # 启动服务"
    echo "  ./manage.sh enable  # 启用开机自启"
}

cmd_menu() {
    echo ""
    echo "╔══════════════════════════════════════╗"
    echo "║        VibeBridge 管理菜单          ║"
    echo "╚══════════════════════════════════════╝"
    echo ""
    echo "  1) 启动服务"
    echo "  2) 停止服务"
    echo "  3) 重启服务"
    echo "  4) 查看状态"
    echo "  5) 查看日志"
    echo "  6) 健康检查"
    echo "  7) 启用开机自启"
    echo "  8) 禁用开机自启"
    echo "  9) 安装 systemd 服务"
    echo "  0) 退出"
    echo ""
    read -p "请选择 [0-9]: " choice

    case $choice in
        1) cmd_start ;;
        2) cmd_stop ;;
        3) cmd_restart ;;
        4) cmd_status ;;
        5) cmd_log ;;
        6) cmd_health ;;
        7) cmd_enable ;;
        8) cmd_disable ;;
        9) cmd_setup ;;
        0) exit 0 ;;
        *) echo "❌ 无效选择" ;;
    esac
}

# 主逻辑
case "${1:-}" in
    start) cmd_start ;;
    stop) cmd_stop ;;
    restart) cmd_restart ;;
    status) cmd_status ;;
    log) cmd_log ;;
    health) cmd_health ;;
    enable) cmd_enable ;;
    disable) cmd_disable ;;
    setup) cmd_setup ;;
    -h|--help|help) show_help ;;
    "") cmd_menu ;;
    *) echo "❌ 未知命令: $1"; show_help; exit 1 ;;
esac
