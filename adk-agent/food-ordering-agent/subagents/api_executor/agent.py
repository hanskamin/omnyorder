"""
API Executor Agent

This agent executes the generated order by sending it to an external API
and processes the response to provide feedback to the user.
"""

from google.adk.agents import LlmAgent
import os
from .tools import send_order_to_api, format_api_response

# Use Gemini model which supports tool use
GEMINI_MODEL = "gemini-2.0-flash-exp"

# Create the API executor agent
api_executor_agent = LlmAgent(
    name="APIExecutorAgent",
    model=GEMINI_MODEL,
    instruction="""You are an API Execution Agent for food ordering.

Your task is to take the generated order and execute it by sending it to the external API.

**Review the context:**

Order Details:
{order_details}

**Your task:**

1. Take the order_details JSON from the previous agent
2. Use the send_order_to_api tool to send the order to the external API
3. Wait for the API response
4. Use the format_api_response tool to format the response into a user-friendly message
5. Return EXACTLY the JSON output from format_api_response - do not modify, paraphrase, or rewrite it

**Important:**
- Always use the send_order_to_api tool first to execute the order
- Then use format_api_response to create a readable message
- Return the EXACT JSON string from format_api_response without any modifications
- Do NOT add any additional text, explanation, or formatting
- Do NOT interpret or paraphrase the JSON - return it as-is

**Example workflow:**
1. Receive order_details: {"budget": 25.0, "orders": [...]}
2. Call send_order_to_api(order_json=order_details)
3. Receive API response: {"success": true, "total_price": 2.19, ...}
4. Call format_api_response(api_response=response)
5. Return the exact JSON string from format_api_response

**Output:**
Return ONLY the JSON string from format_api_response tool, exactly as provided by the tool.
""",
    description="Executes orders by sending them to external API and returns formatted results to the user.",
    tools=[send_order_to_api, format_api_response],
    output_key="api_execution_result",
)
