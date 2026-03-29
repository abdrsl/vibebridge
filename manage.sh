#!/bin/bash
#
# AI Project Lab 用户级自动启动脚本
# 无需root权限，使用nohup实现后台运行

PROJECT_DIR="/home/user/workspace/ai-project"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$LOG_DIR/pids"

# 创建必要的目录
mkdir -p "$LOG_DIR" "$PID_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查服务器是否运行
check_server() {
    if curl -s "http://127.0.0.1:8000/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 启动服务器
start_server() {
    if check_server; then
        log_info "服务器已经在运行"
        return 0
    fi
    
    log_info "启动服务器..."
    cd "$PROJECT_DIR"
    source .venv/bin/activate
    
    nohup python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/server.log" 2>&1 &
    echo $! > "$PID_DIR/server.pid"
    
    # 等待服务器启动
    for i in {1..10}; do
        if check_server; then
            log_info "✅ 服务器启动成功 (PID: $(cat $PID_DIR/server.pid))"
            return 0
        fi
        sleep 1
    done
    
    log_error "❌ 服务器启动失败"
    return 1
}

# 停止服务器
stop_server() {
    if [ -f "$PID_DIR/server.pid" ]; then
        local pid=$(cat "$PID_DIR/server.pid")
        if kill -0 $pid 2>/dev/null; then
            log_info "停止服务器 (PID: $pid)..."
            kill $pid
            rm "$PID_DIR/server.pid"
            sleep 2
        fi
    fi
    
    # 确保所有uvicorn进程都被停止
    pkill -f "uvicorn src.main:app" 2>/dev/null
    log_info "✅ 服务器已停止"
}

# 检查隧道状态
check_tunnel() {
    if [ -f "$LOG_DIR/current_tunnel_url.txt" ]; then
        local url=$(cat "$LOG_DIR/current_tunnel_url.txt")
        if curl -s --max-time 5 "$url/health" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# 启动隧道
start_tunnel() {
    if check_tunnel; then
        local url=$(cat "$LOG_DIR/current_tunnel_url.txt")
        log_info "隧道已经可用: $url"
        return 0
    fi
    
    log_info "启动隧道..."
    
    # 尝试ngrok
    if command -v ngrok &> /dev/null; then
        log_info "尝试启动 ngrok..."
        pkill -f ngrok 2>/dev/null
        sleep 1
        
        cd "$PROJECT_DIR"
        nohup ngrok http 8000 --pooling-enabled > "$LOG_DIR/ngrok.log" 2>&1 &
        echo $! > "$PID_DIR/tunnel.pid"
        
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
        
        if [ -n "$url" ]; then
            echo "$url" > "$LOG_DIR/current_tunnel_url.txt"
            echo "ngrok" > "$LOG_DIR/current_tunnel_type.txt"
            log_info "✅ ngrok 启动成功"
            log_info "🌐 URL: $url"
            log_info "🔗 Webhook: $url/feishu/webhook/opencode"
            return 0
        fi
    fi
    
    # 尝试localtunnel
    if command -v lt &> /dev/null; then
        log_info "尝试启动 localtunnel..."
        pkill -f "lt --port" 2>/dev/null
        sleep 1
        
        cd "$PROJECT_DIR"
        nohup lt --port 8000 > "$LOG_DIR/localtunnel.log" 2>&1 &
        echo $! > "$PID_DIR/tunnel.pid"
        
        sleep 6
        
        local url=$(tail -5 "$LOG_DIR/localtunnel.log" | grep -oE "https://[a-z0-9-]+\.loca\.lt" | tail -1)
        
        if [ -n "$url" ]; then
            echo "$url" > "$LOG_DIR/current_tunnel_url.txt"
            echo "localtunnel" > "$LOG_DIR/current_tunnel_type.txt"
            log_info "✅ localtunnel 启动成功"
            log_info "🌐 URL: $url"
            log_info "🔗 Webhook: $url/feishu/webhook/opencode"
            return 0
        fi
    fi
    
    log_warn "⚠️  无法启动任何隧道"
    log_warn "   服务器只能在本地访问"
    return 1
}

# 停止隧道
stop_tunnel() {
    if [ -f "$PID_DIR/tunnel.pid" ]; then
        local pid=$(cat "$PID_DIR/tunnel.pid")
        if kill -0 $pid 2>/dev/null; then
            log_info "停止隧道 (PID: $pid)..."
            kill $pid 2>/dev/null
        fi
        rm "$PID_DIR/tunnel.pid" 2>/dev/null
    fi
    
    pkill -f ngrok 2>/dev/null
    pkill -f "lt --port" 2>/dev/null
    
    rm -f "$LOG_DIR/current_tunnel_url.txt"
    rm -f "$LOG_DIR/current_tunnel_type.txt"
    
    log_info "✅ 隧道已停止"
}

# 显示状态
show_status() {
    echo "=========================================="
    echo "AI Project Lab 状态"
    echo "=========================================="
    echo ""
    
    # 服务器状态
    if check_server; then
        echo -e "${GREEN}✅ 服务器${NC}: 运行中"
        if [ -f "$PID_DIR/server.pid" ]; then
            echo "   PID: $(cat $PID_DIR/server.pid)"
        fi
        echo "   地址: http://127.0.0.1:8000"
    else
        echo -e "${RED}❌ 服务器${NC}: 未运行"
    fi
    
    echo ""
    
    # 隧道状态
    if check_tunnel; then
        local url=$(cat "$LOG_DIR/current_tunnel_url.txt")
        local type=$(cat "$LOG_DIR/current_tunnel_type.txt" 2>/dev/null || echo "unknown")
        echo -e "${GREEN}✅ 公网隧道${NC}: 可用 ($type)"
        echo "   URL: $url"
        echo "   Webhook: $url/feishu/webhook/opencode"
    else
        echo -e "${YELLOW}⚠️  公网隧道${NC}: 未配置或不可用"
    fi
    
    echo ""
    echo "=========================================="
}

# 重启服务
restart() {
    log_info "重启服务..."
    stop_tunnel
    stop_server
    sleep 2
    start_server && start_tunnel
}

# 主菜单
show_menu() {
    echo ""
    echo "=========================================="
    echo "AI Project Lab 管理菜单"
    echo "=========================================="
    echo ""
    echo "1) 启动服务"
    echo "2) 停止服务"
    echo "3) 重启服务"
    echo "4) 查看状态"
    echo "5) 查看日志"
    echo "6) 仅启动隧道"
    echo "7) 停止隧道"
    echo "0) 退出"
    echo ""
    echo -n "请选择 [0-7]: "
}

# 查看日志
view_logs() {
    echo ""
    echo "选择日志:"
    echo "1) 服务器日志"
    echo "2) 隧道日志"
    echo "3) 自动恢复日志"
    echo -n "请选择 [1-3]: "
    read choice
    
    case $choice in
        1) tail -f "$LOG_DIR/server.log" ;;
        2) 
            if [ -f "$LOG_DIR/current_tunnel_type.txt" ]; then
                local type=$(cat "$LOG_DIR/current_tunnel_type.txt")
                tail -f "$LOG_DIR/$type.log"
            else
                log_warn "没有可用的隧道日志"
            fi
            ;;
        3) tail -f "$LOG_DIR/auto_recovery.log" 2>/dev/null || log_warn "没有自动恢复日志" ;;
    esac
}

# 主程序
case "${1:-menu}" in
    start)
        start_server && start_tunnel
        show_status
        ;;
    stop)
        stop_tunnel
        stop_server
        ;;
    restart)
        restart
        show_status
        ;;
    status)
        show_status
        ;;
    tunnel)
        start_tunnel
        ;;
    stop-tunnel)
        stop_tunnel
        ;;
    menu|--menu|-m|"")
        while true; do
            show_menu
            read choice
            case $choice in
                1) start_server && start_tunnel ;;
                2) stop_tunnel; stop_server ;;
                3) restart ;;
                4) show_status ;;
                5) view_logs ;;
                6) start_tunnel ;;
                7) stop_tunnel ;;
                0) exit 0 ;;
                *) log_warn "无效的选择" ;;
            esac
            echo ""
            read -p "按回车键继续..."
        done
        ;;
    *)
        echo "用法: $0 [start|stop|restart|status|tunnel|stop-tunnel|menu]"
        exit 1
        ;;
esac