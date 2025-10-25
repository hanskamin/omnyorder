# Local Browser MCP Server

A Model Context Protocol (MCP) server that allows remote agents to control your local browser for automated grocery ordering.

## 🏗️ Architecture

```
Remote Agent (elsewhere) → HTTP MCP Server (your machine) → Local Browser (your machine)
```

## 🚀 Quick Start

### 1. Start Local Browser
```bash
./start_local_browser.sh
```

### 2. Start MCP Server
```bash
python3 http_mcp_server.py
```

### 3. Test Remote Agent
```bash
python3 remote_agent_client.py
```

## 📁 Project Structure

```
omnyorder-mcp/
├── http_mcp_server.py              # HTTP MCP server
├── local_browser_mcp_server.py    # Core MCP server logic
├── remote_agent_client.py         # Test remote agent client
├── test_local_browser_mcp.py       # Manual test script
├── start_local_browser.sh         # Start Chrome with remote debugging
├── local_mcp_config.json          # MCP server configuration
├── requirements_http.txt           # Python dependencies
├── LOCAL_BROWSER_MCP_GUIDE.md     # Detailed setup guide
└── LOCAL_BROWSER_HTTP_SUMMARY.md  # Complete documentation
```

## 🔧 Core Files

### **Essential Files:**
- `http_mcp_server.py` - HTTP API server for remote agents
- `local_browser_mcp_server.py` - Core MCP server with browser automation
- `remote_agent_client.py` - Test client for remote agents
- `test_local_browser_mcp.py` - Manual testing script
- `start_local_browser.sh` - Chrome startup script

### **Configuration:**
- `local_mcp_config.json` - MCP server configuration
- `requirements_http.txt` - Python dependencies

### **Documentation:**
- `LOCAL_BROWSER_MCP_GUIDE.md` - Detailed setup guide
- `LOCAL_BROWSER_HTTP_SUMMARY.md` - Complete documentation

## 🌐 Available Endpoints

- `GET /health` - Server health check
- `GET /tools` - List available MCP tools
- `POST /call_tool` - Call any MCP tool
- `POST /place_grocery_order` - Place grocery orders
- `GET /orders` - Get all orders
- `GET /orders/{order_id}` - Get specific order
- `PUT /orders/{order_id}` - Update order
- `DELETE /orders/{order_id}` - Cancel order
- `GET /sites` - Get supported grocery sites
- `GET /browser/status` - Check browser status
- `POST /browser/start` - Start browser

## 🛒 Supported Sites

- **Instacart** - Grocery delivery service
- **Uber Eats** - Food and grocery delivery  
- **DoorDash** - Food and grocery delivery

## 🔒 Security

- **Local Browser**: Chrome runs on your machine
- **HTTP API**: Exposed for remote agent access
- **No Authentication**: Currently open access (add for production)
- **No Encryption**: HTTP only (use HTTPS for production)

## 🚀 Usage Examples

### Remote Agent Control
```python
import httpx

async def place_order(items, site):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://your-machine:8000/place_grocery_order",
            json={"items": items, "site": site}
        )
        return response.json()
```

### Manual Testing
```bash
# Test health
curl http://localhost:8000/health

# Test tools
curl http://localhost:8000/tools

# Test remote agent
python3 remote_agent_client.py
```

## 📊 Test Results

✅ **HTTP MCP Server**: Running on `http://localhost:8000`  
✅ **Local Browser**: Chrome with remote debugging connected  
✅ **Remote Agent**: Can control local browser via HTTP  
✅ **Order Management**: Create, update, cancel orders  
✅ **Real-time Automation**: Live browser control  

## 🎯 Perfect For

- **Remote Grocery Ordering**: Agents place orders on your behalf
- **Multi-Agent Coordination**: Multiple agents can connect
- **Automated Shopping**: Scheduled orders and monitoring
- **Development & Testing**: Remote browser control

## 🔧 Network Options

### SSH Tunnel (Recommended)
```bash
ssh -R 8000:localhost:8000 user@remote-server
```

### Direct Network Access
```bash
python3 http_mcp_server.py --host 0.0.0.0 --port 8000
```

### VPN Connection
Both machines on same VPN network.

## 📈 Production Deployment

### Add Security
- Authentication (API keys, JWT tokens)
- HTTPS encryption
- Rate limiting
- Firewall restrictions
- Activity monitoring

### Scale to Multiple Agents
- Connection pooling
- Resource monitoring
- Load balancing
- Health checks

## 🎉 Summary

This setup provides:
- **Remote Control**: Agents can control your local browser
- **Local Security**: Browser stays on your machine
- **Real-time Visibility**: See what the browser is doing
- **Multi-Site Support**: Instacart, Uber Eats, DoorDash
- **Order Management**: Complete order lifecycle

Perfect for remote agents that need to control your local browser while maintaining security and visibility! 🛒🌐✨