# Local Browser MCP Server Guide

## 🌐 **Local Browser + Remote Agent Architecture**

This guide shows you how to deploy an MCP server that controls your local browser while being called by agents running elsewhere.

## 🏗️ **Architecture Overview**

```
Remote Agent (elsewhere) → MCP Server (your machine) → Local Browser (your machine)
```

- **Remote Agent**: Runs on a different machine/cloud
- **MCP Server**: Runs on your local machine
- **Local Browser**: Chrome with remote debugging on your machine

## 🚀 **Quick Setup**

### **Step 1: Start Local Browser**
```bash
# Start Chrome with remote debugging
./start_local_browser.sh
```

### **Step 2: Start MCP Server**
```bash
# Start the local browser MCP server
python local_browser_mcp_server.py
```

### **Step 3: Connect Remote Agent**
Configure your remote agent to connect to your MCP server.

## 📋 **Detailed Setup**

### **Option 1: Local Browser + MCP Server (Recommended)**

#### **1. Start Chrome with Remote Debugging**
```bash
# Run the setup script
./start_local_browser.sh

# Or manually start Chrome
chrome --remote-debugging-port=9222 \
       --no-first-run \
       --no-default-browser-check \
       --disable-default-apps \
       --disable-popup-blocking \
       --user-data-dir=/tmp/chrome-debug
```

#### **2. Start MCP Server**
```bash
# Start the MCP server
python local_browser_mcp_server.py

# Or with specific configuration
python local_browser_mcp_server.py --config local_mcp_config.json
```

#### **3. Configure Remote Agent**
Your remote agent needs to connect to your MCP server. The connection can be:

- **HTTP/WebSocket**: If you expose the MCP server over HTTP
- **SSH Tunnel**: If you use SSH tunneling
- **VPN**: If both machines are on the same VPN

### **Option 2: Expose MCP Server Over HTTP**

#### **1. Create HTTP MCP Server**
```python
# http_mcp_server.py
import asyncio
from fastapi import FastAPI
from mcp.server import Server
from local_browser_mcp_server import LocalBrowserMCP

app = FastAPI()
mcp_server = LocalBrowserMCP()

@app.post("/mcp/call_tool")
async def call_tool(request: dict):
    # Convert HTTP request to MCP request
    # Call the MCP server
    # Return response
    pass

@app.get("/mcp/list_tools")
async def list_tools():
    # Return available tools
    pass
```

#### **2. Start HTTP Server**
```bash
# Start HTTP server
uvicorn http_mcp_server:app --host 0.0.0.0 --port 8000
```

#### **3. Connect Remote Agent**
```python
# Remote agent code
import httpx

async def call_mcp_tool(tool_name, arguments):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://your-machine:8000/mcp/call_tool",
            json={"name": tool_name, "arguments": arguments}
        )
        return response.json()
```

## 🔧 **Configuration Options**

### **Local Browser MCP Server Features**

#### **Available Tools:**
- `place_grocery_order` - Place grocery orders with local browser
- `get_all_orders` - Get all current orders
- `get_order_status` - Get specific order status
- `update_order` - Update existing orders
- `cancel_order` - Cancel orders
- `get_supported_sites` - List supported sites
- `check_browser_status` - Check browser availability
- `start_browser` - Start local browser

#### **Supported Sites:**
- **Instacart**: Grocery delivery
- **Uber Eats**: Food and grocery delivery
- **DoorDash**: Food and grocery delivery

### **Browser Configuration:**
```python
# Browser settings
browser = Browser(
    cdp_url="http://localhost:9222",  # Local Chrome
    headless=False,                   # Show browser window
    window_size={"width": 1920, "height": 1080},
    viewport={"width": 1280, "height": 720}
)
```

## 🌐 **Network Configuration**

### **Option 1: SSH Tunnel (Recommended)**
```bash
# On your local machine
ssh -R 8000:localhost:8000 user@remote-server

# On remote machine
curl http://localhost:8000/mcp/list_tools
```

### **Option 2: VPN Connection**
```bash
# Both machines on same VPN
# Remote agent connects directly to your machine
curl http://your-vpn-ip:8000/mcp/list_tools
```

