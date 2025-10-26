import asyncio
from enum import Enum

from pydantic import BaseModel, Field

from browser_use import Agent, Browser
from browser_use.llm.models import ChatBrowserUse


class SiteType(str, Enum):
	"""Supported shopping sites"""
	INSTACART = "instacart"
	UBEREATS = "ubereats"
	DOORDASH = "doordash"


class OrderItem(BaseModel):
	"""A single item in an order"""
	
	name: str = Field(..., description='Item name')
	quantity: str = Field(..., description='Quantity needed')
	details: str = Field(default="", description='Additional details or specifications')


class Order(BaseModel):
	"""An order for a specific platform"""
	
	platform: str = Field(..., description='Platform name (e.g., Instacart, Uber Eats)')
	items: list[OrderItem] = Field(..., description='Items to order')


class ShoppingRequest(BaseModel):
	"""Structured shopping request from another agent"""
	
	budget: str | None = Field(None, description='Budget limit if specified')
	dietary_restrictions: list[str] = Field(default_factory=list, description='Dietary restrictions')
	orders: list[Order] = Field(..., description='Orders to process')


class GroceryItem(BaseModel):
	"""A single grocery item"""

	name: str = Field(..., description='Item name')
	price: float = Field(..., description='Price as number')
	brand: str | None = Field(None, description='Brand name')
	size: str | None = Field(None, description='Size or quantity')
	url: str = Field(..., description='Full URL to item')
	site: str = Field(..., description='Site where item was found')


class GroceryCart(BaseModel):
	"""Grocery cart results"""

	items: list[GroceryItem] = Field(default_factory=list, description='All grocery items found')
	site: str = Field(..., description='Site where shopping was done')


def get_site_config(site: SiteType) -> dict:
	"""Get configuration for each supported site"""
	configs = {
		SiteType.INSTACART: {
			"name": "Instacart",
			"url": "https://www.instacart.com/",
			"description": "grocery delivery service"
		},
		SiteType.UBEREATS: {
			"name": "UberEats",
			"url": "https://www.ubereats.com/",
			"description": "food and grocery delivery service"
		},
		SiteType.DOORDASH: {
			"name": "DoorDash",
			"url": "https://www.doordash.com/",
			"description": "food and grocery delivery service"
		}
	}
	return configs[site]


def map_platform_to_site_type(platform: str) -> SiteType:
	"""Map platform name to SiteType enum"""
	platform_lower = platform.lower()
	if 'instacart' in platform_lower:
		return SiteType.INSTACART
	elif 'uber' in platform_lower or 'ubereats' in platform_lower:
		return SiteType.UBEREATS
	elif 'doordash' in platform_lower or 'door' in platform_lower:
		return SiteType.DOORDASH
	else:
		# Default to Instacart for unknown platforms
		return SiteType.INSTACART


def parse_site_from_task(task: str) -> SiteType:
	"""Parse site from task prompt"""
	task_lower = task.lower()
	if 'instacart' in task_lower:
		return SiteType.INSTACART
	elif 'ubereats' in task_lower:
		return SiteType.UBEREATS
	elif 'doordash' in task_lower:
		return SiteType.DOORDASH
	else:
		# Default to Instacart if no site is detected
		return SiteType.INSTACART


def generate_task_for_order(order: Order, budget: float | None = None, dietary_restrictions: list[str] = None) -> str:
	"""Generate task prompt for a specific order"""
	if dietary_restrictions is None:
		dietary_restrictions = []
	
	# Map platform to site type
	site_type = map_platform_to_site_type(order.platform)
	config = get_site_config(site_type)
	
	# Build items list with quantities and details
	items_text = []
	for item in order.items:
		item_desc = f"{item.name}"
		if item.quantity:
			item_desc += f" (quantity: {item.quantity})"
		if item.details:
			item_desc += f" - {item.details}"
		items_text.append(item_desc)
	
	items_list = "\n".join(f"- {item}" for item in items_text)
	
	# Build dietary restrictions text
	dietary_text = ""
	if dietary_restrictions:
		dietary_text = f"\n\nDietary restrictions to consider: {', '.join(dietary_restrictions)}"
	
	# Build budget text
	budget_text = ""
	if budget:
		budget_text = f"\n\nBudget limit: ${budget}"
	
	task = f"""
Search for the following items on {config['name']} at the nearest store:

{items_list}

You will buy all of the items at the same store.
For each item:
1. Search for the item
2. Find the best match (closest name, lowest price)
3. Add the item to the cart

{dietary_text}{budget_text}

IMPORTANT SAFETY REQUIREMENTS:
- NEVER add items that violate dietary restrictions or allergies
- Check ingredient lists and allergen information carefully
- If an item contains restricted ingredients, find a safe alternative or skip it
- Verify cross-contamination risks for severe allergies

RESTAURANT/STORE HOURS:
- Check if the restaurant/store is currently open before attempting to order
- If the restaurant/store is closed, immediately stop and return an error
- Look for "Closed", "Currently unavailable", or "Hours" indicators on the page
- Do not attempt to add items to cart if the establishment is not open for orders

Site: {config['name']}: {config['url']}
"""
	return task


def display_cart_summary(cart: GroceryCart):
	"""Display cart summary for user approval"""
	print(f'\n{"=" * 60}')
	print(f'Cart Summary - {cart.site}')
	print(f'{"=" * 60}\n')
	
	if cart.items:
		total_price = sum(item.price for item in cart.items)
		for i, item in enumerate(cart.items, 1):
			print(f'{i}. {item.name}')
			print(f'   Price: ${item.price:.2f}')
			if item.brand:
				print(f'   Brand: {item.brand}')
			if item.size:
				print(f'   Size: {item.size}')
			print(f'   URL: {item.url}')
			print()
		
		print(f'{"-" * 60}')
		print(f'Total Items: {len(cart.items)}')
		print(f'Total Price: ${total_price:.2f}')
		print(f'{"=" * 60}')
	else:
		print("No items found in cart.")
	
	return cart.items


