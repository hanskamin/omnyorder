"""
Platform Selector Agent

This agent determines the best platform(s) (Uber Eats, DoorDash, or Instacart)
based on the order type and preferences. Can select multiple platforms for mixed orders.
"""

from google.adk.agents import LlmAgent
import os
from google.adk.models.lite_llm import LiteLlm

# --- Constants ---
# GEMINI_MODEL = "gemini-2.0-flash"

# https://docs.litellm.ai/docs/providers/openrouter
model = LiteLlm(
    model="openrouter/nvidia/llama-3.1-nemotron-ultra-253b-v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Create the platform selector agent
platform_selector_agent = LlmAgent(
    name="PlatformSelectorAgent",
   #  model=GEMINI_MODEL,
    model=model,
    instruction="""You are a Platform Selection AI for food ordering.
    
    Based on the preferences analysis, select the most appropriate platform(s).
    You can select MULTIPLE platforms if the order contains both groceries and ready-made food.
    
    **Platform Selection Rules:**
    
    1. **Instacart**: Best for groceries and ingredients
       - Use when order type is "groceries"
       - Use when user wants to cook at home
       - Use for ingredients, produce, pantry items
    
    2. **Uber Eats or DoorDash**: Best for ready-made food
       - Use when order type is "ready-made"
       - Use for restaurant meals, smoothies, prepared foods
       - Choose based on availability and user preference if mentioned
    
    3. **Mixed Orders**: If order type is "mixed", select MULTIPLE platforms
       - Select "Uber Eats" (or "DoorDash") for ready-made food items
       - Select "Instacart" for grocery/ingredient items
       - List each platform with what it will be used for
    
    Review the preferences analysis:
    {preferences_analysis}
    
    **Output Format:**
    
    For single platform orders:
    Platform: [Platform Name]
    Reason: [Brief reason]
    
    For mixed orders with multiple platforms:
    Platforms:
    - [Platform 1]: [What items/purpose]
    - [Platform 2]: [What items/purpose]
    
    **Examples:**
    
    Single platform (groceries):
    Platform: Instacart
    Reason: User needs groceries for cooking butter chicken
    
    Single platform (ready-made):
    Platform: Uber Eats
    Reason: User wants ready-made smoothie
    
    Multiple platforms (mixed order):
    Platforms:
    - Uber Eats: For ready-made lunch (tacos, smoothie)
    - Instacart: For groceries (ingredients for dinner)
    """,
    description="Selects the best platform(s) (Uber Eats, DoorDash, or Instacart) based on order type. Can select multiple platforms for mixed orders.",
    output_key="platform_selection",
)
