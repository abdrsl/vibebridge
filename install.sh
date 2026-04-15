#!/bin/bash
set -e

echo "🚀 Installing VibeBridge..."

# Check Python version
python3 --version >/dev/null 2>&1 || { echo "❌ Python 3.10+ is required"; exit 1; }

PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo "❌ Python 3.10+ is required, found ${PY_MAJOR}.${PY_MINOR}"
    exit 1
fi

INSTALL_DIR="$HOME/.local/share/vibebridge"
REPO_DIR="$INSTALL_DIR/repo"
mkdir -p "$INSTALL_DIR"

# Clone or update
if [ -d "$REPO_DIR/.git" ]; then
    echo "📦 Updating existing installation..."
    cd "$REPO_DIR"
    git pull origin main
else
    echo "📦 Cloning repository..."
    # When published, this will point to the actual GitHub repo
    git clone https://github.com/akliedrak/vibebridge.git "$REPO_DIR" || {
        echo "⚠️  Clone failed. If the repo is not public yet, please clone manually to $REPO_DIR"
        exit 1
    }
fi

cd "$REPO_DIR"

# Create venv
if [ ! -d ".venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install package
echo "📥 Installing dependencies..."
pip install -e ".[dev]"

# Create symlink
mkdir -p "$HOME/.local/bin"
ln -sf "$REPO_DIR/.venv/bin/vibebridge" "$HOME/.local/bin/vibebridge"

# Ensure PATH includes ~/.local/bin
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo "⚠️  Please add $HOME/.local/bin to your PATH"
fi

echo ""
echo "✅ VibeBridge installed successfully!"
echo ""
echo "Next steps:"
echo "   1. Run 'vibebridge init' to configure"
echo "   2. Run 'vibebridge start' to launch"
echo "   3. Run 'vibebridge start --install' to enable auto-start"