def get_user_approval() -> bool:
	"""Get user approval for the cart - for agent use, always approve"""
	print("Agent approval: Auto-approving cart for agent execution")
	return True


async def add_to_cart(task: str):
	"""Add items to cart based on task prompt - for agent invocation"""
	browser = Browser(cdp_url='http://localhost:9222')
	llm = ChatBrowserUse()

	# Parse site from task
	site = parse_site_from_task(task)
	config = get_site_config(site)
	print(f"Detected site: {config['name']}")

	# Create agent with structured output
	agent = Agent(
		browser=browser,
		llm=llm,
		task=task,
		output_model_schema=GroceryCart,
	)

	# Run the agent to find items
	print("Searching for items...")
	result = await agent.run()
	
	if result and result.structured_output:
		cart = result.structured_output
		
		# Display cart summary for approval
		items = display_cart_summary(cart)
		
		if items:
			# Auto-approve for agent execution
			if get_user_approval():
				print("\nProceeding with purchase...")
				print("✅ Purchase approved! Items will be added to cart.")
			else:
				print("❌ Purchase cancelled.")
		else:
			print("No items found to approve.")
	
	return result


async def process_structured_shopping_request(request: ShoppingRequest) -> dict:
	"""Process structured shopping request from another agent"""
	results = {
		"success": True,
		"budget": request.budget,
		"dietary_restrictions": request.dietary_restrictions,
		"orders": [],
		"total_orders": len(request.orders),
		"successful_orders": 0,
		"failed_orders": 0
	}
	
	for order in request.orders:
		print(f"\nProcessing order for {order.platform}...")
		
		# Generate task for this order
		task = generate_task_for_order(
			order, 
			request.budget, 
			request.dietary_restrictions
		)
		
		# Process the order
		result = await add_to_cart(task)
		
		order_result = {
			"platform": order.platform,
			"success": False,
			"items": [],
			"total_items": 0,
			"total_price": 0.0,
			"error": None
		}
		
		if result and result.structured_output:
			cart = result.structured_output
			order_result.update({
				"success": True,
				"items": [
					{
						"name": item.name,
						"price": item.price,
						"brand": item.brand,
						"size": item.size,
						"url": item.url
					} for item in cart.items
				],
				"total_items": len(cart.items),
				"total_price": sum(item.price for item in cart.items)
			})
			results["successful_orders"] += 1
		else:
			order_result["error"] = "Failed to find items or add to cart"
			results["failed_orders"] += 1
		
		results["orders"].append(order_result)
	
	# Update overall success status
	if results["failed_orders"] > 0:
		results["success"] = results["successful_orders"] > 0
	
	return results


async def shop_for_items(items: list[str], site: str = "instacart") -> dict:
	"""Main function for agent invocation - shop for items on specified site (legacy function)"""
	
	# Create task prompt
	task = f"""
    Search for "{items}" on {site.title()} at the nearest store.

    You will buy all of the items at the same store.
    For each item:
    1. Search for the item
    2. Find the best match (closest name, lowest price)
    3. Add the item to the cart

    Site:
    - {site.title()}: https://www.{site}.com/
    """
	
	# Run the shopping task
	result = await add_to_cart(task)
	
	# Return structured result for agent
	if result and result.structured_output:
		cart = result.structured_output
		return {
			"success": True,
			"site": cart.site,
			"items": [
				{
					"name": item.name,
					"price": item.price,
					"brand": item.brand,
					"size": item.size,
					"url": item.url
				} for item in cart.items
			],
			"total_items": len(cart.items),
			"total_price": sum(item.price for item in cart.items)
		}
	else:
		return {
			"success": False,
			"error": "Failed to find items or add to cart"
		}


if __name__ == '__main__':
	# Example usage for structured shopping request
	shopping_request = ShoppingRequest(
		budget=50.0,
		dietary_restrictions=["vegetarian"],
		orders=[
			Order(
				platform="Instacart",
				items=[
					OrderItem(name="Roma Tomatoes", quantity="2 lbs", details=""),
					OrderItem(name="Garlic", quantity="1 bulb", details=""),
					OrderItem(name="Fresh Basil", quantity="1 bunch", details=""),
					OrderItem(name="Spaghetti Pasta", quantity="1 box", details="16 oz")
				]
			),
			Order(
				platform="Uber Eats",
				items=[
					OrderItem(name="Strawberry Banana Smoothie", quantity="1", details="Medium, 16oz"),
					OrderItem(name="Turkey and Swiss Sandwich", quantity="1", details="On whole wheat bread")
				]
			)
		]
	)
	
	print("Processing structured shopping request...")
	result = asyncio.run(process_structured_shopping_request(shopping_request))
	
	if result['success']:
		print(f"\n✅ Shopping completed successfully!")
		print(f"Total orders: {result['total_orders']}")
		print(f"Successful orders: {result['successful_orders']}")
		print(f"Failed orders: {result['failed_orders']}")
		
		for order_result in result['orders']:
			if order_result['success']:
				print(f"\n{order_result['platform']}: {order_result['total_items']} items, ${order_result['total_price']:.2f}")
			else:
				print(f"\n{order_result['platform']}: Failed - {order_result['error']}")
	else:
		print(f"❌ Shopping failed for all orders")