#!/bin/bash

echo "🚀 Setting up Browser-Use Shopping Automation"
echo "=============================================="

# Check if Python 3.12+ is available
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.12"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.12+ is required. Current version: $python_version"
    echo "Please install Python 3.12 or later"
    exit 1
fi

echo "✅ Python version: $python_version"

# Install dependencies
echo "📦 Installing dependencies..."
uv add browser-use fastapi uvicorn pydantic langchain-openai

# Verify browser-use installation
echo "🔍 Verifying browser-use installation..."
uv run python -c "from browser_use import Agent, Browser; from langchain_openai import ChatOpenAI; print('✅ browser-use installed successfully!')"

if [ $? -eq 0 ]; then
    echo "✅ All dependencies installed successfully!"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Check for API keys
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  OPENAI_API_KEY environment variable not set"
    echo "Please set your OpenAI API key:"
    echo "export OPENAI_API_KEY='your-openai-api-key-here'"
    echo ""
    echo "Or create a setup_key.sh file with:"
    echo "export BROWSER_USE_API_KEY='your-api-key-here'"
else
    echo "✅ OpenAI API key is set"
fi

if [ -z "$BROWSER_USE_API_KEY" ]; then
    echo "⚠️  BROWSER_USE_API_KEY environment variable not set (optional)"
    echo "This is only needed if you want to use browser-use's cloud services"
else
    echo "✅ Browser-use API key is set"
fi

# Check for Chrome debugging
echo "🌐 Checking Chrome setup..."
if pgrep -f "remote-debugging-port=9222" > /dev/null; then
    echo "✅ Chrome debugging is enabled"
else
    echo "⚠️  Chrome debugging not detected"
    echo "Please start Chrome with debugging:"
    echo "google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug"
fi

echo ""
echo "🎉 Setup complete! You can now start the server:"
echo "python3 simple_api_server.py"
echo ""
echo "📚 API documentation will be available at: http://localhost:8000/docs"
