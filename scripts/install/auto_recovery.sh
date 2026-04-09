#!/bin/bash
#
# OpenCode-Feishu Bridge 自动监控和恢复脚本
# 功能:
# 1. 监控服务器状态，停止时自动重启
# 2. 监控隧道状态，不可用时自动切换
# 3. 记录日志

# 配置
PROJECT_DIR="/home/user/workspace/opencode-feishu-bridge"
LOG_FILE="$PROJECT_DIR/logs/auto_recovery.log"
PID_FILE="$PROJECT_DIR/logs/auto_recovery.pid"
SERVER_PORT=8000
TUNNEL_CHECK_TIMEOUT=10

# 隧道配置（按优先级排序）
TUNNEL_PRIORITY=("ngrok" "localtunnel" "expose")
CURRENT_TUNNEL_FILE="$PROJECT_DIR/logs/current_tunnel.txt"
CURRENT_URL_FILE="$PROJECT_DIR/logs/current_tunnel_url.txt"

# 确保日志目录存在
mkdir -p "$PROJECT_DIR/logs"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查服务器状态
check_server() {
    if curl -s "http://127.0.0.1:$SERVER_PORT/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 启动服务器
start_server() {
    log "启动服务器..."
    cd "$PROJECT_DIR"
    source .venv/bin/activate
    nohup python -m uvicorn src.main:app --host 0.0.0.0 --port $SERVER_PORT > "$PROJECT_DIR/logs/server.log" 2>&1 &
    sleep 5
    
    if check_server; then
        log "✅ 服务器启动成功 (PID: $(pgrep -f 'uvicorn src.main:app' | head -1))"
        return 0
    else
        log "❌ 服务器启动失败"
        return 1
    fi
}

# 停止服务器
stop_server() {
    log "停止服务器..."
    pkill -f "uvicorn src.main:app" 2>/dev/null
    sleep 2
}

# 检查隧道状态
check_tunnel() {
    local url=$1
    if [ -z "$url" ]; then
        return 1
    fi
    
    # 检查是否能访问
    if curl -s --max-time $TUNNEL_CHECK_TIMEOUT "$url/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 获取当前隧道URL
get_current_tunnel_url() {
    if [ -f "$CURRENT_URL_FILE" ]; then
        cat "$CURRENT_URL_FILE"
    else
        echo ""
    fi
}

# 保存当前隧道信息
save_tunnel_info() {
    local tunnel_type=$1
    local url=$2
    echo "$tunnel_type" > "$CURRENT_TUNNEL_FILE"
    echo "$url" > "$CURRENT_URL_FILE"
    log "保存隧道信息: $tunnel_type -> $url"
}

# 停止所有隧道
stop_all_tunnels() {
    log "停止所有隧道..."
    pkill -f "ngrok" 2>/dev/null
    pkill -f "localtunnel" 2>/dev/null
    pkill -f "expose" 2>/dev/null
    pkill -f "lt --port" 2>/dev/null
    sleep 2
}

# 启动ngrok
start_ngrok() {
    log "尝试启动 ngrok..."
    
    # 检查ngrok是否安装
    if ! command -v ngrok &> /dev/null; then
        log "❌ ngrok 未安装"
        return 1
    fi
    
    # 停止其他隧道
    stop_all_tunnels
    
    # 启动ngrok
    cd "$PROJECT_DIR"
    nohup ngrok http $SERVER_PORT > "$PROJECT_DIR/logs/ngrok.log" 2>&1 &
    sleep 8
    
    # 获取URL
    local url=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    for t in tunnels:
        url = t.get('public_url', '')
        if url and 'http' in url:
            print(url)
            break
except:
    pass
")
    
    if [ -n "$url" ] && check_tunnel "$url"; then
        save_tunnel_info "ngrok" "$url"
        log "✅ ngrok 启动成功: $url"
        return 0
    else
        log "❌ ngrok 启动失败或不可用"
        return 1
    fi
}

# 启动localtunnel
start_localtunnel() {
    log "尝试启动 localtunnel..."
    
    # 检查localtunnel是否安装
    if ! command -v lt &> /dev/null; then
        log "❌ localtunnel 未安装"
        return 1
    fi
    
    # 停止其他隧道
    stop_all_tunnels
    
    # 启动localtunnel
    cd "$PROJECT_DIR"
    nohup lt --port $SERVER_PORT > "$PROJECT_DIR/logs/localtunnel.log" 2>&1 &
    sleep 6
    
    # 获取URL
    local url=$(tail -5 "$PROJECT_DIR/logs/localtunnel.log" | grep -oE "https://[a-z0-9-]+\.loca\.lt" | tail -1)
    
    if [ -n "$url" ] && check_tunnel "$url"; then
        save_tunnel_info "localtunnel" "$url"
        log "✅ localtunnel 启动成功: $url"
        return 0
    else
        log "❌ localtunnel 启动失败或不可用"
        return 1
    fi
}

# 启动expose
start_expose() {
    log "尝试启动 expose..."
    
    # 检查expose是否安装
    if ! command -v expose &> /dev/null; then
        log "❌ expose 未安装，尝试安装..."
        npm install -g expose 2>&1 | tail -5
        if ! command -v expose &> /dev/null; then
            log "❌ expose 安装失败"
            return 1
        fi
    fi
    
    # 停止其他隧道
    stop_all_tunnels
    
    # 启动expose
    cd "$PROJECT_DIR"
    nohup expose $SERVER_PORT > "$PROJECT_DIR/logs/expose.log" 2>&1 &
    sleep 6
    
    # 获取URL (expose通常输出到控制台)
    local url=$(tail -10 "$PROJECT_DIR/logs/expose.log" | grep -oE "https://[a-z0-9-]+\.expose\.dev" | tail -1)
    
    if [ -n "$url" ] && check_tunnel "$url"; then
        save_tunnel_info "expose" "$url"
        log "✅ expose 启动成功: $url"
        return 0
    else
        log "❌ expose 启动失败或不可用"
        return 1
    fi
}

# 自动选择并启动最佳隧道
start_best_tunnel() {
    log "寻找最佳隧道..."
    
    # 首先检查当前隧道是否还可用
    local current_url=$(get_current_tunnel_url)
    if [ -n "$current_url" ]; then
        log "检查当前隧道: $current_url"
        if check_tunnel "$current_url"; then
            log "✅ 当前隧道仍然可用"
            return 0
        else
            log "⚠️ 当前隧道不可用，需要切换"
        fi
    fi
    
    # 按优先级尝试启动隧道
    for tunnel in "${TUNNEL_PRIORITY[@]}"; do
        case $tunnel in
            "ngrok")
                if start_ngrok; then
                    return 0
                fi
                ;;
            "localtunnel")
                if start_localtunnel; then
                    return 0
                fi
                ;;
            "expose")
                if start_expose; then
                    return 0
                fi
                ;;
        esac
    done
    
    log "❌ 所有隧道都不可用"
    return 1
}

