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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Omni Order Voice Agent
          </h1>
          <p className="text-gray-300 text-lg">
            Real-time voice conversations powered by Omni Order
          </p>
          
          {/* Status */}
          <div className="mt-4 flex items-center justify-center gap-3">
            <div className={`w-3 h-3 rounded-full ${getStatusColor()}`} />
            <span className="font-medium">{statusText}</span>
          </div>
        </div>

        {/* Configuration */}
        <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20 mb-6">
          <h2 className="text-xl font-semibold mb-4">⚙️ Configuration</h2>
          
          <div className="grid md:grid-cols-2 gap-4">
            {/* Microphone Selection */}
            <div>
              <label className="block text-sm font-medium mb-2">🎤 Microphone</label>
              <select
                value={selectedMicrophone}
                onChange={(e) => setSelectedMicrophone(e.target.value)}
                disabled={isConversationActive}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <option value="">Select a microphone...</option>
                {microphones.map((mic) => (
                  <option key={mic.deviceId} value={mic.deviceId}>
                    {mic.label || `Microphone ${mic.deviceId.slice(0, 8)}`}
                  </option>
                ))}
              </select>
            </div>
            
            {/* Voice Selection */}
            <div>
              <label className="block text-sm font-medium mb-2">🗣️ ElevenLabs Voice</label>
              <select
                value={config.elevenlabs_voice_id}
                onChange={(e) => setConfig({ ...config, elevenlabs_voice_id: e.target.value })}
                disabled={isConversationActive}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <option value="pNInz6obpgDQGcFmaJgB">Adam (Male - Deep, Authoritative)</option>
                <option value="yoZ06aMxZJJ28mfd3POQ">Sam (Male - Clear, Professional)</option>
                <option value="cgSgspJ2msm6clMCkdW9">Eric (Male - Friendly, Warm)</option>
                <option value="21m00Tcm4TlvDq8ikWAM">Rachel (Female - Calm, Clear)</option>
                <option value="EXAVITQu4vr4xnSDxMaL">Bella (Female - Soft, Young)</option>
                <option value="jsCqWAovK2LkecY7zXl4">Freya (Female - Expressive, Energetic)</option>
              </select>
            </div>
            
            {/* LLM Model */}
            <div>
              <label className="block text-sm font-medium mb-2">🤖 Language Model</label>
              <select
                value={config.llm_model}
                onChange={(e) => setConfig({ ...config, llm_model: e.target.value })}
                disabled={isConversationActive}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <option value="gpt-4o-mini">GPT-4o Mini (Fast & Affordable)</option>
                <option value="gpt-4o">GPT-4o (Best Quality)</option>
                <option value="gpt-3.5-turbo">GPT-3.5 Turbo (Legacy)</option>
              </select>
            </div>
            
            {/* Sample Rate */}
            <div>
              <label className="block text-sm font-medium mb-2">🎵 Sample Rate</label>
              <select
                value={config.sample_rate}
                onChange={(e) => setConfig({ ...config, sample_rate: Number(e.target.value) })}
                disabled={isConversationActive}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <option value="8000">8 kHz</option>
                <option value="16000">16 kHz (Recommended)</option>
                <option value="24000">24 kHz</option>
                <option value="48000">48 kHz</option>
              </select>
            </div>
          </div>
        </div>
        
        {/* Controls */}
        <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20 mb-6 text-center">
          <div className="flex gap-4 justify-center mb-4">
            <button
              onClick={startConversation}
              disabled={!isConnected || !selectedMicrophone || isConversationActive}
              className="bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 disabled:from-gray-500 disabled:to-gray-600 disabled:cursor-not-allowed text-white font-semibold py-3 px-8 rounded-xl shadow-lg transition-all"
            >
              🎤 Start Conversation
            </button>
            
            <button
              onClick={stopConversation}
              disabled={!isConversationActive}
              className="bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 disabled:from-gray-500 disabled:to-gray-600 disabled:cursor-not-allowed text-white font-semibold py-3 px-8 rounded-xl shadow-lg transition-all"
            >
              ⏹️ Stop Conversation
            </button>
          </div>
          
          {isConversationActive && (
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <p className="text-sm text-gray-300 italic">{interimTranscript}</p>
            </div>
          )}
        </div>
        
        {/* Conversation Log */}
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">💬 Conversation History</h2>
            </div>
            
            <div className="bg-slate-900/50 rounded-lg p-4 h-96 overflow-y-auto space-y-3">
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg border-l-4 ${
                    msg.type === 'user'
                      ? 'bg-blue-900/30 border-blue-500'
                      : msg.type === 'agent'
                      ? 'bg-green-900/30 border-green-500'
                      : 'bg-gray-900/30 border-gray-500'
                  }`}
                >
                  <div className="text-xs text-gray-400 mb-1">
                    {msg.type === 'user' ? 'You' : msg.type === 'agent' ? 'Assistant' : 'System'} - {new Date(msg.timestamp).toLocaleTimeString()}
                  </div>
                  <div className="text-sm">{msg.content}</div>
                </div>
              ))}
            </div>
          </div>
        
        </div>
      </div>
    </div>
  )
}

