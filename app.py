"""
FastAPI Voice Agent Backend
Real-time voice conversation with Deepgram Flux, OpenAI, and ElevenLabs TTS
"""

import asyncio
import json
import logging
import os
import struct
from datetime import datetime
from io import BytesIO
from typing import Dict, Any, List, Optional, Union
from enum import Enum

import openai
import websockets
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from deepgram import (
    DeepgramClient,
    SpeakWebSocketEvents,
    SpeakWSOptions,
)
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
from pydantic import BaseModel
from restaraunt_ordering_prompt import (
    RESTAURANT_ORDERING_SYSTEM_PROMPT,
    RESTAURANT_ORDERING_FUNCTIONS
)

load_dotenv()

# Configuration
FLUX_URL = "wss://api.deepgram.com/v2/listen"
FLUX_ENCODING = "linear16"
SAMPLE_RATE = 16000
OPENAI_LLM_MODEL = "gpt-4o"  # Changed to gpt-4o for function calling and web search support
DEEPGRAM_TTS_MODEL = "aura-2-phoebe-en"  # Kept for legacy compatibility
ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Adam voice (default)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Google ADK Configuration
GOOGLE_ADK_BASE_URL = os.getenv("GOOGLE_ADK_BASE_URL", "http://a8a249feb5a8.ngrok-free.app")
GOOGLE_ADK_ENDPOINT = f"{GOOGLE_ADK_BASE_URL}/run"
GOOGLE_ADK_APP_NAME = os.getenv("ADK_APP_NAME")
GOOGLE_ADK_USER_ID = os.getenv("ADK_USER_ID")

# Google Maps API Configuration
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GOOGLE_PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"

# OpenAI Client for restaurant search
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
elevenlabs = ElevenLabs(
    api_key=ELEVENLABS_API_KEY,
)
SYSTEM_PROMPT = RESTAURANT_ORDERING_SYSTEM_PROMPT

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose debug logs from external libraries
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('websockets.client').setLevel(logging.WARNING)
logging.getLogger('websockets.server').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# FastAPI app
app = FastAPI(title="Voice Agent API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session management
active_sessions: Dict[str, Dict[str, Any]] = {}


class ConversationState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


class TTSEvent(Enum):
    FLUSHED = "flushed"


# Pydantic models for structured restaurant output
class MenuItem(BaseModel):
    item: str
    price: float


class Restaurant(BaseModel):
    name: str
    address: str
    lat: float
    lng: float
    cuisine: str
    price_level: str
    rating: Optional[float] = None
    delivery_platforms: List[str]
    menu_items: List[MenuItem]
    reasoning: str


class RestaurantRecommendations(BaseModel):
    recommendations: List[Restaurant]
    search_summary: str


def search_restaurants_with_google_places(location: str, query: str) -> Optional[dict]:
    """
    Search for restaurants using Google Places API.
    
    Args:
        location: Location dict with lat, lng, radius
        query: Search query (e.g., "vegetarian restaurants")
    
    Returns:
        Google Places API response data
    """
    if not GOOGLE_MAPS_API_KEY:
        logger.error("GOOGLE_MAPS_API_KEY not configured")
        return None
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.priceLevel,places.rating,places.websiteUri,places.nationalPhoneNumber,places.types,places.userRatingCount"
    }
    
    body = {
        "textQuery": query,
        "languageCode": "en"
    }
    
    try:
        response = requests.post(GOOGLE_PLACES_API_URL, headers=headers, json=body)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Google Places API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error calling Google Places API: {e}")
        return None


