#!/bin/bash

# 运行 openclaw gateway 并记录日志的脚本
# 作者: opencode

set -e  # 遇到错误立即退出
set -o pipefail  # 管道命令中任何错误都会导致脚本退出

# 配置变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
LOG_DIR="$PROJECT_ROOT/logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/openclaw_gateway_${TIMESTAMP}.log"
PID_FILE="$LOG_DIR/openclaw_gateway.pid"
MAX_RETRIES=3
RETRY_DELAY=5

# 创建日志目录
mkdir -p "$LOG_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 检查 openclaw 是否安装
check_openclaw() {
    if ! command -v openclaw &> /dev/null; then
        log_error "openclaw 命令未找到，请确保已安装 OpenClaw"
        log_info "安装方法: npm install -g @openclaw/cli"
        exit 1
    fi
    
    log_info "OpenClaw 版本: $(openclaw --version 2>/dev/null || echo '未知')"
}

# 检查端口是否被占用
check_port() {
    local port=${1:-19000}
    
    if command -v lsof &> /dev/null; then
        if lsof -ti:"$port" &> /dev/null; then
            log_warn "端口 $port 已被占用"
            lsof -ti:"$port" | xargs kill -9 2>/dev/null || true
            log_info "已终止占用端口 $port 的进程"
            sleep 2
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tuln | grep ":$port " &> /dev/null; then
            log_warn "端口 $port 已被占用"
            # 尝试查找并终止进程
            if command -v fuser &> /dev/null; then
                fuser -k "$port/tcp" 2>/dev/null || true
            fi
            sleep 2
        fi
    fi
}

# 清理之前的进程
cleanup_previous() {
    if [ -f "$PID_FILE" ]; then
        local old_pid=$(cat "$PID_FILE")
        if kill -0 "$old_pid" 2>/dev/null; then
            log_warn "发现之前运行的进程 (PID: $old_pid)，正在终止..."
            kill -9 "$old_pid" 2>/dev/null || true
            sleep 2
        fi
        rm -f "$PID_FILE"
    fi
}

# 运行 openclaw gateway
run_gateway() {
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log_info "尝试运行 openclaw gateway (第 $attempt 次尝试)..."
        
        # 检查端口
        check_port 19000
        
        # 运行命令
        log_info "开始记录日志到: $LOG_FILE"
        log_info "运行命令: openclaw gateway run --log-level=debug"
        
        # 使用 nohup 在后台运行并记录日志
        nohup openclaw gateway run --log-level=debug > "$LOG_FILE" 2>&1 &
        local pid=$!
        
        echo "$pid" > "$PID_FILE"
        log_info "OpenClaw Gateway 已启动 (PID: $pid)"
        
        # 等待进程启动
        sleep 5
        
        # 检查进程是否仍在运行
        if ! kill -0 "$pid" 2>/dev/null; then
            log_error "进程已退出，检查日志文件: $LOG_FILE"
            attempt=$((attempt + 1))
            
            if [ $attempt -le $MAX_RETRIES ]; then
                log_info "等待 $RETRY_DELAY 秒后重试..."
                sleep $RETRY_DELAY
            fi
            continue
        fi
        
        # 检查网关是否响应
        if check_gateway_health; then
            log_success "OpenClaw Gateway 运行成功！"
            log_info "PID: $pid"
            log_info "日志文件: $LOG_FILE"
            return 0
        else
            log_warn "网关启动但健康检查失败，等待更多时间..."
            sleep 10
            
            if check_gateway_health; then
                log_success "OpenClaw Gateway 运行成功！"
                log_info "PID: $pid"
                log_info "日志文件: $LOG_FILE"
                return 0
            else
                log_error "网关健康检查失败"
                kill -9 "$pid" 2>/dev/null || true
                attempt=$((attempt + 1))
                
                if [ $attempt -le $MAX_RETRIES ]; then
                    log_info "等待 $RETRY_DELAY 秒后重试..."
                    sleep $RETRY_DELAY
                fi
            fi
        fi
    done
    
    log_error "经过 $MAX_RETRIES 次尝试后仍无法启动 OpenClaw Gateway"
    return 1
}

# 检查网关健康状态
check_gateway_health() {
    log_info "检查网关健康状态..."
    
    # 尝试使用 openclaw health 命令
    if timeout 10 openclaw health --json 2>/dev/null | grep -q "healthy"; then
        log_info "网关健康检查通过"
        return 0
    fi
    
    # 尝试 curl 检查
    if command -v curl &> /dev/null; then
        if curl -s http://localhost:19000/health 2>/dev/null | grep -q "healthy"; then
            log_info "网关健康检查通过 (通过 HTTP)"
            return 0
        fi
    fi
    
    # 检查日志中是否有成功启动的迹象
    if tail -n 20 "$LOG_FILE" 2>/dev/null | grep -q "Gateway.*started\|listening\|ready"; then
        log_info "从日志检测到网关已启动"
        return 0
    fi
    
    return 1
}

