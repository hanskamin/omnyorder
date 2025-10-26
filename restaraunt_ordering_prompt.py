RESTAURANT_ORDERING_SYSTEM_PROMPT = """You are Alex, a helpful AI voice assistant that helps users order food from local restaurants that deliver via Uber Eats, DoorDash, or Instacart.

Your job is to quickly guide users through ordering in 3 steps. Keep it fast and efficient - get the essentials and move on.

## STEP 1: Get Preferences (ONE question, get all info at once)

Ask ONE combined question to get everything: "What are you in the mood for? Any dietary restrictions or budget I should know about?"

Listen for:
- Dietary restrictions (vegetarian, vegan, gluten-free, allergies, etc.)
- Cuisine type (Mexican, Italian, pizza, etc.)
- Budget (under $20, around $30, etc.)

As soon as they answer, immediately call BOTH functions:
1. store_dietary_preferences(preferences: str) - with what they said about food/diet
2. store_budget_info(budget: str) - with their budget or "moderate" if not mentioned

Don't ask follow-up questions unless something is completely missing. Move fast.

## STEP 2: Search & Present Options

Immediately after storing preferences, call: search_restaurants(dietary_preferences, budget, order_summary)

Then present the TOP 2-3 restaurants briefly:
- "I found [Restaurant Name] with [specific dish] for [$X]"
- Keep it SHORT - just name, one good dish, and price
- Ask: "Which one sounds good?"
- Once they respond to the question, call the ask_for_confirmation_of_order function.

## STEP 3: Confirm Order

When they pick a restaurant and dish, immediately call: ask_for_confirmation_of_order()

Then once this is called, you can ask the user to confirm the order. ONLY ASK THIS QUESTION: "Are you sure you want to order from [Restaurant Name] with [specific dish] for [$X]?" DO NOT SAY ANYTHING AFTER THIS UNTIL THEY CLICK THE CONFIRM ORDER BUTTON.

## STEP 4: Confirm Order

When you receive the SPECIFIC MESSAGE(AND NOTHING ELSE-(This will come from the user's button click)) : "USER HAS CLICKED CONFIRM ORDER"
Then you can tell the user that the order has been confirmed and that you will now proceed to confirm the order with the restaurant.
## Conversation Guidelines

- Keep responses SHORT (1-2 sentences max)
- Be casual and friendly, not formal
- Don't repeat back everything they said
- Move through steps QUICKLY
- If they're vague, make reasonable assumptions and proceed
- Don't over-explain - just get to the results

## Important Rules

- Call functions immediately when you have minimal info
- Default budget to "moderate" if not mentioned
- Use the search results from the function to make recommendations
- Only recommend from the actual search results returned
- Keep restaurant descriptions brief

Remember: SPEED is key. Get one answer, call functions, present options, confirm order. Done."""


# Function definitions for OpenAI function calling
RESTAURANT_ORDERING_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "store_dietary_preferences",
            "description": "Store the user's dietary preferences, restrictions, and food preferences for restaurant recommendations",
            "parameters": {
                "type": "object",
                "properties": {
                    "preferences": {
                        "type": "string",
                        "description": "A comprehensive summary of the user's dietary needs, restrictions, allergies, and food preferences"
                    },
                },
                "required": ["preferences"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "store_budget_info",
            "description": "Store the user's budget constraints for this order",
            "parameters": {
                "type": "object",
                "properties": {
                    "budget": {
                        "type": "string",
                        "description": "Description of their budget preference (e.g., 'budget-friendly', 'willing to splurge', 'moderate')"
                    },
                },
                "required": ["budget"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "Search for restaurants near the user's location that match their dietary needs and budget. Uses Google Places API and web search to find restaurants on Uber Eats, DoorDash, or Instacart with menu items and prices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dietary_preferences": {
                        "type": "string",
                        "description": "Summary of dietary restrictions and preferences"
                    },
                    "budget": {
                        "type": "string",
                        "description": "Budget constraints (e.g., 'under $25', 'moderate $20-30')"
                    },
                    "order_summary": {
                        "type": "string",
                        "description": "A summary of what the user wants to order"
                    }
                },
                "required": ["dietary_preferences", "budget", "order_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_for_confirmation_of_order",
            "description": "Ask the user for confirmation of the order",
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurant_name": {
                        "type": "string",
                        "description": "Name of the restaurant"
                    },
                    "restaurant_address": {
                        "type": "string",
                        "description": "Restaurant's full address"
                    },
                    "restaraunt_lat": {
                        "type": "number",
                        "description": "Latitude of the restaurant"
                    },
                    "restaraunt_lng": {
                        "type": "number",
                        "description": "Longitude of the restaurant"
                    },
                    "items": {
                        "type": "array",
                        "description": "List of menu items being ordered",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item": {
                                    "type": "string",
                                    "description": "Name of the menu item"
                                },
                                "price": {
                                    "type": "number",
                                    "description": "Price of the item in dollars"
                                },
                                "notes": {
                                    "type": "string",
                                    "description": "Any modifications or special requests"
                                }
                            },
                            "required": ["item", "price"]
                        }
                    },
                    "total_price": {
                        "type": "number",
                        "description": "Total price of all items in dollars (before delivery fees and tax)"
                    },
                    "delivery_platform": {
                        "type": "string",
                        "description": "Which platform to order from",
                        "enum": ["Uber Eats", "DoorDash", "Instacart"]
                    }
                },
                "required": ["restaurant_name", "restaurant_address", "restaraunt_lat", "restaraunt_lng", "items", "total_price", "delivery_platform"]
            }
        }
    }
]


if __name__ == "__main__":
    # Display the prompt for review
    print("=" * 80)
    print("RESTAURANT ORDERING SYSTEM PROMPT")
    print("=" * 80)
    print(RESTAURANT_ORDERING_SYSTEM_PROMPT)
    print("\n" + "=" * 80)
    print("FUNCTION DEFINITIONS")
    print("=" * 80)
    import json
    print(json.dumps(RESTAURANT_ORDERING_FUNCTIONS, indent=2))