def search_restaurants_with_web_search(
    places_data: dict,
    dietary_preferences: str,
    budget: str,
    cuisine_preference: str = "any"
) -> Optional[RestaurantRecommendations]:
    """
    Use OpenAI with web search to find menu items and delivery availability.
    """
    # Extract restaurant names and basic info from Places API
    restaurants_info = []
    
    if "places" in places_data:
        for place in places_data["places"][:10]:  # Limit to top 10
            name = place.get("displayName", {}).get("text", "Unknown")
            location = place.get("location", {})
            restaurant_data = {
                "name": name,
                "address": place.get("formattedAddress", ""),
                "lat": location.get("latitude", 0.0),
                "lng": location.get("longitude", 0.0),
                "phone": place.get("nationalPhoneNumber", ""),
                "website": place.get("websiteUri", ""),
                "price_level": place.get("priceLevel", "PRICE_LEVEL_UNSPECIFIED"),
                "rating": place.get("rating", 0)
            }
            restaurants_info.append(restaurant_data)
    
    # Create prompt for OpenAI
    prompt = f"""I need you to research these restaurants and find out:
1. What menu items they have that match these dietary preferences: {dietary_preferences}
2. Whether they're available on Uber Eats, DoorDash, or Instacart
3. Specific menu items with prices (if available)
4. Why each restaurant is a good match

CRITICAL REQUIREMENTS:
- ONLY include restaurants that are available on at least ONE of these platforms: Uber Eats, DoorDash, or Instacart
- If a restaurant is NOT available on any delivery platform, DO NOT include it in the recommendations
- You must verify delivery availability through web search

Dietary preferences: {dietary_preferences}
Budget: {budget}
Cuisine preference: {cuisine_preference}

Restaurants to research:
{json.dumps(restaurants_info, indent=2)}

Use web search to find:
1. Current menu information and prices
2. Delivery platform availability (Uber Eats, DoorDash, Instacart)

Remember: Only recommend restaurants available on at least one delivery platform AND that match the dietary preferences and budget.
Be specific about menu items and prices you find."""

    logger.info("Calling OpenAI with web search for restaurant research...")
    
    try:
        # First, get the web search results using gpt-4o-search-preview
        completion = openai_client.chat.completions.create(
            model="gpt-4o-search-preview",
            web_search_options={},
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful restaurant research assistant. Use web search to find accurate, current information about restaurants, their menus, prices, and delivery availability."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        web_search_result = completion.choices[0].message.content
        logger.info("Web search completed!")
        
        # Now use the web search results with structured output
        formatting_prompt = f"""Based on this research, format the restaurant recommendations into the required structure.

IMPORTANT: Use the EXACT data from the original Google Places information for these fields:
- name, address, lat, lng, rating (use exact values from original data)
- For price_level, convert Google's PRICE_LEVEL_* to symbols: INEXPENSIVE="$", MODERATE="$$", EXPENSIVE="$$$", VERY_EXPENSIVE="$$$$"
- For menu_items, use format: {{"item": "name", "price": float}}
- For delivery_platforms, create a list like ["Uber Eats", "DoorDash"] with only the platforms that are available
- For reasoning, explain why this restaurant matches the user's dietary preferences and budget

Original Google Places Data:
{json.dumps(restaurants_info, indent=2)}

Web Search Research Results:
{web_search_result}

CRITICAL: Only include restaurants that have at least ONE delivery platform available. If delivery_platforms list is empty, DO NOT include that restaurant."""

        structured_completion = openai_client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that formats restaurant information into structured JSON. Always preserve exact data from the original source when provided."
                },
                {
                    "role": "user",
                    "content": formatting_prompt
                }
            ],
            response_format=RestaurantRecommendations
        )
        
        result = structured_completion.choices[0].message.parsed
        logger.info("Structured output generated!")
        
        # Filter out any restaurants without delivery platform availability (safety check)
        filtered_recommendations = [
            r for r in result.recommendations
            if r.delivery_platforms and len(r.delivery_platforms) > 0
        ]
        
        result.recommendations = filtered_recommendations
        logger.info(f"Final count: {len(filtered_recommendations)} restaurants with delivery available")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in restaurant search with web search: {e}", exc_info=True)
        return None