# 主监控循环
monitor() {
    log "=========================================="
    log "启动自动监控服务"
    log "=========================================="
    
    # 检查服务器
    if ! check_server; then
        log "⚠️  服务器未运行，正在启动..."
        if ! start_server; then
            log "❌ 服务器启动失败，退出监控"
            return 1
        fi
    else
        log "✅ 服务器运行正常"
    fi
    
    # 检查隧道
    if ! start_best_tunnel; then
        log "⚠️  警告：没有可用的公网隧道"
        log "   服务器只能在本地访问"
    fi
    
    # 输出当前状态
    log ""
    log "📊 当前状态:"
    log "   服务器: http://127.0.0.1:$SERVER_PORT"
    local current_url=$(get_current_tunnel_url)
    if [ -n "$current_url" ]; then
        log "   公网URL: $current_url"
        log "   Webhook: $current_url/feishu/webhook/opencode"
    else
        log "   公网URL: 不可用"
    fi
    log ""
}

# 持续监控模式
continuous_monitor() {
    log "=========================================="
    log "持续监控模式 (每30秒检查一次)"
    log "=========================================="
    
    # 保存PID
    echo $$ > "$PID_FILE"
    
    while true; do
        # 检查服务器
        if ! check_server; then
            log "⚠️  服务器停止，正在重启..."
            start_server
            
            # 服务器重启后，隧道可能也需要重启
            sleep 3
            start_best_tunnel
        fi
        
        # 检查隧道（每3次循环检查一次）
        if [ $(($(date +%s) % 90)) -lt 30 ]; then
            local current_url=$(get_current_tunnel_url)
            if [ -n "$current_url" ]; then
                if ! check_tunnel "$current_url"; then
                    log "⚠️  隧道不可用，正在切换..."
                    start_best_tunnel
                fi
            else
                # 没有隧道，尝试启动
                start_best_tunnel
            fi
        fi
        
        sleep 30
    done
}

