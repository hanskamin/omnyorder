#!/usr/bin/env python3
"""
HTTP MCP Server for Local Browser Control
Exposes MCP server over HTTP so remote agents can control local browser
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from local_browser_mcp_server import LocalBrowserMCP
from mcp.types import CallToolRequest, CallToolRequestParams

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Local Browser MCP Server",
    description="HTTP interface for controlling local browser via MCP",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP server
mcp_server = LocalBrowserMCP()

# Pydantic models for HTTP requests
class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}

class ToolCallResponse(BaseModel):
    success: bool
    result: str
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    browser_available: bool

@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "message": "Local Browser MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "tools": "/tools",
            "call_tool": "/call_tool"
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Check browser status
        browser_status_request = CallToolRequest(
            params=CallToolRequestParams(name="check_browser_status", arguments={})
        )
        browser_result = await mcp_server.call_tool(browser_status_request)
        browser_available = "running" in browser_result.content[0].text.lower()
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            browser_available=browser_available
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now().isoformat(),
            browser_available=False
        )

@app.get("/tools")
async def list_tools():
    """List available MCP tools"""
    try:
        tools_request = CallToolRequest(
            params=CallToolRequestParams(name="list_tools", arguments={})
        )
        result = await mcp_server.call_tool(tools_request)
        
        # Parse tools from result
        tools_data = []
        if hasattr(result, 'content') and result.content:
            # This is a simplified version - in practice you'd parse the tools properly
            tools_data = [
                {
                    "name": "place_grocery_order",
                    "description": "Place a grocery order with local browser automation",
                    "parameters": {
                        "items": {"type": "array", "items": {"type": "string"}},
                        "site": {"type": "string", "enum": ["instacart", "ubereats", "doordash"]},
                        "max_total_price": {"type": "number", "default": 25.0},
                        "preferred_brand": {"type": "string", "optional": True}
                    }
                },
                {
                    "name": "get_all_orders",
                    "description": "Get all current orders and their statuses",
                    "parameters": {}
                },
                {
                    "name": "get_order_status",
                    "description": "Get status of a specific order",
                    "parameters": {
                        "order_id": {"type": "string", "required": True}
                    }
                },
                {
                    "name": "update_order",
                    "description": "Update an existing order",
                    "parameters": {
                        "order_id": {"type": "string", "required": True},
                        "new_items": {"type": "array", "items": {"type": "string"}, "optional": True},
                        "remove_items": {"type": "array", "items": {"type": "string"}, "optional": True}
                    }
                },
                {
                    "name": "cancel_order",
                    "description": "Cancel an existing order",
                    "parameters": {
                        "order_id": {"type": "string", "required": True}
                    }
                },
                {
                    "name": "get_supported_sites",
                    "description": "Get list of supported grocery sites",
                    "parameters": {}
                },
                {
                    "name": "check_browser_status",
                    "description": "Check if local browser is available",
                    "parameters": {}
                },
                {
                    "name": "start_browser",
                    "description": "Start local browser for automation",
                    "parameters": {
                        "headless": {"type": "boolean", "default": False}
                    }
                }
            ]
        
        return {
            "tools": tools_data,
            "count": len(tools_data)
        }
    except Exception as e:
        logger.error(f"Error listing tools: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing tools: {str(e)}")

@app.post("/call_tool", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """Call an MCP tool"""
    try:
        logger.info(f"Calling tool: {request.name} with arguments: {request.arguments}")
        
        # Create MCP request
        mcp_request = CallToolRequest(
            params=CallToolRequestParams(
                name=request.name,
                arguments=request.arguments
            )
        )
        
        # Call the tool
        result = await mcp_server.call_tool(mcp_request)
        
        # Extract result
        if result.isError:
            return ToolCallResponse(
                success=False,
                result="",
                error=result.content[0].text if result.content else "Unknown error"
            )
        else:
            return ToolCallResponse(
                success=True,
                result=result.content[0].text if result.content else "",
                error=None
            )
            
    except Exception as e:
        logger.error(f"Error calling tool {request.name}: {str(e)}")
        return ToolCallResponse(
            success=False,
            result="",
            error=str(e)
        )

@app.post("/place_grocery_order")
async def place_grocery_order(
    items: List[str],
    site: str,
    max_total_price: float = 25.0,
    preferred_brand: Optional[str] = None
):
    """Convenience endpoint for placing grocery orders"""
    try:
        request = ToolCallRequest(
            name="place_grocery_order",
            arguments={
                "items": items,
                "site": site,
                "max_total_price": max_total_price,
                "preferred_brand": preferred_brand
            }
        )
        
        result = await call_tool(request)
        
        if result.success:
            return {
                "success": True,
                "message": "Grocery order placed successfully",
                "result": result.result
            }
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error(f"Error placing grocery order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders")
async def get_all_orders():
    """Get all current orders"""
    try:
        request = ToolCallRequest(name="get_all_orders", arguments={})
        result = await call_tool(request)
        
        if result.success:
            orders_data = json.loads(result.result)
            return {
                "success": True,
                "orders": orders_data,
                "count": len(orders_data) if orders_data != "No orders found" else 0
            }
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error(f"Error getting orders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders/{order_id}")
async def get_order_status(order_id: str):
    """Get status of a specific order"""
    try:
        request = ToolCallRequest(
            name="get_order_status",
            arguments={"order_id": order_id}
        )
        result = await call_tool(request)
        
        if result.success:
            order_data = json.loads(result.result)
            return {
                "success": True,
                "order": order_data
            }
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error(f"Error getting order status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/orders/{order_id}")
async def update_order(
    order_id: str,
    new_items: Optional[List[str]] = None,
    remove_items: Optional[List[str]] = None
):
    """Update an existing order"""
    try:
        arguments = {"order_id": order_id}
        if new_items:
            arguments["new_items"] = new_items
        if remove_items:
            arguments["remove_items"] = remove_items
            
        request = ToolCallRequest(name="update_order", arguments=arguments)
        result = await call_tool(request)
        
        if result.success:
            return {
                "success": True,
                "message": "Order updated successfully",
                "result": result.result
            }
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error(f"Error updating order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an existing order"""
    try:
        request = ToolCallRequest(
            name="cancel_order",
            arguments={"order_id": order_id}
        )
        result = await call_tool(request)
        
        if result.success:
            return {
                "success": True,
                "message": "Order cancelled successfully",
                "result": result.result
            }
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sites")
async def get_supported_sites():
    """Get list of supported grocery sites"""
    try:
        request = ToolCallRequest(name="get_supported_sites", arguments={})
        result = await call_tool(request)
        
        if result.success:
            sites_data = json.loads(result.result)
            return {
                "success": True,
                "sites": sites_data
            }
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error(f"Error getting supported sites: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/browser/status")
async def check_browser_status():
    """Check browser status"""
    try:
        request = ToolCallRequest(name="check_browser_status", arguments={})
        result = await call_tool(request)
        
        return {
            "success": True,
            "status": result.result,
            "available": "running" in result.result.lower()
        }
        
    except Exception as e:
        logger.error(f"Error checking browser status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/browser/start")
async def start_browser(headless: bool = False):
    """Start local browser"""
    try:
        request = ToolCallRequest(
            name="start_browser",
            arguments={"headless": headless}
        )
        result = await call_tool(request)
        
        if result.success:
            return {
                "success": True,
                "message": "Browser started successfully",
                "result": result.result
            }
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error(f"Error starting browser: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("🚀 Starting HTTP MCP Server for Local Browser Control")
    print("=" * 60)
    print("🌐 Server will be available at: http://localhost:8000")
    print("📋 API Documentation: http://localhost:8000/docs")
    print("🔧 Health Check: http://localhost:8000/health")
    print("=" * 60)
    
    uvicorn.run(
        "http_mcp_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