def call_google_adk_agent(message: str, session_id: str) -> Optional[str]:
    """
    Call Google ADK food ordering agent and extract voice agent response.
    
    Args:
        message: The user's message text
        session_id: Session ID for maintaining conversation context
    
    Returns:
        The voice agent's message text, or None if failed
    """
    # try:
    #     payload = {
    #         "app_name": GOOGLE_ADK_APP_NAME,
    #         "user_id": GOOGLE_ADK_USER_ID,
    #         "session_id": session_id,
    #         "new_message": {
    #             "parts": [{"text": message}],
    #             "role": "user"
    #         },
    #         "streaming": False
    #     }
        
    #     response = requests.post(
    #         GOOGLE_ADK_ENDPOINT,
    #         json=payload,
    #         headers={"Content-Type": "application/json", "Accept": "application/json"},
    #         timeout=120  # 2 minute timeout for order processing
    #     )
        
    #     if response.status_code != 200:
    #         logger.error(f"Google ADK request failed with status {response.status_code}")
    #         return None
        
    #     # Parse response and extract voice_agent_message
    #     response_data = response.json()
        
    #     if isinstance(response_data, list):
    #         for item in reversed(response_data):
    #             if "actions" in item and "state_delta" in item["actions"]:
    #                 state_delta = item["actions"]["state_delta"]
    #                 if "api_execution_result" in state_delta:
    #                     try:
    #                         result_json = json.loads(
    #                             state_delta["api_execution_result"]
    #                             .replace("```json\n", "")
    #                             .replace("\n```", "")
    #                         )
    #                         if "voice_agent_message" in result_json:
    #                             return result_json["voice_agent_message"]
    #                     except Exception as e:
    #                         logger.error(f"Error parsing ADK response: {e}")
    #                         continue
        
    #     logger.warning("Could not extract voice agent message from Google ADK response")
    #     return None
        
    # except Exception as e:
    #     logger.error(f"Error calling Google ADK: {e}")
    #     return None
    return "Hi, I just placed your order have a great day!"


# Mock function handlers for restaurant ordering
async def handle_store_dietary_preferences(preferences: str, websocket: WebSocket, session_id: str) -> dict:
    logger.info(f"Session {session_id}: Storing dietary preferences: {preferences}")
    
    # Mock response
    result = {
        'success': True,
        'message': 'Dietary preferences stored successfully',
        'preferences': preferences
    }
    
    await websocket.send_json({
        'type': 'function_call',
        'function': 'store_dietary_preferences',
        'status': 'completed',
        'result': result,
        'timestamp': datetime.now().isoformat()
    })

    await asyncio.sleep(0)
    
    return result


async def handle_store_budget_info(budget: str, websocket: WebSocket, session_id: str) -> dict:
    """Mock handler for storing budget information"""
    logger.info(f"Session {session_id}: Storing budget info: {budget}")
    
    result = {
        'success': True,
        'message': 'Budget information stored successfully',
        'budget': budget
    }
    
    await websocket.send_json({
        'type': 'function_call',
        'function': 'store_budget_info',
        'status': 'completed',
        'result': result,
        'timestamp': datetime.now().isoformat()
    })
    await asyncio.sleep(0)
    
    return result


