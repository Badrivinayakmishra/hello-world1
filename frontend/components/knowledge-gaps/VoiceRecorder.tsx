import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003') + '/api'

interface VoiceRecorderProps {
  onTranscriptionComplete: (text: string) => void
  authHeaders: any
}

export default function VoiceRecorder({ onTranscriptionComplete, authHeaders }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [transcription, setTranscription] = useState('')
  const [showPreview, setShowPreview] = useState(false)
  const [audioLevel, setAudioLevel] = useState(0)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animationFrameRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
      if (audioContextRef.current) audioContextRef.current.close()
    }
  }, [])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // Set up audio visualization
      audioContextRef.current = new AudioContext()
      const source = audioContextRef.current.createMediaStreamSource(stream)
      analyserRef.current = audioContextRef.current.createAnalyser()
      analyserRef.current.fftSize = 256
      source.connect(analyserRef.current)

      // Start visualization loop
      visualize()

      mediaRecorderRef.current = new MediaRecorder(stream)
      chunksRef.current = []

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach(track => track.stop())
        if (audioContextRef.current) audioContextRef.current.close()
        await transcribeAudio(audioBlob)
      }

      mediaRecorderRef.current.start()
      setIsRecording(true)
      setRecordingTime(0)

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1)
      }, 1000)
    } catch (error) {
      console.error('Error starting recording:', error)
      alert('Could not access microphone. Please check permissions.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      if (timerRef.current) clearInterval(timerRef.current)
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
    }
  }

  const visualize = () => {
    if (!analyserRef.current) return

    const bufferLength = analyserRef.current.frequencyBinCount
    const dataArray = new Uint8Array(bufferLength)

    const update = () => {
      if (!isRecording) return
      analyserRef.current!.getByteFrequencyData(dataArray)

      // Calculate average volume
      const average = dataArray.reduce((a, b) => a + b) / bufferLength
      setAudioLevel(Math.min(100, (average / 255) * 100 * 2))

      animationFrameRef.current = requestAnimationFrame(update)
    }

    update()
  }

  const transcribeAudio = async (audioBlob: Blob) => {
    setIsTranscribing(true)
    try {
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')

      const response = await axios.post(`${API_BASE}/knowledge/transcribe`, formData, {
        headers: {
          ...authHeaders,
          'Content-Type': 'multipart/form-data'
        }
      })

      if (response.data.success && response.data.transcription) {
        setTranscription(response.data.transcription.text)
        setShowPreview(true)
      } else {
        alert('Transcription failed: ' + (response.data.error || 'Unknown error'))
      }
    } catch (error: any) {
      console.error('Error transcribing audio:', error)
      alert('Transcription failed: ' + (error.response?.data?.error || error.message))
    } finally {
      setIsTranscribing(false)
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const handleUseTranscription = () => {
    onTranscriptionComplete(transcription)
    setShowPreview(false)
    setTranscription('')
    setRecordingTime(0)
  }

  const handleReRecord = () => {
    setShowPreview(false)
    setTranscription('')
    setRecordingTime(0)
  }

  return (
    <div className="space-y-3">
      {/* Recording Controls */}
      {!showPreview && (
        <div className="flex items-center gap-3">
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isTranscribing}
            className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors"
            style={{
              backgroundColor: isRecording ? '#FEE2E2' : '#F3F4F6',
              color: isRecording ? '#DC2626' : '#081028',
              fontFamily: '"Work Sans", sans-serif',
              cursor: isTranscribing ? 'wait' : 'pointer'
            }}
          >
            {isTranscribing ? (
              <>
                <span className="animate-spin">⏳</span>
                Transcribing...
              </>
            ) : isRecording ? (
              <>
                <span className="animate-pulse">⏹</span>
                Stop Recording
              </>
            ) : (
              <>
                <span>🎤</span>
                Start Voice Answer
              </>
            )}
          </button>

          {/* Recording Timer */}
          {isRecording && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono text-red-600">{formatTime(recordingTime)}</span>

              {/* Audio Level Indicator */}
              <div className="flex items-center gap-0.5">
                {[...Array(10)].map((_, i) => (
                  <div
                    key={i}
                    className="w-1 rounded-full transition-all"
                    style={{
                      height: audioLevel > (i * 10) ? '16px' : '4px',
                      backgroundColor: audioLevel > (i * 10) ? '#DC2626' : '#E5E7EB'
                    }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Transcription Preview */}
      {showPreview && transcription && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-blue-900">Transcription Preview</span>
            <span className="text-xs text-blue-600">✓ Ready to use</span>
          </div>

          <textarea
            value={transcription}
            onChange={(e) => setTranscription(e.target.value)}
            className="w-full min-h-[80px] p-2 rounded border border-blue-300 bg-white text-sm resize-vertical outline-none focus:border-blue-500"
            style={{ fontFamily: '"Work Sans", sans-serif' }}
            placeholder="Edit transcription if needed..."
          />

          <div className="flex items-center gap-2">
            <button
              onClick={handleUseTranscription}
              className="flex-1 px-4 py-2 rounded-lg bg-blue-600 text-white font-medium text-sm hover:bg-blue-700 transition-colors"
            >
              ✓ Use This Answer
            </button>
            <button
              onClick={handleReRecord}
              className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 font-medium text-sm hover:bg-gray-50 transition-colors"
            >
              🔄 Re-record
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
