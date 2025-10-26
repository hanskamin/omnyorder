'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useMapMarkers } from '@/hooks/useMapMarkers'

interface Message {
  type: 'user' | 'agent' | 'system'
  content: string
  timestamp: string
}

interface Config {
  sample_rate: number
  llm_model: string
  tts_model: string
  elevenlabs_voice_id: string
}

type ConversationState = 'idle' | 'listening' | 'processing' | 'speaking' | 'error'


export default function VoiceAgentPage() {
  // State
  const [status, setStatus] = useState<ConversationState>('idle')
  const [statusText, setStatusText] = useState('Disconnected')
  const [isConnected, setIsConnected] = useState(false)
  const [isConversationActive, setIsConversationActive] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [interimTranscript, setInterimTranscript] = useState('Listening...')
  const [debugLog, setDebugLog] = useState<string[]>([])
  const [selectedMicrophone, setSelectedMicrophone] = useState<string>('')
  const [microphones, setMicrophones] = useState<MediaDeviceInfo[]>([])
  const [showConfirmOrderButton, setShowConfirmOrderButton] = useState(false)
  const [orderSummary, setOrderSummary] = useState('')
  const [isConfirmingOrder, setIsConfirmingOrder] = useState(false)
  
  // Configuration
  const [config, setConfig] = useState<Config>({
    sample_rate: 16000,
    llm_model: 'gpt-4o-mini',
    tts_model: 'aura-2-phoebe-en',
    elevenlabs_voice_id: 'pNInz6obpgDQGcFmaJgB', // Adam voice
  })
  
  // Refs
  const wsRef = useRef<WebSocket | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const isRecordingRef = useRef(false)
  const audioQueueRef = useRef<Uint8Array[]>([])
  const isPlayingRef = useRef(false)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  
  // Map markers hook
  const { addMarker } = useMapMarkers()
  
  // Add debug message
  const addDebug = useCallback((category: string, message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setDebugLog(prev => [...prev.slice(-99), `[${timestamp}] ${category}: ${message}`])
  }, [])
  
  // Add conversation message
  const addMessage = useCallback((type: 'user' | 'agent' | 'system', content: string) => {
    setMessages(prev => [...prev, {
      type,
      content,
      timestamp: new Date().toISOString()
    }])
  }, [])
  
  // Update status
  const updateStatus = useCallback((state: ConversationState, text: string) => {
    setStatus(state)
    setStatusText(text)
  }, [])
  
  // Load microphones
  const loadMicrophones = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach(track => track.stop())
      
      const devices = await navigator.mediaDevices.enumerateDevices()
      const audioInputs = devices.filter(device => device.kind === 'audioinput')
      
      setMicrophones(audioInputs)
      if (audioInputs.length > 0) {
        setSelectedMicrophone(audioInputs[0].deviceId)
        addDebug('INFO', `Loaded ${audioInputs.length} microphone(s)`)
      }
    } catch (error) {
      console.error('Failed to load microphones:', error)
      addDebug('ERROR', `Failed to load microphones: ${error}`)
    }
  }, [addDebug])
  
  // Play audio (now handles MP3 from ElevenLabs)
  const playAudio = useCallback(async (audioBytes: Uint8Array) => {
    try {
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        audioContextRef.current = new AudioContext()
      }

      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume()
      }

      const arrayBuffer: ArrayBuffer = audioBytes.buffer.slice(
        audioBytes.byteOffset,
        audioBytes.byteOffset + audioBytes.byteLength
      ) as ArrayBuffer

      const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer)

      const source = audioContextRef.current.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioContextRef.current.destination)

      source.onended = () => {
        updateStatus('listening', 'Listening...')
      }

      source.start(0)
      addDebug('AUDIO', `Playing MP3 audio (${audioBytes.length} bytes, ${audioBuffer.duration.toFixed(2)}s)`)
    } catch (error) {
      console.error('Error playing audio:', error)
      addDebug('AUDIO', `Playback error: ${error}`)
    }
  }, [updateStatus, addDebug])
  
  const confirmOrder = (summary: string) => {
    // setIsConfirmingOrder(true)
    wsRef.current?.send(JSON.stringify({ type: 'confirmed_order', summary }))
    console.log('Confirmed order', summary)
  };

  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback(async ( data) => {
    const { type } = data

    switch (type) {
      case 'connected':
        addDebug('SOCKET', `Session ID: ${data.session_id}`)
        break

      case 'conversation_started':
        setIsConversationActive(true)
        updateStatus('listening', 'Listening...')
        addDebug('FLUX', 'Conversation started')
        break

      case 'conversation_stopped':
        setIsConversationActive(false)
        updateStatus('idle', 'Conversation stopped')
        addDebug('FLUX', 'Conversation stopped')
        break

      case 'speech_started':
        updateStatus('listening', 'Listening...')
        setInterimTranscript('Listening...')
        addDebug('USER', 'Started speaking')
        break

      case 'user_speech':
        addMessage('user', data.transcript)
        setInterimTranscript('Processing...')
        addDebug('USER', `"${data.transcript}"`)
        break

      case 'agent_processing':
        updateStatus('processing', 'Agent thinking...')
        setInterimTranscript('Agent is thinking...')
        addDebug('AGENT', 'Processing response')
        break

      case 'agent_response':
        addMessage('agent', data.response)
        console.log('Agent response:', data.response)
        addDebug('AGENT', `"${data.response}"`)
        break

      case 'system_response':
        addMessage('system', data.response)
        console.log('System response:', data.response)
        addDebug('SYSTEM', `"${data.response}"`)
        break

      case 'agent_speaking':
        updateStatus('speaking', 'Agent speaking...')
        if (data.audio && data.audio.length > 0) {
          const audioBytes = new Uint8Array(data.audio)
          playAudio(audioBytes)
          addDebug('AGENT', `Playing ${data.audio.length} bytes of audio`)
        }
        break

      case 'function_call':
        const functionCall: string = data.function;
        console.log('Function call:', functionCall)
        switch (functionCall) {
          case 'store_dietary_preferences':
            if (data.result && data.result.success) {
              const preferences: string = data.result.preferences;
              addMessage('system', `Preference saved: ${preferences}`);
            } else {
              addDebug('AGENT', 'Failed to store dietary preferences');
            }
            break;
          case 'store_budget_info':
            if (data.result && data.result.success) {
              const budget: string = data.result.budget;
              addMessage('system', `Budget noted: ${budget}`);
            } else {
              addDebug('AGENT', 'Failed to store budget info');
            }
            break;
          case 'search_restaurants':
            if (data.result && data.result.success) {
              const restaurants = data.result.restaurants;
              console.log('Restaurants:', restaurants);
              for (const restaurant of restaurants) {
                const priceDisplay = restaurant.price_level || 'Price not available'

                const infoWindowContent = `
                  <style>
                    .gm-style-iw button,
                    .gm-style-iw button[title="Close"],
                    .gm-style-iw-d button,
                    button.gm-ui-hover-effect,
                    .gm-style-iw button.gm-ui-hover-effect { display: none !important; }
                    .gm-style-iw-t::after,
                    .gm-style-iw-t::before { display: none !important; }
                  </style>
                  <div style="max-width: 280px; font-family: 'Space Grotesk', Arial, sans-serif; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(8px); border-radius: 12px; padding: 16px; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1); border: 1px solid rgba(148, 163, 184, 0.2);">
                    <h3 style="margin: 0 0 12px 0; color: #334155; font-size: 16px; font-weight: 600; line-height: 1.3;">${restaurant.name}</h3>
                    <p style="margin: 0 0 8px 0; color: #64748b; font-size: 14px; font-weight: 500;"><strong style="color: #475569;">Price:</strong> ${priceDisplay}</p>
                  </div>
                `

                addMarker({
                  id: `restaurant-${restaurant.name}`,
                  position: {
                    lat: restaurant.lat,
                    lng: restaurant.lng
                  },
                  options: {
                    animation: google.maps.Animation.DROP,
                    title: `${restaurant.name} - ${priceDisplay}`, // Enhanced hover tooltip
                  },
                  infoWindowContent: infoWindowContent.trim()
                })
              }
            } else {
              addDebug('AGENT', 'Failed to search restaurants');
            }
            break;
          case 'pick_restaurants':
            if (data.result && data.result.success) {
              const restaurants = data.result.restaurants;
              console.log('Restaurants:', restaurants);
              for (const restaurant of restaurants) {
                const priceDisplay = restaurant.price_level || 'Price not available'
                const reasoning = restaurant.reasoning || 'Recommended restaurant'
                
                // Check delivery platforms
                const deliveryPlatforms = restaurant.delivery_platforms || [];
                const platformsLower = deliveryPlatforms.map((p: string) => p.toLowerCase());
                
                const hasUberEats = platformsLower.some((p: string) => p.includes('uber'));
                const hasDoorDash = platformsLower.some((p: string) => p.includes('doordash'));
                const hasInstacart = platformsLower.some((p: string) => p.includes('instacart'));
                
                // Platform logo URLs mapping
                const platformLogoUrls: Record<string, string> = {
                  'uber': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTmT0Dx-4WB8c13Vn9ay1qbbhtFuQOjzbyG6Q&s',
                  'doordash': 'https://play-lh.googleusercontent.com/ISmECE96NXztm4hdjoRcyU4AbtJyDRFXdcQJTCoh4X5fRyn7A6M_dB4sWSOQl4Hjaqzq',
                  'instacart': 'data:image/png;base64,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'
                };
                
                // Get the first platform's logo URL for marker icon
                let markerIconUrl = '';
                if (deliveryPlatforms.length > 0) {
                  const firstPlatform = platformsLower[0];
                  if (firstPlatform.includes('uber')) {
                    markerIconUrl = platformLogoUrls['uber'];
                  } else if (firstPlatform.includes('doordash')) {
                    markerIconUrl = platformLogoUrls['doordash'];
                  } else if (firstPlatform.includes('instacart')) {
                    markerIconUrl = platformLogoUrls['instacart'];
                  }
                }
                
                // Build delivery platform logos HTML
                let platformLogosHtml = '';
                if (hasUberEats || hasDoorDash || hasInstacart) {
                  platformLogosHtml = '<div style="margin-top: 12px; display: flex; gap: 8px; align-items: center;">';
                  
                  if (hasUberEats) {
                    platformLogosHtml += `<img src="${platformLogoUrls['uber']}" alt="Uber Eats" style="height: 24px; object-fit: contain;" />`;
                  }
                  if (hasDoorDash) {
                    platformLogosHtml += `<img src="${platformLogoUrls['doordash']}" alt="DoorDash" style="height: 24px; object-fit: contain;" />`;
                  }
                  if (hasInstacart) {
                    platformLogosHtml += `<img src="data:image/png;base64,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" alt="Instacart" style="height: 24px; object-fit: contain;" />`;
                  }
                  
                  platformLogosHtml += '</div>';
                }

                const infoWindowContent = `
                  <style>
                    .gm-style-iw button,
                    .gm-style-iw button[title="Close"],
                    .gm-style-iw-d button,
                    button.gm-ui-hover-effect,
                    .gm-style-iw button.gm-ui-hover-effect { display: none !important; }
                    .gm-style-iw-t::after,
                    .gm-style-iw-t::before { display: none !important; }
                  </style>
                  <div style="max-width: 280px; font-family: 'Space Grotesk', Arial, sans-serif; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(8px); border-radius: 12px; padding: 16px; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1); border: 1px solid rgba(148, 163, 184, 0.2);">
                    <h3 style="margin: 0 0 12px 0; color: #334155; font-size: 16px; font-weight: 600; line-height: 1.3;">${restaurant.name}</h3>
                    <p style="margin: 0 0 8px 0; color: #64748b; font-size: 14px; font-weight: 500;"><strong style="color: #475569;">Price:</strong> ${priceDisplay}</p>
                    <p style="margin: 0; color: #64748b; font-size: 14px; line-height: 1.4;">${reasoning}</p>
                    ${platformLogosHtml}
                  </div>
                `

                // Configure marker icon - use first platform logo or fallback to circle
                const markerIcon = markerIconUrl ? {
                  url: markerIconUrl,
                  scaledSize: new google.maps.Size(32, 32),
                  anchor: new google.maps.Point(16, 16),
                } : {
                  path: google.maps.SymbolPath.CIRCLE,
                  scale: 10,
                  fillColor: '#00FF00',
                  fillOpacity: 1,
                  strokeColor: '#006400',
                  strokeWeight: 2,
                };

                addMarker({
                  id: `restaurant-${restaurant.name}`,
                  position: {
                    lat: restaurant.lat,
                    lng: restaurant.lng
                  },
                  options: {
                    animation: google.maps.Animation.BOUNCE,
                    title: `${restaurant.name} - ${priceDisplay}`, // Enhanced hover tooltip
                    icon: markerIcon,
                  },
                  infoWindowContent: infoWindowContent.trim()
                })
              }
            } else {
              addDebug('AGENT', 'Failed to search restaurants');
            }
            break;
           case 'confirm_order':
             if (data.result && data.result.success) {
               // display the order summary
               // store the order summary for the confirm button
               setOrderSummary(data.result.order_summary);
               // display the confirm button
               setShowConfirmOrderButton(true)
               // TODO: replace with actual order confirmation.
              //  setTimeout(() => {
              //   setIsConfirmingOrder(false)
              //  }, 3000);
             } else {
               addDebug('AGENT', 'Failed to confirm order');
             }
             break;
        }
        break

      case 'approval_request':
        // TODO: Handle approval request
        addDebug('APPROVAL', `${data.request}`)
        break

      case 'interim_transcript':
        if (data.transcript) {
          setInterimTranscript(data.transcript)
        }
        break

      // case 'flux_event':
      //   addDebug('FLUX', `${data.data.type}`)
      //   break

      case 'error':
        updateStatus('error', `Error: ${data.error}`)
        addDebug('ERROR', data.error)
        break
    }
  }, [updateStatus, addMessage, addDebug, playAudio, addMarker])

  // Initialize WebSocket
  const initWebSocket = useCallback(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/voice')
    
    ws.onopen = () => {
      console.log('WebSocket connected')
      setIsConnected(true)
      updateStatus('idle', 'Connected')
      addDebug('SOCKET', 'Connected to server')
    }
    
    ws.onclose = () => {
      console.log('WebSocket disconnected')
      setIsConnected(false)
      updateStatus('idle', 'Disconnected')
      addDebug('SOCKET', 'Disconnected from server')
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      addDebug('ERROR', 'WebSocket error')
    }
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type != 'flux_event' &&data.type != 'interim_transcript' && data.type != 'agent_speaking')
          console.log("I'm gettting a message" + JSON.stringify(data))
        handleWebSocketMessage(data).catch(error => {
          console.error('Error handling message:', error);
          addDebug('ERROR', `Message handling failed: ${error.message}`);
        });
      } catch (error) {
        console.error('Error parsing message:', error)
      }
    }
    
    wsRef.current = ws
  }, [updateStatus, addDebug, handleWebSocketMessage])
  
  // Convert float to PCM
  const convertFloatToPcm = (floatData: Float32Array): Int16Array => {
    const pcmData = new Int16Array(floatData.length)
    for (let i = 0; i < floatData.length; i++) {
      const s = Math.max(-1, Math.min(1, floatData[i]))
      pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
    }
    return pcmData
  }
  
  // Setup audio processing
  const setupAudioProcessing = useCallback(() => {
    console.log('setupAudioProcessing called', {
      hasAudioContext: !!audioContextRef.current,
      hasMediaStream: !!mediaStreamRef.current,
      wsReadyState: wsRef.current?.readyState
    })
    
    if (!audioContextRef.current || !mediaStreamRef.current) {
      console.log('Missing audio context or media stream')
      return
    }
    
    const source = audioContextRef.current.createMediaStreamSource(mediaStreamRef.current)
    const bufferSize = 2048
    const processor = audioContextRef.current.createScriptProcessor(bufferSize, 1, 1)
    
    console.log('Created audio processor with buffer size:', bufferSize)
    
    source.connect(processor)
    processor.connect(audioContextRef.current.destination)
    
    let lastSendTime = 0
    const sendInterval = 100
    
    processor.onaudioprocess = (e) => {
      const now = Date.now()
      
      if (wsRef.current?.readyState === WebSocket.OPEN &&
          isRecordingRef.current &&
          now - lastSendTime >= sendInterval) {
        
        const inputData = e.inputBuffer.getChannelData(0)
        const pcmData = convertFloatToPcm(inputData)
        
        // Send as binary
        console.log(`Sending ${pcmData.length} audio samples (${pcmData.buffer.byteLength} bytes)`)
        wsRef.current.send(pcmData.buffer)
        lastSendTime = now
      }
    }
    
    processorRef.current = processor
    isRecordingRef.current = true
    console.log('Audio processing setup complete, isRecordingRef.current =', isRecordingRef.current)
  }, [])
  
  // Start conversation
  const startConversation = async () => {
    console.log('startConversation called', { isConnected, selectedMicrophone })
    if (!isConnected || !selectedMicrophone) {
      console.log('Cannot start: not connected or no microphone selected')
      return
    }
    
    try {
      console.log('Creating audio context...')
      audioContextRef.current = new AudioContext({
        sampleRate: config.sample_rate
      })
      
      const constraints = {
        audio: {
          deviceId: { exact: selectedMicrophone },
          channelCount: 1,
          sampleRate: config.sample_rate,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      }
      
      console.log('Getting user media with constraints:', constraints)
      mediaStreamRef.current = await navigator.mediaDevices.getUserMedia(constraints)
      console.log('Got media stream, setting up audio processing...')
      setupAudioProcessing()
      
      // Send configuration update to backend
      console.log('Sending config update to server:', config)
      wsRef.current?.send(JSON.stringify({ 
        type: 'update_config', 
        config: config 
      }))
      
      // Send start command
      console.log('Sending start_conversation command to server')
      wsRef.current?.send(JSON.stringify({ type: 'start_conversation' }))
      
      addDebug('AUDIO', `Started audio capture at ${config.sample_rate}Hz with ${config.elevenlabs_voice_id}`)
    } catch (error) {
      console.error('Failed to start conversation:', error)
      updateStatus('error', 'Failed to start')
      addDebug('ERROR', `Failed to start: ${error}`)
    }
  }
  
  // Stop conversation
  const stopConversation = () => {
    isRecordingRef.current = false
    
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current.onaudioprocess = null
      processorRef.current = null
    }
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop())
      mediaStreamRef.current = null
    }
    
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    
    wsRef.current?.send(JSON.stringify({ type: 'stop_conversation' }))
    
    addDebug('AUDIO', 'Conversation stopped - all audio processing cleaned up')
  }
  
  // Clear log
  const clearLog = () => {
    setMessages([{ type: 'system', content: 'Conversation log cleared', timestamp: new Date().toISOString() }])
  }
  
  // Export conversation
  const exportConversation = () => {
    if (messages.length === 0) {
      alert('No conversation to export')
      return
    }
    
    const exportData = {
      timestamp: new Date().toISOString(),
      config,
      messages
    }
    
    const dataStr = JSON.stringify(exportData, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(dataBlob)
    link.download = `voice-conversation-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`
    link.click()
  }

  
  // Initialize on mount
  useEffect(() => {
    loadMicrophones()
    initWebSocket()
    
    return () => {
      if (isConversationActive) {
        stopConversation()
      }
      wsRef.current?.close()
    }
  }, [])

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])
  
  // Get status color
  const getStatusColor = () => {
    switch (status) {
      case 'idle': return 'bg-gray-500'
      case 'listening': return 'bg-green-500 animate-pulse'
      case 'processing': return 'bg-yellow-500 animate-pulse'
      case 'speaking': return 'bg-blue-500 animate-pulse'
      case 'error': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }
  
  return (
    <div
      className="fixed left-3 top-3 md:left-6 md:top-6 z-2
             w-[calc(100vw-1.5rem)] md:w-[420px]
             max-h-[calc(100vh-var(--map-controls-inset)-1.5rem)]
             overflow-auto rounded-2xl border border-black/10 shadow-xl
             bg-white/90 dark:bg-neutral-900/80 backdrop-blur-xl
             text-slate-900 dark:text-white p-4 md:p-6"
    >
      <div className="flex items-center gap-3 mb-6 text-slate-700 dark:text-slate-200">
        <div className={`w-3 h-3 rounded-full ${getStatusColor()}`} />
        <span className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
          Status
        </span>
        <span className="text-base font-medium text-slate-700 dark:text-white">{statusText}</span>
      </div>
      
      <div className="space-y-6">
        <div className="rounded-xl bg-transparent dark:bg-neutral-900/70 p-2">
          <div className="flex flex-wrap gap-3 justify-center w-full">
            <button
              onClick={startConversation}
              disabled={!isConnected || !selectedMicrophone || isConversationActive}
              className="bg-emerald-500 hover:bg-emerald-600 disabled:bg-transparent disabled:border-gray-400 disabled:text-gray-400 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-xl shadow-xl transition-all disabled:border flex-1"
            >
              Begin
            </button>
            
            <button
              onClick={stopConversation}
              disabled={!isConversationActive}
              className="bg-rose-500 hover:bg-rose-600 disabled:bg-transparent disabled:border-gray-400 disabled:text-gray-400 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-xl shadow-xl transition-all disabled:border flex-1"
            >
              Cancel
            </button>
          </div>
          
          {isConversationActive && (
            <div className="mt-4 rounded-lg border border-slate-200/70 dark:border-white/10 bg-slate-50/80 dark:bg-white/5 p-3">
              <p className="text-sm text-slate-600 dark:text-slate-200 italic">{interimTranscript}</p>
            </div>
          )}
        </div>
        
        <div className="rounded-xl border border-slate-200 dark:border-white/10 bg-white/80 dark:bg-neutral-900/70 shadow-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white">Your Order</h2>
            {messages.length > 0 && (
              <button
                onClick={clearLog}
                className="text-xs font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700 dark:text-slate-300 dark:hover:text-white transition-colors"
              >
                Clear
              </button>
            )}
          </div>
          
          <div className="rounded-lg h-96 overflow-y-auto space-y-3">
            {messages.length === 0 && (
              <p className="text-sm text-slate-500 dark:text-slate-300">Place an order now!</p>
            )}
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg border ${
                  msg.type === 'user'
                    ? 'border-emerald-200 bg-emerald-50/90 text-emerald-900 dark:border-emerald-400/40 dark:bg-emerald-500/15 dark:text-white'
                    : msg.type === 'agent'
                    ? 'border-sky-200 bg-sky-50/90 text-sky-900 dark:border-sky-400/40 dark:bg-sky-500/15 dark:text-white'
                    : 'border-amber-200 bg-amber-50/90 text-amber-900 dark:border-amber-400/40 dark:bg-amber-500/15 dark:text-white'
                }`}
              >
                <div className="text-xs font-medium text-slate-500 dark:text-slate-300 mb-1">
                  {msg.type === 'user' ? 'You' : msg.type === 'agent' ? 'Omni' : 'System'} · {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
                <div className="text-sm leading-relaxed">
                  {msg.content}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {showConfirmOrderButton && (
          <div className="mt-6">
            <button
              onClick={() => {
                confirmOrder(orderSummary);
                addMessage('system', 'ORDER SUBMITTED.')
              }}
              disabled={isConfirmingOrder}
              className="w-full bg-sky-500 hover:bg-sky-600 disabled:bg-sky-400 disabled:cursor-not-allowed text-white font-semibold py-4 px-6 rounded-xl shadow-xl transition-all"
            >
              {isConfirmingOrder ? 'Confirming...' : 'Confirm Order'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
