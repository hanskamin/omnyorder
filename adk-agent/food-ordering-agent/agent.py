"""
Food Ordering Sequential Agent

This agent orchestrates a food ordering pipeline that analyzes user preferences,
selects the appropriate platform, and generates a complete order.
"""

from google.adk.agents import SequentialAgent

# Import the subagents
from .subagents.order_generator import order_generator_agent
from .subagents.platform_selector import platform_selector_agent
from .subagents.preferences_analyzer import preferences_analyzer_agent
from .subagents.api_executor import api_executor_agent

# Create the sequential agent
root_agent = SequentialAgent(
    name="FoodOrderingPipeline",
    sub_agents=[
        preferences_analyzer_agent,
        platform_selector_agent,
        order_generator_agent,
        api_executor_agent,
    ],
    description="A pipeline that analyzes preferences, selects platform, generates food orders, and executes them via external API from Uber Eats, DoorDash, or Instacart",
)