async def handle_search_restaurants(dietary_preferences: str, budget: str, order_summary: str, websocket: WebSocket, session_id: str) -> dict:
    """Real handler for searching restaurants using Google Places + OpenAI web search"""
    logger.info(f"Session {session_id}: Searching restaurants - Dietary: {dietary_preferences}, Budget: {budget}, Order: {order_summary}")
    
    
    try:
        # Step 1: Search Google Places API
        # Default to Austin, TX location - in production, should get user's location
        await websocket.send_json({
            'type': 'system_response',
            'response': f'Searching restaurants with query: {order_summary}',
            'timestamp': datetime.now().isoformat()
        })
        await asyncio.sleep(0.3)
        places_data = search_restaurants_with_google_places(location="Austin, TX", query=order_summary)
        restaurants_info = []
        for place in places_data["places"][:10]:  # Limit to top 10
            name = place.get("displayName", {}).get("text", "Unknown")
            location = place.get("location", {})
            restaurant_data = {
                "name": name,
                "address": place.get("formattedAddress", ""),
                "lat": location.get("latitude", 0.0),
                "lng": location.get("longitude", 0.0),
                "phone": place.get("nationalPhoneNumber", ""),
                "website": place.get("websiteUri", ""),
                "price_level": place.get("priceLevel", "PRICE_LEVEL_UNSPECIFIED"),
                "rating": place.get("rating", 0)
            }
            restaurants_info.append(restaurant_data)
        result = {
            'success': True,
            'restaurants': restaurants_info,
            'count': len(places_data),
            'summary': 'Restaurants found in your area'
        }
        await websocket.send_json({
            'type': 'function_call',
            'function': 'search_restaurants',
            'status': 'completed',
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
        await asyncio.sleep(0.3)
        if not places_data or "places" not in places_data:
            logger.error("No places found from Google Places API")
            result = {
                'success': False,
                'error': 'No restaurants found in your area',
                'restaurants': [],
                'count': 0
            }
        else:
            # Step 2: Use OpenAI web search to research menus and delivery
            recommendations = search_restaurants_with_web_search(
                places_data=places_data,
                dietary_preferences=dietary_preferences,
                budget=budget,
                cuisine_preference=order_summary
            )

            
            
            if recommendations and recommendations.recommendations:
                # Convert Pydantic models to dicts for JSON serialization
                restaurants = [r.model_dump() for r in recommendations.recommendations]
                
                result = {
                    'success': True,
                    'restaurants': restaurants,
                    'count': len(restaurants),
                    'summary': recommendations.search_summary
                }
            else:
                logger.warning("No restaurants matched criteria after web search")
                result = {
                    'success': False,
                    'error': 'No restaurants found matching your preferences with delivery available',
                    'restaurants': [],
                    'count': 0
                }
        
        await websocket.send_json({
            'type': 'function_call',
            'function': 'pick_restaurants',
            'status': 'completed',
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Error in handle_search_restaurants: {e}", exc_info=True)
        result = {
            'success': False,
            'error': str(e),
            'restaurants': [],
            'count': 0
        }
        
        await websocket.send_json({
            'type': 'function_call',
            'function': 'search_restaurants',
            'status': 'error',
            'result': result,
            'timestamp': datetime.now().isoformat()
        })

        await asyncio.sleep(0)
        
        return result


async def handle_confirm_order(restaurant_name: str, restaurant_address: str, restaraunt_lat: float, restaraunt_lng: float, items: list, total_price: float, delivery_platform: str, order_summary: str, websocket: WebSocket, session_id: str) -> dict:
    """Mock handler for confirming order"""
    logger.info(f"Session {session_id}: Confirming order at {restaurant_name}")
    
    await websocket.send_json({
        'type': 'function_call',
        'function': 'confirm_order',
        'status': 'executing',
        'data': {
            'restaurant_name': restaurant_name,
            'restaurant_address': restaurant_address,
            'items': items,
            'total_price': total_price,
            'delivery_platform': delivery_platform,
            'order_summary': order_summary
        },
        'timestamp': datetime.now().isoformat()
    })
    
    
    result = {
        'success': True,
        'restaurant': {
            'name': restaurant_name,
            'address': restaurant_address,
            'lat': restaraunt_lat,
            'lng': restaraunt_lng,
            'order_summary': order_summary
        },
        'items': items,
        'total_price': total_price,
        'delivery_platform': delivery_platform,
        'estimated_delivery': '30-45 minutes',
        'order_summary': order_summary
    }
    
    await websocket.send_json({
        'type': 'function_call',
        'function': 'confirm_order',
        'status': 'completed',
        'result': result,
        'timestamp': datetime.now().isoformat()
    })
    await asyncio.sleep(0)
    
    return result


async def generate_agent_reply(
    messages: List[Dict[str, str]],
    user_speech: str,
    session_id: str,
    config: Dict[str, Any],
    websocket: WebSocket
) -> Optional[tuple[str, bytes, dict]]:
    """Generate agent reply using OpenAI with function calling and TTS."""
    
    logger.info(f"Session {session_id}: Generating reply for: '{user_speech}'")
    
    try:
        # Set up OpenAI client
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Prepare messages
        llm_messages = messages.copy()
        llm_messages.append({"role": "user", "content": user_speech})
        final_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + llm_messages
        
        # Function calling loop
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        ui_update = None
        print(f"final messages: {final_messages}")
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Session {session_id}: LLM call iteration {iteration}")
            # Call OpenAI with function calling enabled
            response = openai_client.chat.completions.create(
                model=config['llm_model'],
                messages=final_messages,
                temperature=0.3,
                tools=RESTAURANT_ORDERING_FUNCTIONS,
                tool_choice="auto"
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            # If no function calls, we have the final response
            if not tool_calls:
                agent_message = response_message.content
                logger.info(f"Session {session_id}: Final response: '{agent_message}'")
                
                # Generate TTS audio
                tts_audio = await generate_tts_audio(agent_message, session_id, config)
                return agent_message, tts_audio, ui_update
            
            # Add assistant's response with tool calls to messages
            final_messages.append({
                "role": "assistant",
                "content": response_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in tool_calls
                ]
            })
            
            # Process each tool call
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Session {session_id}: Calling function: {function_name} with args: {function_args}")
                
                # Execute the appropriate function
                function_result = None
                
                if function_name == "store_dietary_preferences":
                    function_result = await handle_store_dietary_preferences(
                        preferences=function_args.get("preferences", ""),
                        websocket=websocket,
                        session_id=session_id
                    )
                
                elif function_name == "store_budget_info":
                    function_result = await handle_store_budget_info(
                        budget=function_args.get("budget", ""),
                        websocket=websocket,
                        session_id=session_id
                    )
                
                elif function_name == "search_restaurants":
                    function_result = await handle_search_restaurants(
                        dietary_preferences=function_args.get("dietary_preferences", ""),
                        budget=function_args.get("budget", ""),
                        order_summary=function_args.get("order_summary", ""),
                        websocket=websocket,
                        session_id=session_id
                    )
                    # Store UI update for restaurant search results
                    if function_result and 'restaurants' in function_result:
                        ui_update = {'restaurants': function_result['restaurants']}
                
                elif function_name == "ask_for_confirmation_of_order":
                    function_result = await handle_confirm_order(
                        restaurant_name=function_args.get("restaurant_name", ""),
                        restaurant_address=function_args.get("restaurant_address", ""),
                        restaraunt_lat=function_args.get("restaraunt_lat", 0.0),
                        restaraunt_lng=function_args.get("restaraunt_lng", 0.0),
                        items=function_args.get("items", []),
                        total_price=function_args.get("total_price", 0.0),
                        delivery_platform=function_args.get("delivery_platform", ""),
                        websocket=websocket,
                        session_id=session_id,
                        order_summary=function_args.get("order_summary", "")
                    )
                
                # Add function result to messages
                final_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_result)
                })
                session = active_sessions[session_id]
        
        logger.warning(f"Session {session_id}: Max iterations reached")
        return "I apologize, but I'm having trouble processing your request. Let's start over.", None, None
        
    except Exception as e:
        logger.error(f"Session {session_id}: Error generating reply: {e}", exc_info=True)
        return None


async def generate_tts_audio(text: str, session_id: str, config: Dict[str, Any]) -> Optional[bytes]:
    """Generate TTS audio using ElevenLabs."""
    
    logger.info(f"Session {session_id}: Generating TTS for: '{text}'")
    
    try:
        # Run the blocking ElevenLabs API call in a thread pool
        loop = asyncio.get_running_loop()
        
        def text_to_speech_stream(text: str) -> BytesIO:
            """Perform text-to-speech conversion using ElevenLabs."""
            # Get voice_id from config or use default (Adam)
            voice_id = config.get('elevenlabs_voice_id', 'pNInz6obpgDQGcFmaJgB')
            
            # Perform the text-to-speech conversion
            response = elevenlabs.text_to_speech.convert(
                voice_id=voice_id,
                output_format="mp3_22050_32",
                text=text,
                model_id="eleven_multilingual_v2",
                # Optional voice settings for customization
                voice_settings=VoiceSettings(
                    stability=0.0,
                    similarity_boost=1.0,
                    style=0.0,
                    use_speaker_boost=True,
                    speed=1.0,
                ),
            )
            
            # Create a BytesIO object to hold the audio data in memory
            audio_stream = BytesIO()
            
            # Write each chunk of audio data to the stream
            for chunk in response:
                if chunk:
                    audio_stream.write(chunk)
            
            # Reset stream position to the beginning
            audio_stream.seek(0)
            
            return audio_stream
        
        # Run the blocking call in a thread pool
        audio_stream = await loop.run_in_executor(None, text_to_speech_stream, text)
        
        # Get the audio bytes
        audio_bytes = audio_stream.getvalue()
        
        if audio_bytes:
            logger.info(f"Session {session_id}: TTS complete: {len(audio_bytes)} bytes (MP3)")
            return audio_bytes
        
        return None
        
    except Exception as e:
        logger.error(f"Session {session_id}: TTS exception: {e}")
        return None


async def connect_to_flux(session_id: str, websocket: WebSocket):
    """Connect to Deepgram Flux and handle conversation."""
    
    session = active_sessions[session_id]
    config = session['config']
    
    flux_url = f"{FLUX_URL}?model=flux-general-en&sample_rate={config['sample_rate']}&encoding={FLUX_ENCODING}"
    headers = {
        'Authorization': f'Token {DEEPGRAM_API_KEY}',
    }
    
    try:
        async with websockets.connect(flux_url, additional_headers=headers) as flux_ws:
            session['flux_ws'] = flux_ws
            logger.info(f"Session {session_id}: Connected to Flux")
            
            # Handle Flux responses
            async def handle_flux_messages():
                async for message in flux_ws:
                    try:
                        data = json.loads(message)
                        
                        # Forward event to client
                        await websocket.send_json({
                            'type': 'flux_event',
                            'data': data
                        })
                        
                        # Handle specific events
                        if data.get('type') == 'TurnInfo':
                            event = data.get('event')
                            
                            if event == 'StartOfTurn':
                                await websocket.send_json({
                                    'type': 'speech_started',
                                    'timestamp': datetime.now().isoformat()
                                })
                            
                            elif event == 'EndOfTurn':
                                transcript = data.get('transcript', '').strip()
                                if transcript:
                                    logger.info(f"Session {session_id}: User said: '{transcript}'")
                                    
                                    # Add to history
                                    session['messages'].append({"role": "user", "content": transcript})
                                    
                                    # Send transcript to client
                                    await websocket.send_json({
                                        'type': 'user_speech',
                                        'transcript': transcript,
                                        'timestamp': datetime.now().isoformat()
                                    })
                                    
                                    # Generate response
                                    await websocket.send_json({
                                        'type': 'agent_processing',
                                        'timestamp': datetime.now().isoformat()
                                    })
                                    
                                    result = await generate_agent_reply(
                                        session['messages'],
                                        transcript,
                                        session_id,
                                        config,
                                        websocket
                                    )
                                    session['messages'].append({"role": "assistant", "content": result[0]})
                                    
                                    if result:
                                        agent_text, audio_data, ui_update = result
                                        if ui_update:
                                            await websocket.send_json({
                                                'type': 'ui_update',
                                                'response': ui_update,
                                                'timestamp': datetime.now().isoformat()
                                            })
                                        # Send text response
                                        await websocket.send_json({
                                            'type': 'agent_response',
                                            'response': agent_text,
                                            'timestamp': datetime.now().isoformat()
                                        })
                                        
                                        # Send audio
                                        if audio_data:
                                            await websocket.send_json({
                                                'type': 'agent_speaking',
                                                'audio': list(audio_data),
                                                'timestamp': datetime.now().isoformat()
                                            })
                            
                            elif event == 'Update':
                                transcript = data.get('transcript', '').strip()
                                if transcript:
                                    await websocket.send_json({
                                        'type': 'interim_transcript',
                                        'transcript': transcript,
                                        'is_final': False
                                    })
                    
                    except json.JSONDecodeError as e:
                        logger.error(f"Session {session_id}: Invalid JSON: {e}")
                    except Exception as e:
                        logger.error(f"Session {session_id}: Error processing message: {e}")
            
            # Send audio to Flux
            async def send_audio():
                try:
                    while session.get('conversation_active'):
                        if 'audio_buffer' in session and session['audio_buffer']:
                            audio_bytes = session['audio_buffer'].pop(0)
                            await flux_ws.send(audio_bytes)
                        await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"Session {session_id}: Error sending audio: {e}")
            
            # Run both tasks
            await asyncio.gather(
                handle_flux_messages(),
                send_audio()
            )
            
    except Exception as e:
        logger.error(f"Session {session_id}: Flux connection error: {e}")
        await websocket.send_json({
            'type': 'error',
            'error': f'Failed to connect to Flux: {str(e)}'
        })


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """Main WebSocket endpoint for voice agent."""
    
    await websocket.accept()
    session_id = id(websocket)
    
    logger.info(f"Client connected: {session_id}")
    
    # Initialize session
    active_sessions[session_id] = {
        'state': ConversationState.IDLE,
        'messages': [],
        'config': {
            'sample_rate': SAMPLE_RATE,
            'llm_model': OPENAI_LLM_MODEL,
            'tts_model': DEEPGRAM_TTS_MODEL,  # Legacy field
            'elevenlabs_voice_id': ELEVENLABS_VOICE_ID,  # Now using ElevenLabs
        },
        'conversation_active': False,
        'audio_buffer': [],
    }
    
    try:
        await websocket.send_json({
            'type': 'connected',
            'session_id': str(session_id)
        })
        
        while True:
            try:
                data = await websocket.receive()
                
                # Handle text messages (commands)
                if 'text' in data:
                    message = json.loads(data['text'])
                    msg_type = message.get('type')
                    
                    if msg_type == 'start_conversation':
                        logger.info(f"Session {session_id}: Starting conversation")
                        session = active_sessions[session_id]
                        session['conversation_active'] = True
                        session['messages'] = []
                        
                        await websocket.send_json({
                            'type': 'conversation_started',
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        # Start Flux connection
                        asyncio.create_task(connect_to_flux(session_id, websocket))
                    
                    elif msg_type == 'stop_conversation':
                        logger.info(f"Session {session_id}: Stopping conversation")
                        session = active_sessions[session_id]
                        session['conversation_active'] = False
                        
                        await websocket.send_json({
                            'type': 'conversation_stopped',
                            'timestamp': datetime.now().isoformat()
                        })
                    elif msg_type == 'confirmed_order':
                        session['messages'].append({"role": "user", "content": "USER HAS CLICKED CONFIRM ORDER"})
                        config = session['config']
                        result = await generate_agent_reply(
                                        session['messages'],
                                        'USER HAS CLICKED CONFIRM ORDER',
                                        session_id,
                                        config,
                                        websocket
                                    )
                        session['messages'].append({"role": "assistant", "content": result[0]})
                                    
                        if result:
                            agent_text, audio_data, ui_update = result
                            if ui_update:
                                await websocket.send_json({
                                    'type': 'ui_update',
                                    'response': ui_update,
                                    'timestamp': datetime.now().isoformat()
                                })
                            # Send text response
                            await websocket.send_json({
                                'type': 'agent_response',
                                'response': agent_text,
                                'timestamp': datetime.now().isoformat()
                            })
                            
                            # Send audio
                            if audio_data:
                                await websocket.send_json({
                                    'type': 'agent_speaking',
                                    'audio': list(audio_data),
                                    'timestamp': datetime.now().isoformat()
                                })
                    
                    elif msg_type == 'update_config':
                        config_data = message.get('config', {})
                        active_sessions[session_id]['config'].update(config_data)
                        logger.info(f"Session {session_id}: Config updated")
                    
                    elif msg_type == 'confirmed_order':
                        logger.info(f"Session {session_id}: Confirmed order message received")
                        session['messages'].append({"role": "user", "content": "USER HAS CLICKED CONFIRM ORDER"})
                        config = session['config']

                        order_message = message.get('message', '')
                        
                        if not order_message:
                            await websocket.send_json({
                                'type': 'error',
                                'error': 'No message provided in confirmed_order'
                            })
                        else:
                            result = await generate_agent_reply(
                                        session['messages'],
                                        'USER HAS CLICKED CONFIRM ORDER',
                                        session_id,
                                        config,
                                        websocket
                                    )
                        session['messages'].append({"role": "assistant", "content": result[0]})
                                    
                        if result:
                            agent_text, audio_data = result
                            # Send text response
                            await websocket.send_json({
                                'type': 'agent_response',
                                'response': agent_text,
                                'timestamp': datetime.now().isoformat()
                            })
                            
                            # Send audio
                            if audio_data:
                                await websocket.send_json({
                                    'type': 'agent_speaking',
                                    'audio': list(audio_data),
                                    'timestamp': datetime.now().isoformat()
                                })

                            await asyncio.sleep(1)
                            # Call Google ADK agent
                            adk_response = call_google_adk_agent(
                                message=order_message,
                                session_id=str(session_id)
                            )
                            
                            if adk_response:
                                # Send the voice agent's response
                                await websocket.send_json({
                                    'type': 'order_response',
                                    'response': adk_response,
                                    'timestamp': datetime.now().isoformat()
                                })
                                
                                # Generate TTS for the response
                                config = active_sessions[session_id]['config']
                                tts_audio = await generate_tts_audio(adk_response, str(session_id), config)
                                
                                if tts_audio:
                                    await websocket.send_json({
                                        'type': 'order_speaking',
                                        'audio': list(tts_audio),
                                        'timestamp': datetime.now().isoformat()
                                    })
                            else:
                                await websocket.send_json({
                                    'type': 'error',
                                    'error': 'Failed to get response from ordering agent',
                                    'timestamp': datetime.now().isoformat()
                                })
                
                # Handle binary messages (audio data)
                elif 'bytes' in data:
                    session = active_sessions.get(session_id)
                    if session and session['conversation_active']:
                        audio_bytes = data['bytes']
                        session['audio_buffer'].append(audio_bytes)
            
            except WebSocketDisconnect:
                logger.info(f"Session {session_id}: Client disconnected")
                break
            except Exception as e:
                logger.error(f"Session {session_id}: Error: {e}")
                await websocket.send_json({
                    'type': 'error',
                    'error': str(e)
                })
    
    finally:
        # Cleanup
        if session_id in active_sessions:
            active_sessions[session_id]['conversation_active'] = False
            del active_sessions[session_id]
        logger.info(f"Session {session_id}: Cleaned up")




@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Voice Agent API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

