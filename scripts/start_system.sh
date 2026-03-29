#!/bin/bash
# Start system script for AI Product Lab
# Starts FastAPI server and tunnel manager

set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_ROOT="$PWD"
VENV_PATH="$PROJECT_ROOT/.venv"
LOG_DIR="$PROJECT_ROOT/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    error "Virtual environment not found at $VENV_PATH"
    error "Please create it with: python -m venv .venv"
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Kill existing processes
stop_system() {
    info "Stopping existing processes..."
    
    # Kill uvicorn processes
    pkill -f "uvicorn src.main:app" 2>/dev/null || true
    # Kill tunnel processes
    pkill -f "ssh.*serveo.net" 2>/dev/null || true
    # Kill tunnel manager
    pkill -f "tunnel_manager.py" 2>/dev/null || true
    
    sleep 2
    info "Stopped all processes"
}

# Check if system is already running
check_running() {
    if pgrep -f "uvicorn src.main:app" > /dev/null; then
        echo "server"
    fi
    if pgrep -f "ssh.*serveo.net" > /dev/null; then
        echo "tunnel"
    fi
}

case "${1:-start}" in
    start)
        # Check if already running
        running=$(check_running)
        if [ -n "$running" ]; then
            warn "System is already running: $running"
            read -p "Restart? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                stop_system
            else
                info "Exiting"
                exit 0
            fi
        fi
        
        info "Starting AI Product Lab system..."
        
        # Start FastAPI server
        info "Starting FastAPI server..."
        nohup python -m uvicorn src.main:app \
            --host 0.0.0.0 \
            --port 8000 \
            > "$LOG_DIR/server.log" 2>&1 &
        SERVER_PID=$!
        info "Server started with PID: $SERVER_PID"
        
        # Wait a moment for server to start
        sleep 3
        
        # Check if server is healthy
        if curl -s http://localhost:8000/health > /dev/null; then
            info "✅ Server is healthy"
        else
            error "❌ Server failed to start, check $LOG_DIR/server.log"
            exit 1
        fi
        
        # Start tunnel manager
        info "Starting tunnel manager..."
        nohup python -m src.legacy.tunnel_manager \
            > "$LOG_DIR/tunnel_manager.log" 2>&1 &
        TUNNEL_MANAGER_PID=$!
        info "Tunnel manager started with PID: $TUNNEL_MANAGER_PID"
        
        info ""
        info "========================================"
        info "✅ System started successfully!"
        info "========================================"
        info ""
        info "📊 Monitoring:"
        info "  - Server logs: tail -f $LOG_DIR/server.log"
        info "  - Tunnel logs: tail -f $LOG_DIR/tunnel.log"
        info "  - Tunnel manager: tail -f $LOG_DIR/tunnel_manager.log"
        info ""
        info "🔄 To restart: $0 restart"
        info "🛑 To stop: $0 stop"
        info ""
        ;;
    
    stop)
        stop_system
        ;;
    
    restart)
        stop_system
        sleep 2
        exec "$0" start
        ;;
    
    status)
        info "System status:"
        if pgrep -f "uvicorn src.main:app" > /dev/null; then
            info "✅ Server: RUNNING"
        else
            info "❌ Server: STOPPED"
        fi
        
        if pgrep -f "ssh.*serveo.net" > /dev/null; then
            info "✅ Tunnel: RUNNING"
        else
            info "❌ Tunnel: STOPPED"
        fi
        
        if pgrep -f "tunnel_manager.py" > /dev/null; then
            info "✅ Tunnel manager: RUNNING"
        else
            info "❌ Tunnel manager: STOPPED"
        fi
        
        # Show tunnel URL if available
        if [ -f "$LOG_DIR/last_tunnel_url.txt" ]; then
            CURRENT_URL=$(cat "$LOG_DIR/last_tunnel_url.txt")
            info "🌐 Current tunnel URL: $CURRENT_URL"
        fi
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac