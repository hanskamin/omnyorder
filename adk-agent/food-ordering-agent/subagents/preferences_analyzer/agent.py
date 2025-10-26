"""
Preferences Analyzer Agent

This agent analyzes user preferences, dietary restrictions, and budget
from the user's request and knowledge base.
"""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
import os
# --- Constants ---
# GEMINI_MODEL = "gemini-2.0-flash"

# https://docs.litellm.ai/docs/providers/openrouter
model = LiteLlm(
    model="openrouter/nvidia/llama-3.1-nemotron-ultra-253b-v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Create the preferences analyzer agent
preferences_analyzer_agent = LlmAgent(
    name="PreferencesAnalyzerAgent",
   #  model=GEMINI_MODEL,
    model=model,
    instruction="""You are a Preferences Analysis AI for food ordering.
    
    Analyze the user's request and extract the following information:
    
    1. **Budget**: Extract any budget constraints mentioned (e.g., "$20", "under $50", "cheap", "expensive")
       - If not mentioned, output "Not specified"
    
    2. **Dietary Restrictions**: Identify all dietary restrictions or preferences mentioned
       - Examples: vegan, vegetarian, keto, low-carb, high-protein, low-calorie, gluten-free, etc.
       - If not mentioned, output "None"
    
    3. **Order Type**: Classify the order type
       - "ready-made" for prepared food (smoothies, tacos, restaurant meals)
       - "groceries" for ingredients to cook at home
       - "mixed" if both are needed
    
    4. **Special Requirements**: Any other preferences like favorite restaurants, specific ingredients, etc.
       - If not mentioned, output "None"
    
    5. **Number of People**: How many people is this order for?
       - If not mentioned, output "1"
    
    Format your output as:
    Budget: [budget]
    Dietary Restrictions: [restrictions]
    Order Type: [type]
    Special Requirements: [requirements]
    Number of People: [number]
    
    Example output:
    Budget: Not specified
    Dietary Restrictions: Vegan, Low-calorie
    Order Type: ready-made
    Special Requirements: None
    Number of People: 2
    """,
    description="Analyzes user preferences, dietary restrictions, and budget from the request.",
    output_key="preferences_analysis",
)