# 停止监控
stop_monitor() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 $pid 2>/dev/null; then
            log "停止监控进程 (PID: $pid)..."
            kill $pid
            rm "$PID_FILE"
        else
            log "监控进程未运行"
        fi
    else
        log "未找到监控进程"
    fi
}

# 状态检查
show_status() {
    echo "=========================================="
    echo "系统状态检查"
    echo "=========================================="
    echo ""
    
    # 检查服务器
    if check_server; then
        echo "✅ 服务器: 运行中"
        echo "   地址: http://127.0.0.1:$SERVER_PORT"
        local pid=$(pgrep -f "uvicorn src.main:app" | head -1)
        echo "   PID: $pid"
    else
        echo "❌ 服务器: 未运行"
    fi
    
    echo ""
    
    # 检查隧道
    local current_url=$(get_current_tunnel_url)
    if [ -n "$current_url" ]; then
        echo "🌐 公网隧道:"
        echo "   URL: $current_url"
        if check_tunnel "$current_url"; then
            echo "   状态: ✅ 可用"
        else
            echo "   状态: ❌ 不可用"
        fi
        echo "   Webhook: $current_url/feishu/webhook/opencode"
    else
        echo "🌐 公网隧道: 未配置"
    fi
    
    echo ""
    
    # 检查监控进程
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 $pid 2>/dev/null; then
            echo "👁️  监控进程: 运行中 (PID: $pid)"
        else
            echo "👁️  监控进程: 未运行"
        fi
    else
        echo "👁️  监控进程: 未启动"
    fi
    
    echo ""
    echo "=========================================="
}

# 显示帮助
show_help() {
    echo "OpenCode-Feishu Bridge 自动监控脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start       启动一次监控和恢复"
    echo "  daemon      启动持续监控（后台运行）"
    echo "  foreground  启动持续监控（前台运行）"
    echo "  stop        停止持续监控"
    echo "  status      显示当前状态"
    echo "  restart     重启服务器和隧道"
    echo "  tunnel      仅重启隧道"
    echo "  help        显示此帮助"
    echo ""
    echo "示例:"
    echo "  $0 start    # 启动一次检查"
    echo "  $0 daemon   # 后台持续监控"
    echo "  $0 status   # 查看状态"
}

# 主程序
case "${1:-start}" in
    start)
        monitor
        ;;
    daemon)
        continuous_monitor &
        log "监控进程已后台启动 (PID: $!)"
        ;;
    foreground)
        continuous_monitor
        ;;
    stop)
        stop_monitor
        ;;
    status)
        show_status
        ;;
    restart)
        log "重启服务器和隧道..."
        stop_server
        stop_all_tunnels
        sleep 2
        monitor
        ;;
    tunnel)
        log "仅重启隧道..."
        start_best_tunnel
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "未知命令: $1"
        show_help
        exit 1
        ;;
esac