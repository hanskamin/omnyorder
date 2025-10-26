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

load_dotenv()

# Configuration
FLUX_URL = "wss://api.deepgram.com/v2/listen"
FLUX_ENCODING = "linear16"
SAMPLE_RATE = 16000
OPENAI_LLM_MODEL = "gpt-4o-mini"
DEEPGRAM_TTS_MODEL = "aura-2-phoebe-en"  # Kept for legacy compatibility
ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Adam voice (default)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
elevenlabs = ElevenLabs(
    api_key=ELEVENLABS_API_KEY,
)
SYSTEM_PROMPT = """You are a helpful voice assistant powered by Deepgram Flux, OpenAI, and ElevenLabs.
You should:
- Keep responses conversational and natural
- Be concise but helpful
- Respond as if you're having a real-time voice conversation
- Ask follow-up questions when appropriate
- Be friendly and engaging

The user is speaking to you via voice, so respond naturally as if in a live conversation."""

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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


async def generate_agent_reply(
    messages: List[Dict[str, str]],
    user_speech: str,
    session_id: str,
    config: Dict[str, Any]
) -> Optional[tuple[str, bytes]]:
    """Generate agent reply using OpenAI and TTS."""
    
    logger.info(f"Session {session_id}: Generating reply for: '{user_speech}'")
    
    try:
        # Set up OpenAI client
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Prepare messages
        llm_messages = messages.copy()
        llm_messages.append({"role": "user", "content": user_speech})
        final_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + llm_messages
        
        # Call OpenAI
        response = openai_client.chat.completions.create(
            model=config['llm_model'],
            messages=final_messages,
            temperature=0.7,
            max_tokens=150
        )
        
        agent_message = response.choices[0].message.content
        logger.info(f"Session {session_id}: Generated response: '{agent_message}'")
        
        # Generate TTS audio
        tts_audio = await generate_tts_audio(agent_message, session_id, config)
        ui_update = {
            "restaraunts": [
                {
                    "name": "Restaurant 1",
                    "lat": 30.3108,
                    "lng": 97.7400,
                },
            ]
        }
        return agent_message, tts_audio, ui_update
        
    except Exception as e:
        logger.error(f"Session {session_id}: Error generating reply: {e}")
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
                        logger.debug(f"Session {session_id}: Flux event: {data}")
                        
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
                                        config
                                    )
                                    
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
                    audio_count = 0
                    while session.get('conversation_active'):
                        if 'audio_buffer' in session and session['audio_buffer']:
                            audio_bytes = session['audio_buffer'].pop(0)
                            await flux_ws.send(audio_bytes)
                            audio_count += 1
                            if audio_count % 10 == 0:  # Log every 10th chunk
                                logger.debug(f"Session {session_id}: Sent {audio_count} audio chunks to Flux")
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
                    
                    elif msg_type == 'update_config':
                        config_data = message.get('config', {})
                        active_sessions[session_id]['config'].update(config_data)
                        logger.info(f"Session {session_id}: Config updated")
                
                # Handle binary messages (audio data)
                elif 'bytes' in data:
                    session = active_sessions.get(session_id)
                    if session and session['conversation_active']:
                        audio_bytes = data['bytes']
                        session['audio_buffer'].append(audio_bytes)
                        logger.debug(f"Session {session_id}: Received {len(audio_bytes)} bytes of audio, buffer size: {len(session['audio_buffer'])}")
            
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


@app.post("/webhook")
async def webhook(request: dict):
    """Simple webhook endpoint to receive data."""
    logger.info(f"Webhook received: {request}")
    
    # You can add your webhook logic here
    # For example, process the data, trigger actions, etc.
    
    return {
        "status": "success",
        "message": "Webhook received",
        "received_data": request
    }


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Voice Agent API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

