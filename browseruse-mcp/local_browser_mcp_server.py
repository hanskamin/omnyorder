#!/usr/bin/env python3
"""
MCP Server for Local Browser Control
Allows remote agents to control your local browser through MCP
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
    LoggingLevel
)

from browser_use import Agent, Browser, ChatBrowserUse
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GrocerySite(str, Enum):
    """Supported grocery sites"""
    INSTACART = "instacart"
    UBER_EATS = "ubereats"
    DOORDASH = "doordash"

class GroceryItem(BaseModel):
    """A single grocery item"""
    name: str = Field(..., description='Item name')
    price: float = Field(..., description='Price as number')
    brand: str | None = Field(None, description='Brand name')
    size: str | None = Field(None, description='Size or quantity')
    url: str = Field(..., description='Full URL to item')

class GroceryCart(BaseModel):
    """Grocery cart results"""
    items: list[GroceryItem] = Field(default_factory=list, description='All grocery items found')

class OrderStatus(str, Enum):
    """Order status types"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Order(BaseModel):
    """Order tracking model"""
    order_id: str = Field(..., description='Unique order identifier')
    items: list[str] = Field(..., description='Items in the order')
    site: str = Field(..., description='Site where order was placed')
    status: OrderStatus = Field(default=OrderStatus.PENDING, description='Current order status')
    total_price: float = Field(0.0, description='Total order price')
    created_at: str = Field(..., description='Order creation timestamp')
    updated_at: str = Field(..., description='Last update timestamp')
    error_message: str | None = Field(None, description='Error message if order failed')
    reasoning: list[str] = Field(default_factory=list, description='Order reasoning steps')

class OrderRequest(BaseModel):
    """Order request model"""
    items: list[str] = Field(..., description='Items to order')
    site: GrocerySite = Field(..., description='Site to order from')
    max_total_price: float = Field(25.0, description='Maximum total price')
    preferred_brand: str | None = Field(None, description='Preferred brand')
    max_items_per_product: int = Field(1, description='Maximum items per product')