# 分析日志文件
analyze_logs() {
    log_info "开始分析日志文件: $LOG_FILE"
    
    if [ ! -f "$LOG_FILE" ] || [ ! -s "$LOG_FILE" ]; then
        log_error "日志文件不存在或为空"
        return 1
    fi
    
    echo ""
    echo "="*80
    echo "日志分析报告"
    echo "="*80
    echo ""
    
    # 1. 检查错误
    echo "1. 错误检查:"
    echo "-"*40
    local error_count=$(grep -c -i "error\|failed\|exception\|crash\|panic\|segmentation fault" "$LOG_FILE")
    if [ "$error_count" -gt 0 ]; then
        echo "发现 $error_count 个错误/异常:"
        grep -n -i "error\|failed\|exception\|crash\|panic\|segmentation fault" "$LOG_FILE" | head -20
    else
        echo "未发现明显的错误信息"
    fi
    echo ""
    
    # 2. 检查警告
    echo "2. 警告检查:"
    echo "-"*40
    local warn_count=$(grep -c -i "warn\|warning" "$LOG_FILE")
    if [ "$warn_count" -gt 0 ]; then
        echo "发现 $warn_count 个警告:"
        grep -n -i "warn\|warning" "$LOG_FILE" | head -20
    else
        echo "未发现警告信息"
    fi
    echo ""
    
    # 3. 检查启动过程
    echo "3. 启动过程检查:"
    echo "-"*40
    echo "最后 10 行启动日志:"
    tail -n 10 "$LOG_FILE"
    echo ""
    
    # 4. 检查退出代码相关
    echo "4. 退出代码检查:"
    echo "-"*40
    if grep -q "exited with code\|exit code\|exit status" "$LOG_FILE"; then
        echo "发现退出代码信息:"
        grep -n "exited with code\|exit code\|exit status" "$LOG_FILE"
    else
        echo "未发现明确的退出代码信息"
    fi
    echo ""
    
    # 5. 检查内存/资源问题
    echo "5. 内存和资源检查:"
    echo "-"*40
    if grep -q -i "memory\|oom\|out of memory\|heap\|gc\|garbage collection" "$LOG_FILE"; then
        echo "发现内存相关日志:"
        grep -n -i "memory\|oom\|out of memory\|heap\|gc\|garbage collection" "$LOG_FILE" | head -10
    else
        echo "未发现内存相关问题"
    fi
    echo ""
    
    # 6. 检查网络/连接问题
    echo "6. 网络和连接检查:"
    echo "-"*40
    if grep -q -i "connection\|socket\|timeout\|refused\|network\|port" "$LOG_FILE"; then
        echo "发现网络相关日志:"
        grep -n -i "connection\|socket\|timeout\|refused\|network\|port" "$LOG_FILE" | head -10
    else
        echo "未发现网络连接问题"
    fi
    echo ""
    
    # 7. 检查配置问题
    echo "7. 配置检查:"
    echo "-"*40
    if grep -q -i "config\|configuration\|env\|environment\|missing\|not found" "$LOG_FILE"; then
        echo "发现配置相关日志:"
        grep -n -i "config\|configuration\|env\|environment\|missing\|not found" "$LOG_FILE" | head -10
    else
        echo "未发现配置问题"
    fi
    echo ""
    
    # 8. 统计信息
    echo "8. 日志统计:"
    echo "-"*40
    local total_lines=$(wc -l < "$LOG_FILE")
    local error_lines=$(grep -c -i "error" "$LOG_FILE")
    local warn_lines=$(grep -c -i "warn" "$LOG_FILE")
    local info_lines=$(grep -c -i "info" "$LOG_FILE")
    
    echo "总行数: $total_lines"
    echo "错误行数: $error_lines"
    echo "警告行数: $warn_lines"
    echo "信息行数: $info_lines"
    echo ""
    
    # 9. 建议
    echo "9. 建议:"
    echo "-"*40
    if [ "$error_count" -gt 0 ]; then
        echo "⚠️  发现错误，请检查上面的错误信息"
        echo "   建议: 根据错误信息修复问题后重试"
    elif [ "$warn_count" -gt 0 ]; then
        echo "⚠️  发现警告，但可能不影响运行"
        echo "   建议: 检查警告信息，确认是否需要处理"
    else
        echo "✅ 日志看起来正常，没有发现明显问题"
        echo "   建议: 如果仍有问题，请检查系统资源或联系支持"
    fi
    echo ""
    
    echo "="*80
}

# 主函数
main() {
    log_info "开始运行 OpenClaw Gateway 监控脚本"
    log_info "项目目录: $PROJECT_ROOT"
    log_info "日志目录: $LOG_DIR"
    
    # 检查依赖
    check_openclaw
    
    # 清理之前的进程
    cleanup_previous
    
    # 运行网关
    if run_gateway; then
        # 等待一段时间让日志积累
        log_info "等待 10 秒收集日志..."
        sleep 10
        
        # 分析日志
        analyze_logs
        
        log_info "脚本执行完成"
        log_info "网关仍在后台运行，PID: $(cat "$PID_FILE" 2>/dev/null || echo '未知')"
        log_info "要停止网关，请运行: kill \$(cat $PID_FILE)"
        log_info "要查看实时日志，请运行: tail -f $LOG_FILE"
    else
        log_error "网关启动失败"
        analyze_logs
        exit 1
    fi
}

# 信号处理
trap 'log_warn "收到中断信号，正在清理..."; cleanup_previous; exit 0' INT TERM

# 执行主函数
main "$@"