'use client'

import React, { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003') + '/api'

// Modern Design System - matching Documents page
const colors = {
  primary: '#2563EB',
  primaryHover: '#1D4ED8',
  primaryLight: '#EFF6FF',
  pageBg: '#F9FAFB',
  cardBg: '#FFFFFF',
  textPrimary: '#111827',
  textSecondary: '#6B7280',
  textMuted: '#9CA3AF',
  border: '#E5E7EB',
  borderLight: '#F3F4F6',
  statusGreen: '#22C55E',
  statusOrange: '#F59E0B',
  statusRed: '#EF4444',
}

const shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
}

interface KnowledgeGap {
  id: string
  description: string
  project: string
  answered?: boolean
  answer?: string
  category?: string
  priority?: string
  quality_score?: number
  evidence?: string
  context?: string
  suggested_sources?: string[]
  detection_method?: string
  estimated_time?: number // in minutes
  flagged?: boolean
  skipped?: boolean
}

export default function KnowledgeGaps() {
  const router = useRouter()
  const [gaps, setGaps] = useState<KnowledgeGap[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)

  // Time strategy filter
  const [timeStrategy, setTimeStrategy] = useState<'10' | '30' | '90'>('30')

  // View mode
  const [viewMode, setViewMode] = useState<'focus' | 'list'>('list')

  // Current gap in focus mode
  const [currentGapIndex, setCurrentGapIndex] = useState(0)

  // Card states (answer, input mode)
  const [cardStates, setCardStates] = useState<{
    [key: string]: {
      inputMode: 'type' | 'speak'
      answer: string
      isRecording: boolean
      audioLevel: number
    }
  }>({})

  // Session tracking
  const [sessionAnswered, setSessionAnswered] = useState(0)
  const [sessionSkipped, setSessionSkipped] = useState(0)

  // Submitting state
  const [submittingId, setSubmittingId] = useState<string | null>(null)

  const authHeaders = useAuthHeaders()
  const { token, user } = useAuth()

  // Media recorder refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)

  useEffect(() => {
    if (token) loadKnowledgeGaps()
  }, [token])

  const loadKnowledgeGaps = async () => {
    try {
      const response = await axios.get(`${API_BASE}/knowledge/gaps`, { headers: authHeaders })

      if (response.data.success && response.data.gaps) {
        const allGaps: KnowledgeGap[] = []

        response.data.gaps.forEach((gap: any) => {
          const groupName = gap.title || gap.category || 'General'
          const questions = gap.questions || []

          const gapMetadata = {
            category: gap.category,
            priority: gap.priority || 'medium',
            quality_score: gap.quality_score,
            evidence: gap.evidence,
            context: gap.context || gap.description,
            detection_method: gap.detection_method || gap.source,
            estimated_time: gap.estimated_time || (gap.priority === 'high' ? 5 : gap.priority === 'low' ? 2 : 3)
          }

          if (questions.length === 0 && gap.description) {
            allGaps.push({
              id: gap.id,
              description: gap.description,
              project: groupName,
              answered: gap.status === 'answered' || gap.status === 'verified' || gap.status === 'closed',
              answer: '',
              ...gapMetadata
            })
          } else {
            questions.forEach((question: any, qIndex: number) => {
              const questionText = typeof question === 'string' ? question : question.text || ''
              const isAnswered = typeof question === 'object' ? question.answered : false
              const answerObj = gap.answers?.find((a: any) => a.question_index === qIndex)

              allGaps.push({
                id: `${gap.id}_${qIndex}`,
                description: questionText,
                project: groupName,
                answered: isAnswered || gap.status === 'answered',
                answer: answerObj?.answer_text || '',
                ...gapMetadata
              })
            })
          }
        })

        setGaps(allGaps)

        // Initialize card states
        const states: typeof cardStates = {}
        allGaps.forEach(gap => {
          states[gap.id] = {
            inputMode: 'type',
            answer: gap.answer || '',
            isRecording: false,
            audioLevel: 0
          }
        })
        setCardStates(states)
      }
    } catch (error) {
      console.error('Error loading knowledge gaps:', error)
    } finally {
      setLoading(false)
    }
  }

  const generateQuestions = async () => {
    setGenerating(true)
    try {
      const response = await axios.post(`${API_BASE}/knowledge/analyze`, {
        force: true,
        include_pending: true,
        mode: 'intelligent'
      }, { headers: authHeaders })

      if (response.data.success) {
        await loadKnowledgeGaps()
      }
    } catch (error) {
      console.error('Error analyzing documents:', error)
    } finally {
      setGenerating(false)
    }
  }

  const handleSubmitAnswer = async (gapId: string) => {
    const state = cardStates[gapId]
    if (!state?.answer.trim() || submittingId) return

    setSubmittingId(gapId)
    try {
      const idParts = gapId.split('_')
      const questionIndex = idParts.length > 1 ? parseInt(idParts[idParts.length - 1]) : 0
      const originalGapId = idParts.length > 1 ? idParts.slice(0, -1).join('_') : gapId

      await axios.post(`${API_BASE}/knowledge/gaps/${originalGapId}/answers`, {
        question_index: questionIndex,
        answer_text: state.answer
      }, { headers: authHeaders })

      setGaps(prev => prev.map(g =>
        g.id === gapId ? { ...g, answered: true, answer: state.answer } : g
      ))

      setSessionAnswered(prev => prev + 1)

      // Move to next gap in focus mode
      if (viewMode === 'focus') {
        const filtered = getFilteredGaps()
        const currentIdx = filtered.findIndex(g => g.id === gapId)
        if (currentIdx < filtered.length - 1) {
          setCurrentGapIndex(currentIdx + 1)
        }
      }
    } catch (error) {
      console.error('Error submitting answer:', error)
      alert('Failed to save answer. Please try again.')
    } finally {
      setSubmittingId(null)
    }
  }

  const handleSkip = (gapId: string) => {
    setGaps(prev => prev.map(g =>
      g.id === gapId ? { ...g, skipped: true } : g
    ))
    setSessionSkipped(prev => prev + 1)

    if (viewMode === 'focus') {
      const filtered = getFilteredGaps()
      const currentIdx = filtered.findIndex(g => g.id === gapId)
      if (currentIdx < filtered.length - 1) {
        setCurrentGapIndex(currentIdx + 1)
      }
    }
  }

  const handleFlag = (gapId: string) => {
    setGaps(prev => prev.map(g =>
      g.id === gapId ? { ...g, flagged: !g.flagged } : g
    ))
  }

  const updateCardState = (gapId: string, updates: Partial<typeof cardStates[string]>) => {
    setCardStates(prev => ({
      ...prev,
      [gapId]: { ...prev[gapId], ...updates }
    }))
  }

  // Voice recording functions
  const startRecording = async (gapId: string) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      audioContextRef.current = new AudioContext()
      const source = audioContextRef.current.createMediaStreamSource(stream)
      analyserRef.current = audioContextRef.current.createAnalyser()
      analyserRef.current.fftSize = 256
      source.connect(analyserRef.current)

      mediaRecorderRef.current = new MediaRecorder(stream)
      chunksRef.current = []

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach(track => track.stop())
        if (audioContextRef.current) audioContextRef.current.close()
        await transcribeAudio(gapId, audioBlob)
      }

      mediaRecorderRef.current.start()
      updateCardState(gapId, { isRecording: true })

      // Audio level visualization
      visualizeAudio(gapId)
    } catch (error) {
      console.error('Error starting recording:', error)
      alert('Could not access microphone. Please check permissions.')
    }
  }

  const stopRecording = (gapId: string) => {
    if (mediaRecorderRef.current && cardStates[gapId]?.isRecording) {
      mediaRecorderRef.current.stop()
      updateCardState(gapId, { isRecording: false, audioLevel: 0 })
    }
  }

  const visualizeAudio = (gapId: string) => {
    if (!analyserRef.current) return

    const bufferLength = analyserRef.current.frequencyBinCount
    const dataArray = new Uint8Array(bufferLength)

    const update = () => {
      if (!cardStates[gapId]?.isRecording) return
      analyserRef.current!.getByteFrequencyData(dataArray)
      const average = dataArray.reduce((a, b) => a + b) / bufferLength
      updateCardState(gapId, { audioLevel: Math.min(100, (average / 255) * 100 * 2) })
      requestAnimationFrame(update)
    }

    update()
  }

  const transcribeAudio = async (gapId: string, audioBlob: Blob) => {
    try {
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')

      const response = await axios.post(`${API_BASE}/knowledge/transcribe`, formData, {
        headers: { ...authHeaders, 'Content-Type': 'multipart/form-data' }
      })

      if (response.data.success && response.data.transcription) {
        updateCardState(gapId, {
          answer: (cardStates[gapId]?.answer || '') + ' ' + response.data.transcription.text
        })
      }
    } catch (error) {
      console.error('Error transcribing audio:', error)
    }
  }

  // Filter gaps by time strategy
  const getFilteredGaps = () => {
    let filtered = gaps.filter(g => !g.answered && !g.skipped)

    // Calculate total time and filter based on strategy
    let timeLimit = parseInt(timeStrategy)
    let totalTime = 0
    const result: KnowledgeGap[] = []

    // Sort by priority first
    const priorityOrder = { high: 0, medium: 1, low: 2 }
    filtered.sort((a, b) => {
      const aPri = (a.priority?.toLowerCase() || 'medium') as keyof typeof priorityOrder
      const bPri = (b.priority?.toLowerCase() || 'medium') as keyof typeof priorityOrder
      return (priorityOrder[aPri] || 1) - (priorityOrder[bPri] || 1)
    })

    for (const gap of filtered) {
      const estTime = gap.estimated_time || 3
      if (totalTime + estTime <= timeLimit) {
        result.push(gap)
        totalTime += estTime
      }
    }

    return result
  }

  const filteredGaps = getFilteredGaps()
  const totalAnswered = gaps.filter(g => g.answered).length
  const totalPending = gaps.filter(g => !g.answered && !g.skipped).length
  const sessionProgress = filteredGaps.length > 0
    ? Math.round((sessionAnswered / filteredGaps.length) * 100)
    : 0

  // Gap Card Component
  const GapCard = ({ gap, index, isFocused }: { gap: KnowledgeGap; index: number; isFocused?: boolean }) => {
    const state = cardStates[gap.id] || { inputMode: 'type', answer: '', isRecording: false, audioLevel: 0 }

    return (
      <div
        style={{
          backgroundColor: colors.cardBg,
          borderRadius: '12px',
          border: `1px solid ${gap.flagged ? colors.statusOrange : colors.border}`,
          boxShadow: isFocused ? shadows.md : shadows.sm,
          padding: '24px',
          marginBottom: isFocused ? 0 : '16px',
          transition: 'all 0.2s ease',
        }}
      >
        {/* Category & Priority Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          {gap.category && (
            <span style={{
              padding: '4px 10px',
              backgroundColor: colors.primaryLight,
              color: colors.primary,
              fontSize: '11px',
              fontWeight: 600,
              borderRadius: '12px',
              textTransform: 'uppercase',
            }}>
              {gap.category}
            </span>
          )}
          {gap.priority && (
            <span style={{
              padding: '4px 10px',
              backgroundColor: gap.priority === 'high' ? '#FEE2E2' : gap.priority === 'low' ? '#F3F4F6' : '#FEF3C7',
              color: gap.priority === 'high' ? colors.statusRed : gap.priority === 'low' ? colors.textMuted : colors.statusOrange,
              fontSize: '11px',
              fontWeight: 600,
              borderRadius: '12px',
              textTransform: 'uppercase',
            }}>
              {gap.priority}
            </span>
          )}
          {gap.flagged && (
            <span style={{ fontSize: '14px' }}>🚩</span>
          )}
          <span style={{
            marginLeft: 'auto',
            fontSize: '12px',
            color: colors.textMuted,
          }}>
            ~{gap.estimated_time || 3} min
          </span>
        </div>

        {/* Question Text */}
        <h3 style={{
          fontSize: isFocused ? '20px' : '16px',
          fontWeight: 600,
          color: colors.textPrimary,
          marginBottom: '16px',
          lineHeight: 1.5,
        }}>
          {gap.description}
        </h3>

        {/* Context/Evidence */}
        {gap.context && (
          <p style={{
            fontSize: '13px',
            color: colors.textSecondary,
            marginBottom: '16px',
            padding: '12px',
            backgroundColor: colors.borderLight,
            borderRadius: '8px',
            lineHeight: 1.6,
          }}>
            <strong>Context:</strong> {gap.context}
          </p>
        )}

        {/* Input Mode Toggle */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '12px',
        }}>
          <button
            onClick={() => updateCardState(gap.id, { inputMode: 'type' })}
            style={{
              padding: '8px 16px',
              backgroundColor: state.inputMode === 'type' ? colors.primary : 'transparent',
              color: state.inputMode === 'type' ? '#fff' : colors.textSecondary,
              border: `1px solid ${state.inputMode === 'type' ? colors.primary : colors.border}`,
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
            </svg>
            Type Answer
          </button>
          <button
            onClick={() => updateCardState(gap.id, { inputMode: 'speak' })}
            style={{
              padding: '8px 16px',
              backgroundColor: state.inputMode === 'speak' ? colors.primary : 'transparent',
              color: state.inputMode === 'speak' ? '#fff' : colors.textSecondary,
              border: `1px solid ${state.inputMode === 'speak' ? colors.primary : colors.border}`,
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
            Speak Answer
          </button>
        </div>

        {/* Input Area */}
        {state.inputMode === 'type' ? (
          <textarea
            value={state.answer}
            onChange={(e) => updateCardState(gap.id, { answer: e.target.value })}
            placeholder="Type your answer here..."
            style={{
              width: '100%',
              minHeight: isFocused ? '120px' : '80px',
              padding: '12px 16px',
              backgroundColor: colors.borderLight,
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              color: colors.textPrimary,
              resize: 'vertical',
              outline: 'none',
              fontFamily: 'inherit',
            }}
          />
        ) : (
          <div style={{
            padding: '20px',
            backgroundColor: colors.borderLight,
            borderRadius: '8px',
            textAlign: 'center',
          }}>
            <button
              onClick={() => state.isRecording ? stopRecording(gap.id) : startRecording(gap.id)}
              style={{
                width: '80px',
                height: '80px',
                borderRadius: '50%',
                backgroundColor: state.isRecording ? colors.statusRed : colors.primary,
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 12px',
                boxShadow: state.isRecording ? `0 0 0 8px rgba(239, 68, 68, 0.2), 0 0 0 16px rgba(239, 68, 68, 0.1)` : 'none',
                animation: state.isRecording ? 'pulse 1.5s ease-in-out infinite' : 'none',
                transition: 'all 0.2s ease',
              }}
            >
              <svg width="32" height="32" viewBox="0 0 24 24" fill="#fff" stroke="none">
                {state.isRecording ? (
                  <rect x="6" y="6" width="12" height="12" rx="2"/>
                ) : (
                  <>
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" fill="none" stroke="#fff" strokeWidth="2"/>
                  </>
                )}
              </svg>
            </button>
            <p style={{ fontSize: '14px', color: colors.textSecondary }}>
              {state.isRecording ? 'Recording... Click to stop' : 'Click to start recording'}
            </p>
            {state.isRecording && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '2px',
                marginTop: '12px',
              }}>
                {Array.from({ length: 12 }).map((_, i) => (
                  <div
                    key={i}
                    style={{
                      width: '4px',
                      height: state.audioLevel > (i * 8) ? '24px' : '8px',
                      backgroundColor: state.audioLevel > (i * 8) ? colors.primary : colors.border,
                      borderRadius: '2px',
                      transition: 'height 0.1s ease',
                    }}
                  />
                ))}
              </div>
            )}
            {state.answer && (
              <p style={{
                marginTop: '12px',
                padding: '12px',
                backgroundColor: colors.cardBg,
                borderRadius: '6px',
                fontSize: '13px',
                color: colors.textPrimary,
                textAlign: 'left',
              }}>
                {state.answer}
              </p>
            )}
          </div>
        )}

        {/* Card Actions */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: `1px solid ${colors.borderLight}`,
        }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => handleSkip(gap.id)}
              style={{
                padding: '8px 16px',
                backgroundColor: 'transparent',
                color: colors.textSecondary,
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="5 4 15 12 5 20 5 4"/>
                <line x1="19" y1="5" x2="19" y2="19"/>
              </svg>
              Skip
            </button>
            <button
              onClick={() => handleFlag(gap.id)}
              style={{
                padding: '8px 16px',
                backgroundColor: gap.flagged ? '#FEF3C7' : 'transparent',
                color: gap.flagged ? colors.statusOrange : colors.textSecondary,
                border: `1px solid ${gap.flagged ? colors.statusOrange : colors.border}`,
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill={gap.flagged ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2">
                <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/>
                <line x1="4" y1="22" x2="4" y2="15"/>
              </svg>
              Flag
            </button>
          </div>
          <button
            onClick={() => handleSubmitAnswer(gap.id)}
            disabled={!state.answer.trim() || submittingId === gap.id}
            style={{
              padding: '10px 24px',
              backgroundColor: state.answer.trim() ? colors.primary : colors.border,
              color: state.answer.trim() ? '#fff' : colors.textMuted,
              border: 'none',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: 600,
              cursor: state.answer.trim() ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            {submittingId === gap.id ? 'Saving...' : 'Submit Answer'}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: colors.pageBg, display: 'flex', flexDirection: 'column' }}>
      {/* CSS for pulse animation */}
      <style jsx global>{`
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0.2), 0 0 0 16px rgba(239, 68, 68, 0.1); }
          50% { box-shadow: 0 0 0 12px rgba(239, 68, 68, 0.3), 0 0 0 24px rgba(239, 68, 68, 0.15); }
        }
      `}</style>

      {/* Top Navigation Bar */}
      <nav style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 32px',
        backgroundColor: colors.cardBg,
        borderBottom: `1px solid ${colors.border}`,
      }}>
        {/* Logo */}
        <div
          onClick={() => router.push('/')}
          style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}
        >
          <div style={{
            width: '36px',
            height: '36px',
            backgroundColor: colors.primary,
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: '14px',
          }}>
            2B
          </div>
          <span style={{ fontSize: '18px', fontWeight: 700, color: colors.textPrimary }}>
            Second Brain
          </span>
        </div>

        {/* Center Navigation */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
          {[
            { label: 'Chat', path: '/' },
            { label: 'Documents', path: '/documents' },
            { label: 'Knowledge Gaps', path: '/knowledge-gaps', active: true },
            { label: 'Integrations', path: '/integrations' },
            { label: 'Training Guides', path: '/training-guides' },
          ].map((item) => (
            <button
              key={item.label}
              onClick={() => router.push(item.path)}
              style={{
                background: 'none',
                border: 'none',
                padding: '8px 0',
                fontSize: '14px',
                fontWeight: 500,
                color: item.active ? colors.primary : colors.textSecondary,
                cursor: 'pointer',
                borderBottom: item.active ? `2px solid ${colors.primary}` : '2px solid transparent',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Right Cluster */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            onClick={() => router.push('/settings')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              backgroundColor: colors.cardBg,
              border: `1px solid ${colors.border}`,
              borderRadius: '20px',
              cursor: 'pointer',
            }}
          >
            <div style={{
              width: '28px',
              height: '28px',
              backgroundColor: colors.primary,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontSize: '12px',
              fontWeight: 600,
            }}>
              {user?.email?.charAt(0).toUpperCase() || 'U'}
            </div>
            <span style={{ fontSize: '14px', fontWeight: 500, color: colors.textPrimary }}>
              My Account
            </span>
          </button>
        </div>
      </nav>

      {/* Progress Bar */}
      <div style={{
        padding: '16px 32px',
        backgroundColor: colors.cardBg,
        borderBottom: `1px solid ${colors.border}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '13px', fontWeight: 500, color: colors.textSecondary }}>
            Session Progress
          </span>
          <span style={{ fontSize: '13px', fontWeight: 600, color: colors.primary }}>
            {sessionAnswered}/{filteredGaps.length} completed ({sessionProgress}%)
          </span>
        </div>
        <div style={{
          height: '8px',
          backgroundColor: colors.borderLight,
          borderRadius: '4px',
          overflow: 'hidden',
        }}>
          <div style={{
            width: `${sessionProgress}%`,
            height: '100%',
            backgroundColor: colors.primary,
            borderRadius: '4px',
            transition: 'width 0.3s ease',
          }} />
        </div>
      </div>

      {/* Main Content */}
      <main style={{ flex: 1, padding: '32px', paddingBottom: '100px' }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px',
        }}>
          <h1 style={{ fontSize: '28px', fontWeight: 700, color: colors.textPrimary, margin: 0 }}>
            Knowledge Gaps
          </h1>
          <button
            onClick={generateQuestions}
            disabled={generating}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              backgroundColor: generating ? colors.textMuted : colors.primary,
              border: 'none',
              borderRadius: '8px',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 500,
              cursor: generating ? 'not-allowed' : 'pointer',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.35-4.35"/>
            </svg>
            {generating ? 'Analyzing...' : 'Find Gaps'}
          </button>
        </div>

        {/* Strategy Bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px',
          padding: '16px 20px',
          backgroundColor: colors.cardBg,
          borderRadius: '12px',
          border: `1px solid ${colors.border}`,
        }}>
          {/* Time Strategy Pills */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 500, color: colors.textSecondary, marginRight: '8px' }}>
              Strategy:
            </span>
            {[
              { value: '10', label: '10 Mins', desc: 'Essential' },
              { value: '30', label: '30 Mins', desc: 'Standard' },
              { value: '90', label: '1.5 Hours', desc: 'Deep Dive' },
            ].map((option) => (
              <button
                key={option.value}
                onClick={() => setTimeStrategy(option.value as typeof timeStrategy)}
                style={{
                  padding: '8px 16px',
                  backgroundColor: timeStrategy === option.value ? colors.primaryLight : 'transparent',
                  color: timeStrategy === option.value ? colors.primary : colors.textSecondary,
                  border: `1px solid ${timeStrategy === option.value ? colors.primary : colors.border}`,
                  borderRadius: '20px',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {option.label}
              </button>
            ))}
          </div>

          {/* View Mode Toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => { setViewMode('focus'); setCurrentGapIndex(0) }}
              style={{
                padding: '8px 16px',
                backgroundColor: viewMode === 'focus' ? colors.primary : 'transparent',
                color: viewMode === 'focus' ? '#fff' : colors.textSecondary,
                border: `1px solid ${viewMode === 'focus' ? colors.primary : colors.border}`,
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
              Start Answering
            </button>
            <button
              onClick={() => setViewMode('list')}
              style={{
                padding: '8px 16px',
                backgroundColor: viewMode === 'list' ? colors.primary : 'transparent',
                color: viewMode === 'list' ? '#fff' : colors.textSecondary,
                border: `1px solid ${viewMode === 'list' ? colors.primary : colors.border}`,
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="8" y1="6" x2="21" y2="6"/>
                <line x1="8" y1="12" x2="21" y2="12"/>
                <line x1="8" y1="18" x2="21" y2="18"/>
                <line x1="3" y1="6" x2="3.01" y2="6"/>
                <line x1="3" y1="12" x2="3.01" y2="12"/>
                <line x1="3" y1="18" x2="3.01" y2="18"/>
              </svg>
              View All Gaps
            </button>
          </div>
        </div>

        {/* Stats */}
        <div style={{
          display: 'flex',
          gap: '16px',
          marginBottom: '24px',
        }}>
          {[
            { label: 'Total Gaps', value: gaps.length, color: colors.textPrimary },
            { label: 'Pending', value: totalPending, color: colors.statusOrange },
            { label: 'Answered', value: totalAnswered, color: colors.statusGreen },
            { label: 'In Session', value: filteredGaps.length, color: colors.primary },
          ].map((stat) => (
            <div
              key={stat.label}
              style={{
                flex: 1,
                padding: '16px 20px',
                backgroundColor: colors.cardBg,
                borderRadius: '10px',
                border: `1px solid ${colors.border}`,
              }}
            >
              <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '4px' }}>
                {stat.label}
              </div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: stat.color }}>
                {stat.value}
              </div>
            </div>
          ))}
        </div>

        {/* Content */}
        {loading ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '80px',
          }}>
            <div style={{
              width: '40px',
              height: '40px',
              border: `3px solid ${colors.border}`,
              borderTop: `3px solid ${colors.primary}`,
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
            }} />
            <style jsx>{`
              @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
              }
            `}</style>
          </div>
        ) : gaps.length === 0 ? (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '80px',
            backgroundColor: colors.cardBg,
            borderRadius: '12px',
            border: `1px solid ${colors.border}`,
          }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔍</div>
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 8px' }}>
              No knowledge gaps found
            </h3>
            <p style={{ fontSize: '14px', color: colors.textMuted, marginBottom: '24px' }}>
              Analyze your documents to identify knowledge gaps
            </p>
            <button
              onClick={generateQuestions}
              disabled={generating}
              style={{
                padding: '12px 24px',
                backgroundColor: colors.primary,
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              {generating ? 'Analyzing...' : 'Analyze Documents'}
            </button>
          </div>
        ) : viewMode === 'focus' ? (
          // Focus Mode - One card at a time
          <div style={{ maxWidth: '800px', margin: '0 auto' }}>
            {filteredGaps.length > 0 ? (
              <>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '16px',
                }}>
                  <span style={{ fontSize: '14px', color: colors.textMuted }}>
                    Question {currentGapIndex + 1} of {filteredGaps.length}
                  </span>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => setCurrentGapIndex(prev => Math.max(0, prev - 1))}
                      disabled={currentGapIndex === 0}
                      style={{
                        padding: '6px 12px',
                        backgroundColor: 'transparent',
                        border: `1px solid ${colors.border}`,
                        borderRadius: '6px',
                        color: currentGapIndex === 0 ? colors.textMuted : colors.textSecondary,
                        cursor: currentGapIndex === 0 ? 'not-allowed' : 'pointer',
                      }}
                    >
                      ← Previous
                    </button>
                    <button
                      onClick={() => setCurrentGapIndex(prev => Math.min(filteredGaps.length - 1, prev + 1))}
                      disabled={currentGapIndex === filteredGaps.length - 1}
                      style={{
                        padding: '6px 12px',
                        backgroundColor: 'transparent',
                        border: `1px solid ${colors.border}`,
                        borderRadius: '6px',
                        color: currentGapIndex === filteredGaps.length - 1 ? colors.textMuted : colors.textSecondary,
                        cursor: currentGapIndex === filteredGaps.length - 1 ? 'not-allowed' : 'pointer',
                      }}
                    >
                      Next →
                    </button>
                  </div>
                </div>
                <GapCard gap={filteredGaps[currentGapIndex]} index={currentGapIndex} isFocused />
              </>
            ) : (
              <div style={{
                textAlign: 'center',
                padding: '40px',
                backgroundColor: colors.cardBg,
                borderRadius: '12px',
                border: `1px solid ${colors.border}`,
              }}>
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎉</div>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary }}>
                  All done for this session!
                </h3>
                <p style={{ fontSize: '14px', color: colors.textMuted }}>
                  You've answered all gaps in your {timeStrategy} minute strategy.
                </p>
              </div>
            )}
          </div>
        ) : (
          // List Mode - All cards
          <div>
            {filteredGaps.length > 0 ? (
              filteredGaps.map((gap, index) => (
                <GapCard key={gap.id} gap={gap} index={index} />
              ))
            ) : (
              <div style={{
                textAlign: 'center',
                padding: '40px',
                backgroundColor: colors.cardBg,
                borderRadius: '12px',
                border: `1px solid ${colors.border}`,
              }}>
                <p style={{ fontSize: '14px', color: colors.textMuted }}>
                  No pending gaps for this time strategy. Try a longer session or find new gaps.
                </p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Sticky Footer */}
      <div style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        padding: '16px 32px',
        backgroundColor: colors.cardBg,
        borderTop: `1px solid ${colors.border}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 -4px 6px -1px rgba(0, 0, 0, 0.1)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontSize: '14px', color: colors.textSecondary }}>
            Session: {sessionAnswered} answered, {sessionSkipped} skipped
          </span>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={() => router.push('/documents')}
            style={{
              padding: '10px 20px',
              backgroundColor: 'transparent',
              border: `1px solid ${colors.primary}`,
              borderRadius: '8px',
              color: colors.primary,
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Save for Later
          </button>
          <button
            onClick={() => {
              alert(`Session complete! You answered ${sessionAnswered} questions.`)
              router.push('/documents')
            }}
            style={{
              padding: '10px 20px',
              backgroundColor: colors.primary,
              border: 'none',
              borderRadius: '8px',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Complete Session
          </button>
        </div>
      </div>
    </div>
  )
}