class LocalBrowserMCP:
    """MCP Server for Local Browser Control"""
    
    def __init__(self):
        self.server = Server("local-browser-mcp")
        self.setup_handlers()
        self.browser = None
        self.orders: Dict[str, Order] = {}
        self.next_order_id = 1
    
    def setup_handlers(self):
        """Setup MCP handlers"""
        self.server.list_tools = self.list_tools
        self.server.call_tool = self.call_tool
    
    async def list_tools(self, request: ListToolsRequest) -> ListToolsResult:
        """List available tools"""
        tools = [
            Tool(
                name="place_grocery_order",
                description="Place a grocery order with local browser automation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of items to order"
                        },
                        "site": {
                            "type": "string",
                            "enum": ["instacart", "ubereats", "doordash"],
                            "description": "Site to order from"
                        },
                        "max_total_price": {
                            "type": "number",
                            "description": "Maximum total price",
                            "default": 25.0
                        },
                        "preferred_brand": {
                            "type": "string",
                            "description": "Preferred brand (optional)"
                        }
                    },
                    "required": ["items", "site"]
                }
            ),
            Tool(
                name="get_all_orders",
                description="Get all current orders and their statuses",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="get_order_status",
                description="Get status of a specific order",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Order ID to check"
                        }
                    },
                    "required": ["order_id"]
                }
            ),
            Tool(
                name="update_order",
                description="Update an existing order (if possible)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Order ID to update"
                        },
                        "new_items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "New items to add (optional)"
                        },
                        "remove_items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Items to remove (optional)"
                        }
                    },
                    "required": ["order_id"]
                }
            ),
            Tool(
                name="cancel_order",
                description="Cancel an existing order",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Order ID to cancel"
                        }
                    },
                    "required": ["order_id"]
                }
            ),
            Tool(
                name="get_supported_sites",
                description="Get list of supported grocery sites",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="check_browser_status",
                description="Check if local browser is available",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="start_browser",
                description="Start local browser for automation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "headless": {
                            "type": "boolean",
                            "description": "Run browser in headless mode",
                            "default": False
                        }
                    }
                }
            )
        ]
        
        return ListToolsResult(tools=tools)
    
    async def call_tool(self, request: CallToolRequest) -> CallToolResult:
        """Handle tool calls"""
        try:
            tool_name = request.params.name
            arguments = request.params.arguments or {}
            
            if tool_name == "place_grocery_order":
                return await self.place_grocery_order(arguments)
            elif tool_name == "get_all_orders":
                return await self.get_all_orders()
            elif tool_name == "get_order_status":
                return await self.get_order_status(arguments)
            elif tool_name == "update_order":
                return await self.update_order(arguments)
            elif tool_name == "cancel_order":
                return await self.cancel_order(arguments)
            elif tool_name == "get_supported_sites":
                return await self.get_supported_sites()
            elif tool_name == "check_browser_status":
                return await self.check_browser_status()
            elif tool_name == "start_browser":
                return await self.start_browser(arguments)
            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {tool_name}")],
                    isError=True
                )
        except Exception as e:
            logger.error(f"Error in tool call {request.params.name}: {str(e)}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True
            )
    
    async def get_supported_sites(self) -> CallToolResult:
        """Get list of supported sites"""
        sites_info = {
            "instacart": {
                "name": "Instacart",
                "url": "https://www.instacart.com/",
                "description": "Grocery delivery service",
                "features": ["Same-day delivery", "Multiple stores", "Fresh produce"]
            },
            "ubereats": {
                "name": "Uber Eats",
                "url": "https://www.ubereats.com/",
                "description": "Food and grocery delivery",
                "features": ["Quick delivery", "Restaurant food", "Grocery items"]
            },
            "doordash": {
                "name": "DoorDash",
                "url": "https://www.doordash.com/",
                "description": "Food and grocery delivery",
                "features": ["Fast delivery", "Local restaurants", "Grocery stores"]
            }
        }
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(sites_info, indent=2)
            )]
        )
    
    async def get_all_orders(self) -> CallToolResult:
        """Get all current orders"""
        if not self.orders:
            return CallToolResult(
                content=[TextContent(type="text", text="No orders found")]
            )
        
        orders_data = {}
        for order_id, order in self.orders.items():
            orders_data[order_id] = {
                "order_id": order.order_id,
                "items": order.items,
                "site": order.site,
                "status": order.status.value,
                "total_price": order.total_price,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "error_message": order.error_message,
                "reasoning": order.reasoning
            }
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(orders_data, indent=2)
            )]
        )
    
    async def get_order_status(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Get status of a specific order"""
        order_id = arguments.get("order_id")
        if not order_id:
            return CallToolResult(
                content=[TextContent(type="text", text="Order ID is required")],
                isError=True
            )
        
        if order_id not in self.orders:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Order {order_id} not found")],
                isError=True
            )
        
        order = self.orders[order_id]
        order_data = {
            "order_id": order.order_id,
            "items": order.items,
            "site": order.site,
            "status": order.status.value,
            "total_price": order.total_price,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "error_message": order.error_message,
            "reasoning": order.reasoning
        }
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(order_data, indent=2)
            )]
        )
    
    async def update_order(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Update an existing order"""
        order_id = arguments.get("order_id")
        if not order_id:
            return CallToolResult(
                content=[TextContent(type="text", text="Order ID is required")],
                isError=True
            )
        
        if order_id not in self.orders:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Order {order_id} not found")],
                isError=True
            )
        
        order = self.orders[order_id]
        
        # Update items
        new_items = arguments.get("new_items", [])
        remove_items = arguments.get("remove_items", [])
        
        if new_items:
            order.items.extend(new_items)
            order.reasoning.append(f"➕ Added items: {', '.join(new_items)}")
        
        if remove_items:
            for item in remove_items:
                if item in order.items:
                    order.items.remove(item)
            order.reasoning.append(f"➖ Removed items: {', '.join(remove_items)}")
        
        order.updated_at = datetime.now().isoformat()
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Order {order_id} updated successfully. New items: {order.items}"
            )]
        )
    
    async def cancel_order(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Cancel an existing order"""
        order_id = arguments.get("order_id")
        if not order_id:
            return CallToolResult(
                content=[TextContent(type="text", text="Order ID is required")],
                isError=True
            )
        
        if order_id not in self.orders:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Order {order_id} not found")],
                isError=True
            )
        
        order = self.orders[order_id]
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now().isoformat()
        order.reasoning.append("❌ Order cancelled by user")
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Order {order_id} cancelled successfully"
            )]
        )
    
    async def check_browser_status(self) -> CallToolResult:
        """Check if local browser is available"""
        try:
            # Check if Chrome is running with remote debugging
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:9222/json/version", timeout=5.0)
                if response.status_code == 200:
                    browser_info = response.json()
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Local browser is running: {browser_info.get('Browser', 'Chrome')}/{browser_info.get('User-Agent', 'Unknown')}"
                        )]
                    )
        except Exception as e:
            pass
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text="Local browser is not available. Start Chrome with: chrome --remote-debugging-port=9222"
            )]
        )
    
    async def start_browser(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Start local browser for automation"""
        try:
            headless = arguments.get("headless", False)
            
            # Start Chrome with remote debugging
            import subprocess
            import platform
            
            if platform.system() == "Darwin":  # macOS
                chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            elif platform.system() == "Windows":
                chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
            else:  # Linux
                chrome_path = "/usr/bin/google-chrome"
            
            chrome_args = [
                chrome_path,
                "--remote-debugging-port=9222",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-popup-blocking",
                "--disable-translate",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-client-side-phishing-detection",
                "--disable-sync",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-domain-reliability",
                "--disable-features=VizDisplayCompositor"
            ]
            
            if headless:
                chrome_args.append("--headless")
            
            subprocess.Popen(chrome_args)
            
            # Wait for browser to start
            await asyncio.sleep(3)
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="Local browser started successfully"
                )]
            )
            
        except Exception as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Failed to start browser: {str(e)}"
                )],
                isError=True
            )
    
    async def place_grocery_order(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Place a grocery order with local browser automation"""
        try:
            # Parse arguments
            items = arguments.get("items", [])
            site_str = arguments.get("site", "instacart")
            max_total_price = arguments.get("max_total_price", 25.0)
            preferred_brand = arguments.get("preferred_brand")
            
            if not items:
                return CallToolResult(
                    content=[TextContent(type="text", text="No items specified")],
                    isError=True
                )
            
            # Validate site
            try:
                site = GrocerySite(site_str)
            except ValueError:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Invalid site: {site_str}")],
                    isError=True
                )
            
            # Create order tracking
            order_id = f"order_{self.next_order_id}"
            self.next_order_id += 1
            
            current_time = datetime.now().isoformat()
            order = Order(
                order_id=order_id,
                items=items,
                site=site.value,
                status=OrderStatus.PENDING,
                created_at=current_time,
                updated_at=current_time,
                reasoning=[]
            )
            
            # Add to orders tracking
            self.orders[order_id] = order
            order.reasoning.append(f"🛒 Order {order_id} created for {len(items)} items on {site.value}")
            
            # Check browser status
            browser_status = await self.check_browser_status()
            if "not available" in browser_status.content[0].text:
                order.status = OrderStatus.FAILED
                order.error_message = "Local browser not available"
                order.reasoning.append("❌ Local browser not available")
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"Order {order_id} failed: Local browser not available. Start Chrome with: chrome --remote-debugging-port=9222"
                    )],
                    isError=True
                )
            
            # Update order status
            order.status = OrderStatus.IN_PROGRESS
            order.updated_at = datetime.now().isoformat()
            order.reasoning.append("🤖 Starting local browser automation...")
            
            # Create order request
            order_request = OrderRequest(
                items=items,
                site=site,
                max_total_price=max_total_price,
                preferred_brand=preferred_brand
            )
            
            # Execute order with local browser
            result = await self._execute_order_with_local_browser(order_request, order.reasoning)
            
            # Update order with results
            if result.get('success', False):
                order.status = OrderStatus.COMPLETED
                order.total_price = result.get('total_price', 0.0)
                order.reasoning.append(f"✅ Order completed successfully. Total: ${order.total_price:.2f}")
            else:
                order.status = OrderStatus.FAILED
                order.error_message = result.get('error', 'Unknown error')
                order.reasoning.append(f"❌ Order failed: {order.error_message}")
            
            order.updated_at = datetime.now().isoformat()
            
            # Format result
            result_text = f"Order Summary:\n"
            result_text += f"Order ID: {order_id}\n"
            result_text += f"Items: {', '.join(items)}\n"
            result_text += f"Site: {site.value}\n"
            result_text += f"Status: {order.status.value}\n"
            result_text += f"Total Price: ${order.total_price:.2f}\n"
            result_text += f"Created: {order.created_at}\n"
            result_text += f"Updated: {order.updated_at}\n"
            
            if order.error_message:
                result_text += f"Error: {order.error_message}\n"
            
            result_text += f"\nReasoning Steps:\n"
            for i, step in enumerate(order.reasoning, 1):
                result_text += f"{i}. {step}\n"
            
            if result.get('cart_items'):
                result_text += f"\nCart Items:\n"
                for item in result['cart_items']:
                    result_text += f"- {item['name']}: ${item['price']:.2f}\n"
            
            return CallToolResult(
                content=[TextContent(type="text", text=result_text)]
            )
            
        except Exception as e:
            logger.error(f"Error placing grocery order: {str(e)}")
            if 'order_id' in locals():
                order.status = OrderStatus.FAILED
                order.error_message = str(e)
                order.reasoning.append(f"❌ Error: {str(e)}")
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Error placing order: {str(e)}"
                )],
                isError=True
            )
    
    async def _execute_order_with_local_browser(self, order_request: OrderRequest, reasoning_stream: List[str]) -> Dict[str, Any]:
        """Execute order with local browser automation"""
        try:
            # Use local browser (Chrome with remote debugging)
            browser = Browser(cdp_url="http://localhost:9222")
            llm = ChatBrowserUse()
            
            # Build task prompt
            site_configs = {
                GrocerySite.INSTACART: {
                    "url": "https://www.instacart.com/",
                    "name": "Instacart"
                },
                GrocerySite.UBER_EATS: {
                    "url": "https://www.ubereats.com/",
                    "name": "Uber Eats"
                },
                GrocerySite.DOORDASH: {
                    "url": "https://www.doordash.com/",
                    "name": "DoorDash"
                }
            }
            
            site_config = site_configs[order_request.site]
            task_prompt = f"""
            Task: Search for {order_request.items} on {site_config['name']} at the nearest store. You will buy all of the items at the same store. For each item:
            1. Search for the item
            2. Find the best match (closest name, lowest price)
            3. Add the item to the cart
            
            Site: {site_config['name']}: {site_config['url']}
            
            Expected output format: GroceryCart {GroceryCart.model_json_schema()}
            """
            
            if order_request.max_total_price:
                task_prompt += f"\nMaximum total price: ${order_request.max_total_price}"
            
            if order_request.preferred_brand:
                task_prompt += f"\nPreferred brand: {order_request.preferred_brand}"
            
            reasoning_stream.append(f"🌐 Navigating to {site_config['name']}...")
            
            # Create agent and run
            agent = Agent(
                task=task_prompt,
                llm=llm,
                browser=browser
            )
            
            reasoning_stream.append("🤖 Starting browser automation...")
            result = await agent.run()
            
            reasoning_stream.append("✅ Browser automation completed")
            
            # Parse result
            if result and hasattr(result, 'result'):
                cart_data = result.result
                if isinstance(cart_data, dict) and 'items' in cart_data:
                    total_price = sum(item.get('price', 0) for item in cart_data['items'])
                    return {
                        'success': True,
                        'total_price': total_price,
                        'cart_items': cart_data['items']
                    }
            
            return {
                'success': False,
                'error': 'Failed to parse cart data'
            }
            
        except Exception as e:
            logger.error(f"Error in local browser automation: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            if 'browser' in locals():
                await browser.close()

async def main():
    """Main function to run the MCP server"""
    mcp_server = LocalBrowserMCP()
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="local-browser-mcp",
                server_version="1.0.0",
                capabilities=mcp_server.server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities=None
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
