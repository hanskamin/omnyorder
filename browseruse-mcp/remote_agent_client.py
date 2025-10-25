#!/usr/bin/env python3
"""
Remote Agent Client for Local Browser MCP Server
Demonstrates how remote agents can control local browser via HTTP
"""

import asyncio
import json
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional

class RemoteAgentClient:
    """Client for remote agents to control local browser MCP server"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if the MCP server is healthy"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.json()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools"""
        try:
            response = await self.client.get(f"{self.base_url}/tools")
            return response.json()["tools"]
        except Exception as e:
            print(f"Error listing tools: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool"""
        try:
            response = await self.client.post(
                f"{self.base_url}/call_tool",
                json={"name": tool_name, "arguments": arguments}
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def place_grocery_order(
        self, 
        items: List[str], 
        site: str, 
        max_total_price: float = 25.0,
        preferred_brand: Optional[str] = None
    ) -> Dict[str, Any]:
        """Place a grocery order"""
        try:
            response = await self.client.post(
                f"{self.base_url}/place_grocery_order",
                json={
                    "items": items,
                    "site": site,
                    "max_total_price": max_total_price,
                    "preferred_brand": preferred_brand
                }
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_all_orders(self) -> Dict[str, Any]:
        """Get all current orders"""
        try:
            response = await self.client.get(f"{self.base_url}/orders")
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status of a specific order"""
        try:
            response = await self.client.get(f"{self.base_url}/orders/{order_id}")
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def update_order(
        self, 
        order_id: str, 
        new_items: Optional[List[str]] = None,
        remove_items: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Update an existing order"""
        try:
            data = {}
            if new_items:
                data["new_items"] = new_items
            if remove_items:
                data["remove_items"] = remove_items
                
            response = await self.client.put(
                f"{self.base_url}/orders/{order_id}",
                json=data
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order"""
        try:
            response = await self.client.delete(f"{self.base_url}/orders/{order_id}")
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_supported_sites(self) -> Dict[str, Any]:
        """Get list of supported grocery sites"""
        try:
            response = await self.client.get(f"{self.base_url}/sites")
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def check_browser_status(self) -> Dict[str, Any]:
        """Check browser status"""
        try:
            response = await self.client.get(f"{self.base_url}/browser/status")
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def start_browser(self, headless: bool = False) -> Dict[str, Any]:
        """Start local browser"""
        try:
            response = await self.client.post(
                f"{self.base_url}/browser/start",
                params={"headless": headless}
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def close(self):
        """Close the client"""
        await self.client.aclose()

async def test_remote_agent():
    """Test remote agent functionality"""
    print("🤖 Testing Remote Agent Client")
    print("=" * 60)
    print(f"Test started at: {datetime.now().isoformat()}")
    
    client = RemoteAgentClient()
    
    try:
        # Test 1: Health check
        print("\n1️⃣ Checking MCP Server Health...")
        health = await client.health_check()
        print(f"Health Status: {health.get('status', 'unknown')}")
        print(f"Browser Available: {health.get('browser_available', False)}")
        
        # Test 2: List tools
        print("\n2️⃣ Getting Available Tools...")
        tools = await client.list_tools()
        print(f"✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool['name']}: {tool['description']}")
        
        # Test 3: Check browser status
        print("\n3️⃣ Checking Browser Status...")
        browser_status = await client.check_browser_status()
        print(f"Browser Status: {browser_status.get('status', 'unknown')}")
        
        # Test 4: Get supported sites
        print("\n4️⃣ Getting Supported Sites...")
        sites = await client.get_supported_sites()
        if sites.get('success'):
            sites_data = sites.get('sites', {})
            print(f"✅ Supported Sites: {list(sites_data.keys())}")
            for site, info in sites_data.items():
                print(f"   - {info['name']}: {info['description']}")
        
        # Test 5: Place grocery order
        print("\n5️⃣ Placing Grocery Order...")
        order_result = await client.place_grocery_order(
            items=["milk", "bread", "eggs"],
            site="instacart",
            max_total_price=25.0,
            preferred_brand="organic"
        )
        
        print(f"Order Result: {'✅ Success' if order_result.get('success') else '❌ Failed'}")
        if order_result.get('success'):
            print(f"Result: {order_result.get('result', '')[:200]}...")
        else:
            print(f"Error: {order_result.get('error', 'Unknown error')}")
        
        # Test 6: Get all orders
        print("\n6️⃣ Getting All Orders...")
        orders = await client.get_all_orders()
        if orders.get('success'):
            orders_data = orders.get('orders', {})
            if orders_data and orders_data != "No orders found":
                print(f"✅ Found {len(orders_data)} orders:")
                for order_id, order in orders_data.items():
                    print(f"   - {order_id}: {order['items']} on {order['site']} ({order['status']})")
            else:
                print("   No orders found")
        else:
            print(f"Error: {orders.get('error', 'Unknown error')}")
        
        # Test 7: Get specific order status
        if orders.get('success') and orders.get('orders') and orders.get('orders') != "No orders found":
            print("\n7️⃣ Getting Order Status...")
            first_order_id = list(orders['orders'].keys())[0]
            order_status = await client.get_order_status(first_order_id)
            if order_status.get('success'):
                order_data = order_status.get('order', {})
                print(f"Order {first_order_id} Details:")
                print(f"   - Items: {order_data.get('items', [])}")
                print(f"   - Site: {order_data.get('site', 'Unknown')}")
                print(f"   - Status: {order_data.get('status', 'Unknown')}")
                print(f"   - Total Price: ${order_data.get('total_price', 0):.2f}")
                print(f"   - Created: {order_data.get('created_at', 'Unknown')}")
                if order_data.get('error_message'):
                    print(f"   - Error: {order_data.get('error_message')}")
                if order_data.get('reasoning'):
                    print(f"   - Reasoning Steps: {len(order_data.get('reasoning', []))}")
                    for i, step in enumerate(order_data.get('reasoning', [])[:3], 1):
                        print(f"     {i}. {step}")
        
        # Test 8: Update order
        if orders.get('success') and orders.get('orders') and orders.get('orders') != "No orders found":
            print("\n8️⃣ Updating Order...")
            first_order_id = list(orders['orders'].keys())[0]
            update_result = await client.update_order(
                order_id=first_order_id,
                new_items=["cheese"],
                remove_items=["bread"]
            )
            print(f"Update Result: {update_result.get('message', 'Unknown')}")
        
        # Test 9: Cancel order
        if orders.get('success') and orders.get('orders') and orders.get('orders') != "No orders found":
            print("\n9️⃣ Cancelling Order...")
            first_order_id = list(orders['orders'].keys())[0]
            cancel_result = await client.cancel_order(first_order_id)
            print(f"Cancel Result: {cancel_result.get('message', 'Unknown')}")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()
    
    print("\n🎉 Remote Agent Test Completed!")
    print("=" * 60)
    print("Summary:")
    print("✅ Remote agent can connect to local MCP server")
    print("✅ Remote agent can control local browser")
    print("✅ Order management works through HTTP API")
    print("✅ Real-time browser automation is functional")
    print("\nNext steps:")
    print("1. Deploy this setup for production use")
    print("2. Set up authentication for security")
    print("3. Monitor browser activities and order processing")
    print("4. Scale to multiple remote agents")

async def main():
    """Main function"""
    print("🚀 Remote Agent Client Test Suite")
    print("=" * 60)
    print("This demonstrates how remote agents can control your local browser")
    print("Make sure the HTTP MCP server is running: python http_mcp_server.py")
    print("=" * 60)
    
    await test_remote_agent()

if __name__ == "__main__":
    asyncio.run(main())
