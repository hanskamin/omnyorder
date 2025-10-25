#!/bin/bash
# Start Chrome with remote debugging for local browser MCP server

echo "🚀 Starting Chrome with Remote Debugging for Local Browser MCP Server"
echo "=" * 60

# Check if Chrome is already running
if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "✅ Chrome is already running with remote debugging on port 9222"
    echo "🌐 You can now connect remote agents to this MCP server"
    echo ""
    echo "📋 Next steps:"
    echo "1. Start the MCP server: python local_browser_mcp_server.py"
    echo "2. Connect your remote agent to this MCP server"
    echo "3. The agent can now control your local browser!"
    exit 0
fi

# Detect operating system
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    echo "🍎 Detected macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    CHROME_PATH="/usr/bin/google-chrome"
    echo "🐧 Detected Linux"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    # Windows
    CHROME_PATH="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    echo "🪟 Detected Windows"
else
    echo "❌ Unsupported operating system: $OSTYPE"
    exit 1
fi

# Check if Chrome exists
if [ ! -f "$CHROME_PATH" ]; then
    echo "❌ Chrome not found at: $CHROME_PATH"
    echo "Please install Google Chrome or update the path in this script"
    exit 1
fi

echo "🔍 Chrome found at: $CHROME_PATH"

# Start Chrome with remote debugging
echo "🚀 Starting Chrome with remote debugging on port 9222..."

"$CHROME_PATH" \
    --remote-debugging-port=9222 \
    --no-first-run \
    --no-default-browser-check \
    --disable-default-apps \
    --disable-popup-blocking \
    --disable-translate \
    --disable-background-timer-throttling \
    --disable-renderer-backgrounding \
    --disable-backgrounding-occluded-windows \
    --disable-client-side-phishing-detection \
    --disable-sync \
    --disable-features=TranslateUI \
    --disable-ipc-flooding-protection \
    --disable-hang-monitor \
    --disable-prompt-on-repost \
    --disable-domain-reliability \
    --disable-features=VizDisplayCompositor \
    --user-data-dir=/tmp/chrome-debug \
    > /dev/null 2>&1 &

# Wait for Chrome to start
echo "⏳ Waiting for Chrome to start..."
sleep 3

# Check if Chrome started successfully
if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "✅ Chrome started successfully with remote debugging!"
    echo "🌐 Remote debugging available at: http://localhost:9222"
    echo ""
    echo "📋 Next steps:"
    echo "1. Start the MCP server: python local_browser_mcp_server.py"
    echo "2. Connect your remote agent to this MCP server"
    echo "3. The agent can now control your local browser!"
    echo ""
    echo "🔧 To stop Chrome: pkill -f 'chrome.*remote-debugging-port=9222'"
else
    echo "❌ Failed to start Chrome with remote debugging"
    echo "Please check if Chrome is installed and try again"
    exit 1
fi
