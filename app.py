"""
FastAPI Voice Agent Backend
Real-time voice conversation with Deepgram Flux, OpenAI, and TTS
"""

import asyncio
import json
import logging
import os
import struct
from datetime import datetime
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
from dotenv import load_dotenv

load_dotenv()

# Configuration
FLUX_URL = "wss://api.deepgram.com/v2/listen"
FLUX_ENCODING = "linear16"
SAMPLE_RATE = 16000
OPENAI_LLM_MODEL = "gpt-4o-mini"
DEEPGRAM_TTS_MODEL = "aura-2-phoebe-en"
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SYSTEM_PROMPT = """You are a helpful voice assistant powered by Deepgram Flux and OpenAI.
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
        
        return agent_message, tts_audio
        
    except Exception as e:
        logger.error(f"Session {session_id}: Error generating reply: {e}")
        return None


async def generate_tts_audio(text: str, session_id: str, config: Dict[str, Any]) -> Optional[bytes]:
    """Generate TTS audio using Deepgram."""
    
    logger.info(f"Session {session_id}: Generating TTS for: '{text}'")
    
    try:
        dg_tts_ws = DeepgramClient(api_key=DEEPGRAM_API_KEY).speak.websocket.v("1")
        audio_queue: asyncio.Queue[Union[bytes, TTSEvent]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        
        # Event handlers
        def on_binary_data(self, data, **kwargs):
            asyncio.run_coroutine_threadsafe(audio_queue.put(data), loop)
        
        def on_flushed(self, **kwargs):
            asyncio.run_coroutine_threadsafe(audio_queue.put(TTSEvent.FLUSHED), loop)
        
        def on_error(self, error, **kwargs):
            logger.error(f"Session {session_id}: TTS error: {error}")
        
        # Register handlers
        dg_tts_ws.on(SpeakWebSocketEvents.AudioData, on_binary_data)
        dg_tts_ws.on(SpeakWebSocketEvents.Flushed, on_flushed)
        dg_tts_ws.on(SpeakWebSocketEvents.Error, on_error)
        
        # TTS options
        tts_options = SpeakWSOptions(
            model=config['tts_model'],
            encoding="linear16",
            sample_rate=config['sample_rate']
        )
        
        # Start TTS
        if not dg_tts_ws.start(tts_options):
            logger.error(f"Session {session_id}: TTS start failed")
            return None
        
        # Send text
        dg_tts_ws.send_text(text)
        dg_tts_ws.flush()
        
        # Collect audio
        audio_chunks = []
        timeout = 10.0
        
        while True:
            try:
                chunk = await asyncio.wait_for(audio_queue.get(), timeout=timeout)
                if chunk == TTSEvent.FLUSHED:
                    break
                elif isinstance(chunk, bytes):
                    audio_chunks.append(chunk)
            except asyncio.TimeoutError:
                logger.warning(f"Session {session_id}: TTS timeout")
                break
        
        dg_tts_ws.finish()
        
        if audio_chunks:
            combined_audio = b''.join(audio_chunks)
            logger.info(f"Session {session_id}: TTS complete: {len(combined_audio)} bytes")
            return combined_audio
        
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
        async with websockets.connect(flux_url, extra_headers=headers) as flux_ws:
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
            'tts_model': DEEPGRAM_TTS_MODEL,
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


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Voice Agent API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

