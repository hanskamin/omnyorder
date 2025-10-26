'use client'

import { useState, useRef, useEffect, useCallback } from 'react'

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
        console.log('Received WebSocket message:', data)
        handleWebSocketMessage(data)
      } catch (error) {
        console.error('Error parsing message:', error)
      }
    }
    
    wsRef.current = ws
  }, [updateStatus, addDebug, ])
  
  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback((data: any) => {
    const { type } = data
    
    switch (type) {
      case 'connected':
        addDebug('SOCKET', `Session ID: ${data.session_id}`)
        break
      
      case 'conversation_started':
        setIsConversationActive(true)
        updateStatus('listening', 'Listening...')
        addMessage('system', 'Conversation started')
        addDebug('FLUX', 'Conversation started')
        break
      
      case 'conversation_stopped':
        setIsConversationActive(false)
        updateStatus('idle', 'Conversation stopped')
        addMessage('system', 'Conversation ended')
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
        addDebug('AGENT', `"${data.response}"`)
        break
      
      case 'agent_speaking':
        updateStatus('speaking', 'Agent speaking...')
        if (data.audio && data.audio.length > 0) {
          const audioBytes = new Uint8Array(data.audio)
          playAudio(audioBytes)
          addDebug('AGENT', `Playing ${data.audio.length} bytes of audio`)
        }
        break
      
      case 'interim_transcript':
        if (data.transcript) {
          setInterimTranscript(data.transcript)
        }
        break
      
      case 'flux_event':
        addDebug('FLUX', `${data.data.type}`)
        break
      
      case 'error':
        updateStatus('error', `Error: ${data.error}`)
        addDebug('ERROR', data.error)
        break
    }
  }, [updateStatus, addMessage, addDebug])
  
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
  
  // Play audio (now handles MP3 from ElevenLabs)
  const playAudio = async (audioBytes: Uint8Array) => {
    try {
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        audioContextRef.current = new AudioContext()
      }
      
      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume()
      }
      
      // Convert Uint8Array to ArrayBuffer for decoding
      // ElevenLabs sends MP3, which AudioContext can decode natively
      const arrayBuffer: ArrayBuffer = audioBytes.buffer.slice(
        audioBytes.byteOffset,
        audioBytes.byteOffset + audioBytes.byteLength
      ) as ArrayBuffer
      
      // Decode MP3 audio directly (no WAV wrapper needed)
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
  }
  
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
      className="fixed left-3 top-3 md:left-6 md:top-6 z-[2]
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
        <div className="rounded-xl border border-slate-200/60 dark:border-white/10 bg-white/80 dark:bg-neutral-900/70 shadow-sm p-5">
          <div className="flex flex-wrap gap-3">
            <button
              onClick={startConversation}
              disabled={!isConnected || !selectedMicrophone || isConversationActive}
              className="bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 disabled:from-gray-400 disabled:to-gray-500 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-xl shadow-lg transition-all"
            >
              🎤 Start Conversation
            </button>
            
            <button
              onClick={stopConversation}
              disabled={!isConversationActive}
              className="bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 disabled:from-gray-400 disabled:to-gray-500 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-xl shadow-lg transition-all"
            >
              ⏹️ Stop Conversation
            </button>
          </div>
          
          {isConversationActive && (
            <div className="mt-4 rounded-lg border border-slate-200/70 dark:border-white/10 bg-slate-50/80 dark:bg-white/5 p-3">
              <p className="text-sm text-slate-600 dark:text-slate-200 italic">{interimTranscript}</p>
            </div>
          )}
        </div>
        
        <div className="rounded-xl border border-slate-200/60 dark:border-white/10 bg-white/80 dark:bg-neutral-900/70 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white">💬 Conversation History</h2>
            {messages.length > 0 && (
              <button
                onClick={clearLog}
                className="text-xs font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700 dark:text-slate-300 dark:hover:text-white transition-colors"
              >
                Clear
              </button>
            )}
          </div>
          
          <div className="rounded-lg border border-slate-200/60 dark:border-white/10 bg-slate-50/70 dark:bg-white/5 p-4 h-96 overflow-y-auto space-y-3">
            {messages.length === 0 && (
              <p className="text-sm text-slate-500 dark:text-slate-300">No messages yet.</p>
            )}
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg border ${
                  msg.type === 'user'
                    ? 'border-emerald-200 bg-emerald-50/90 text-emerald-900 dark:border-emerald-400/40 dark:bg-emerald-500/15 dark:text-white'
                    : msg.type === 'agent'
                    ? 'border-sky-200 bg-sky-50/90 text-sky-900 dark:border-sky-400/40 dark:bg-sky-500/15 dark:text-white'
                    : 'border-slate-200 bg-slate-50/90 text-slate-700 dark:border-slate-500/40 dark:bg-slate-500/20 dark:text-white'
                }`}
              >
                <div className="text-xs font-medium text-slate-500 dark:text-slate-300 mb-1">
                  {msg.type === 'user' ? 'You' : msg.type === 'agent' ? 'Assistant' : 'System'} · {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
                <div className="text-sm leading-relaxed">
                  {msg.content}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