### **Option 3: Port Forwarding**
```bash
# Forward local port to remote
ssh -L 8000:localhost:8000 user@remote-server
```

## 🔒 **Security Considerations**

### **1. Network Security**
- Use SSH tunnels for secure connections
- Implement authentication for HTTP endpoints
- Use HTTPS for production deployments

### **2. Browser Security**
- Run Chrome in a sandboxed environment
- Limit browser permissions
- Monitor browser activity

### **3. MCP Server Security**
- Validate all incoming requests
- Implement rate limiting
- Log all activities

## 📊 **Usage Examples**

### **Example 1: Remote Agent Calling Local Browser**
```python
# Remote agent code
async def place_grocery_order(items, site):
    response = await call_mcp_tool("place_grocery_order", {
        "items": items,
        "site": site,
        "max_total_price": 25.0
    })
    return response
```

### **Example 2: Check Browser Status**
```python
# Check if local browser is available
status = await call_mcp_tool("check_browser_status", {})
print(f"Browser status: {status}")
```

### **Example 3: Get All Orders**
```python
# Get all current orders
orders = await call_mcp_tool("get_all_orders", {})
print(f"Current orders: {orders}")
```

## 🚀 **Deployment Options**

### **Option 1: Local Development**
```bash
# Start browser
./start_local_browser.sh

# Start MCP server
python local_browser_mcp_server.py

# Connect remote agent via SSH tunnel
```

### **Option 2: Production Deployment**
```bash
# Use systemd service for MCP server
sudo systemctl start local-browser-mcp

# Use nginx for HTTP proxy
sudo nginx -s reload

# Monitor with systemd
sudo systemctl status local-browser-mcp
```

### **Option 3: Docker Deployment**
```dockerfile
# Dockerfile for local browser MCP
FROM python:3.11-slim

# Install Chrome
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Copy MCP server
COPY local_browser_mcp_server.py .
COPY requirements.txt .

# Install dependencies
RUN pip install -r requirements.txt

# Start Chrome and MCP server
CMD ["sh", "-c", "google-chrome --remote-debugging-port=9222 & python local_browser_mcp_server.py"]
```

## 🔍 **Troubleshooting**

### **Common Issues:**

#### **1. Chrome Not Starting**
```bash
# Check if Chrome is installed
which google-chrome

# Check if port 9222 is available
netstat -an | grep 9222

# Kill existing Chrome processes
pkill -f chrome
```

#### **2. MCP Server Not Connecting**
```bash
# Check if MCP server is running
ps aux | grep local_browser_mcp_server

# Check browser status
curl http://localhost:9222/json/version
```

#### **3. Remote Agent Connection Issues**
```bash
# Test network connectivity
ping your-machine-ip

# Test port accessibility
telnet your-machine-ip 8000

# Check firewall settings
sudo ufw status
```

## 📈 **Performance Optimization**

### **1. Browser Performance**
- Use headless mode for better performance
- Limit concurrent browser sessions
- Implement browser session pooling

### **2. Network Performance**
- Use WebSocket connections for real-time updates
- Implement connection pooling
- Use compression for large responses

### **3. MCP Server Performance**
- Implement caching for frequent requests
- Use async/await for better concurrency
- Monitor resource usage

## 🎯 **Best Practices**

### **1. Security**
- Always use SSH tunnels for remote connections
- Implement proper authentication
- Monitor and log all activities

### **2. Reliability**
- Implement health checks
- Use process managers (systemd, supervisor)
- Set up monitoring and alerting

### **3. Scalability**
- Use connection pooling
- Implement rate limiting
- Monitor resource usage

## 🎉 **Summary**

The local browser MCP server allows you to:

✅ **Control your local browser** from remote agents  
✅ **Maintain security** with local browser control  
✅ **Scale easily** with multiple remote agents  
✅ **Monitor activities** with local browser visibility  
✅ **Deploy flexibly** with various network configurations  

This architecture is perfect for scenarios where you want to:
- Keep browser automation local for security
- Allow remote agents to control your browser
- Maintain visibility into browser activities
- Scale to multiple remote agents

The MCP server acts as a bridge between remote agents and your local browser, providing a secure and efficient way to automate browser tasks! 🛒🌐✨
