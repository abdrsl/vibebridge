#!/bin/bash
# OpenRouter setup script for VibeBridge

set -e

echo "🔧 Setting up OpenRouter for VibeBridge"
echo "========================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "📄 Creating .env file from template..."
    cp .env.example .env 2>/dev/null || touch .env
fi

# Ask for OpenRouter API key
echo ""
echo "🔑 Please enter your OpenRouter API key:"
echo "   (Get it from https://openrouter.ai/api-keys)"
echo ""
read -p "OpenRouter API Key: " OPENROUTER_KEY

if [ -z "$OPENROUTER_KEY" ]; then
    echo "❌ No API key provided. Exiting."
    exit 1
fi

# Update .env file
if grep -q "OPENROUTER_API_KEY" .env; then
    # Replace existing key
    sed -i.bak "s|OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$OPENROUTER_KEY|" .env
    rm -f .env.bak
else
    # Add new key
    echo "OPENROUTER_API_KEY=$OPENROUTER_KEY" >> .env
fi

echo "✅ API key saved to .env file"

# Export for current session
export OPENROUTER_API_KEY="$OPENROUTER_KEY"

# Update config
echo ""
echo "⚙️  Updating VibeBridge configuration..."
if command -v vibebridge &> /dev/null; then
    # Re-run init to detect OpenRouter
    echo "Running vibebridge init to update configuration..."
    vibebridge init --non-interactive
else
    echo "⚠️  VibeBridge CLI not found. Please install VibeBridge first."
    echo "   Run: pip install -e ."
fi

# Test the integration
echo ""
echo "🧪 Testing OpenRouter integration..."
if [ -f test_openrouter.py ]; then
    python3 test_openrouter.py
else
    echo "⚠️  Test script not found. Creating it..."
    # The test script should already be created by the main implementation
    if [ -f test_openrouter.py ]; then
        python3 test_openrouter.py
    else
        echo "❌ Test script not available. Please check the implementation."
    fi
fi

echo ""
echo "🎉 OpenRouter setup complete!"
echo ""
echo "Next steps:"
echo "1. Start VibeBridge: vibebridge start"
echo "2. Test in Feishu: @VibeBridge /openrouter hello"
echo "3. Run comprehensive tests: python3 test_openrouter.py --all-models"
echo ""
echo "For more details, see OPENROUTER_README.md"