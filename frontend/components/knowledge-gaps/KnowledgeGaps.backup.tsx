'use client'

import React, { useState, useEffect } from 'react'
import Sidebar from '../shared/Sidebar'
import Image from 'next/image'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'

const API_BASE = 'http://localhost:5003/api'

// Add pulse animation for voice recording
const pulseKeyframes = `
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.05); }
}
`

interface KnowledgeGap {
  id: string
  type: string
  description: string
  project: string
  project_id?: string
  severity: 'high' | 'medium' | 'low'
  category?: string
  questions?: string[]
  is_standard: boolean
  answered?: boolean
  answer?: string
  status?: string
}

interface ProjectGaps {
  project: string
  gaps: KnowledgeGap[]
  answeredCount: number
  totalCount: number
}

const SeverityBadge = ({ severity }: { severity: string }) => {
  const colors = {
    high: { bg: '#FEE2E2', text: '#DC2626', border: '#FCA5A5' },
    medium: { bg: '#FEF3C7', text: '#D97706', border: '#FCD34D' },
    low: { bg: '#D1FAE5', text: '#059669', border: '#6EE7B7' }
  }
  const color = colors[severity as keyof typeof colors] || colors.medium

  return (
    <span
      style={{
        display: 'inline-flex',
        padding: '2px 8px',
        borderRadius: '12px',
        backgroundColor: color.bg,
        border: `1px solid ${color.border}`,
        color: color.text,
        fontFamily: 'Inter, sans-serif',
        fontSize: '10px',
        fontWeight: 500,
        textTransform: 'capitalize'
      }}
    >
      {severity}
    </span>
  )
}

const QuestionTypeBadge = ({ type }: { type: string }) => {
  const typeLabels: Record<string, string> = {
    project_goal: 'Goal',
    success_criteria: 'Success Metrics',
    project_outcome: 'Outcome',
    key_decision: 'Decision',
    lesson_learned: 'Lesson',
    stakeholder: 'Stakeholder',
    process: 'Process',
    risk: 'Risk'
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        padding: '2px 8px',
        borderRadius: '4px',
        backgroundColor: '#E0E7FF',
        color: '#3730A3',
        fontFamily: 'Inter, sans-serif',
        fontSize: '10px',
        fontWeight: 500
      }}
    >
      {typeLabels[type] || type}
    </span>
  )
}

// Microphone button component for voice input using OpenAI Whisper
const VoiceInputButton = ({
  onTranscript,
  isListening,
  onListeningChange,
  authHeaders
}: {
  onTranscript: (text: string) => void
  isListening: boolean
  onListeningChange: (listening: boolean) => void
  authHeaders: Record<string, string>
}) => {
  const [isTranscribing, setIsTranscribing] = React.useState(false)
  const mediaRecorderRef = React.useRef<MediaRecorder | null>(null)
  const chunksRef = React.useRef<Blob[]>([])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      mediaRecorder.onstop = async () => {
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop())

        // Create blob and send to Whisper API
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' })

        if (audioBlob.size > 0) {
          setIsTranscribing(true)
          try {
            const formData = new FormData()
            formData.append('audio', audioBlob, 'recording.webm')

            const response = await axios.post(`${API_BASE}/knowledge/transcribe`, formData, {
              headers: {
                'Content-Type': 'multipart/form-data',
                ...authHeaders
              }
            })

            if (response.data.transcript) {
              onTranscript(response.data.transcript)
            }
          } catch (error) {
            console.error('Transcription error:', error)
            alert('Failed to transcribe audio. Please try again.')
          } finally {
            setIsTranscribing(false)
          }
        }

        onListeningChange(false)
      }

      mediaRecorder.start(1000) // Collect data every second
      onListeningChange(true)
    } catch (error) {
      console.error('Microphone access error:', error)
      alert('Could not access microphone. Please allow microphone access.')
      onListeningChange(false)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
  }

  const handleClick = () => {
    if (isListening) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={isTranscribing}
      style={{
        width: '36px',
        height: '36px',
        borderRadius: '8px',
        backgroundColor: isTranscribing ? '#F59E0B' : isListening ? '#EF4444' : '#F3F4F6',
        border: 'none',
        cursor: isTranscribing ? 'wait' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all 0.2s',
        animation: isListening ? 'pulse 1.5s infinite' : 'none'
      }}
      title={isTranscribing ? 'Transcribing with Whisper...' : isListening ? 'Stop recording' : 'Start voice input (Whisper AI)'}
    >
      {isTranscribing ? (
        <svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
        </svg>
      ) : isListening ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
          <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#374151" strokeWidth="2">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
      )}
    </button>
  )
}

const ProjectCard = ({
  projectGaps,
  isExpanded,
  onToggle,
  onAnswerQuestion,
  authHeaders
}: {
  projectGaps: ProjectGaps
  isExpanded: boolean
  onToggle: () => void
  onAnswerQuestion: (gap: KnowledgeGap, answer: string) => void
  authHeaders: Record<string, string>
}) => {
  const [answeringIndex, setAnsweringIndex] = useState<number | null>(null)
  const [answerText, setAnswerText] = useState('')
  const [isListening, setIsListening] = useState(false)

  const progress = projectGaps.totalCount > 0
    ? (projectGaps.answeredCount / projectGaps.totalCount) * 100
    : 0

  const handleSubmitAnswer = (gap: KnowledgeGap, index: number) => {
    if (answerText.trim()) {
      onAnswerQuestion(gap, answerText)
      setAnswerText('')
      setAnsweringIndex(null)
    }
  }

  return (
    <div
      style={{
        borderRadius: '12px',
        border: '1px solid #D4D4D8',
        backgroundColor: '#FFE2BF',
        overflow: 'hidden',
        marginBottom: '16px'
      }}
    >
      {/* Project Header */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '20px 24px',
          backgroundColor: isExpanded ? '#FFE2BF' : '#FFF',
          cursor: 'pointer',
          transition: 'background-color 0.2s'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              backgroundColor: '#FFE2BF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <span style={{ fontSize: '24px' }}>📋</span>
          </div>
          <div>
            <h3
              style={{
                color: '#18181B',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '18px',
                fontWeight: 600,
                marginBottom: '4px'
              }}
            >
              {projectGaps.project}
            </h3>
            <p
              style={{
                color: '#71717A',
                fontFamily: 'Inter, sans-serif',
                fontSize: '13px'
              }}
            >
              {projectGaps.answeredCount} of {projectGaps.totalCount} questions answered
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          {/* Progress Bar */}
          <div style={{ width: '160px' }}>
            <div
              style={{
                height: '8px',
                borderRadius: '4px',
                backgroundColor: '#E5E7EB',
                overflow: 'hidden'
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${progress}%`,
                  backgroundColor: progress === 100 ? '#10B981' : '#F97316',
                  borderRadius: '4px',
                  transition: 'width 0.3s'
                }}
              />
            </div>
            <p
              style={{
                color: '#71717A',
                fontFamily: 'Inter, sans-serif',
                fontSize: '11px',
                marginTop: '4px',
                textAlign: 'right'
              }}
            >
              {Math.round(progress)}% complete
            </p>
          </div>

          {/* Expand Icon */}
          <div
            style={{
              transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s'
            }}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M5 7.5L10 12.5L15 7.5" stroke="#71717A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
        </div>
      </div>

      {/* Questions List */}
      {isExpanded && (
        <div style={{ borderTop: '1px solid #E5E7EB' }}>
          {projectGaps.gaps.map((gap, index) => (
            <div
              key={index}
              style={{
                padding: '16px 24px',
                borderBottom: index < projectGaps.gaps.length - 1 ? '1px solid #F3F4F6' : 'none',
                backgroundColor: gap.answered ? '#FFF3E4' : '#FFE2BF'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <QuestionTypeBadge type={gap.type} />
                    <SeverityBadge severity={gap.severity} />
                    {gap.answered && (
                      <span style={{ color: '#10B981', fontSize: '12px' }}>✓ Answered</span>
                    )}
                  </div>
                  <p
                    style={{
                      color: '#18181B',
                      fontFamily: 'Inter, sans-serif',
                      fontSize: '14px',
                      fontWeight: 500,
                      lineHeight: '1.5'
                    }}
                  >
                    {gap.description}
                  </p>

                  {/* Show answer if exists */}
                  {gap.answered && gap.answer && (
                    <div
                      style={{
                        marginTop: '12px',
                        padding: '12px',
                        backgroundColor: '#F0FDF4',
                        borderRadius: '8px',
                        borderLeft: '3px solid #10B981'
                      }}
                    >
                      <p style={{ color: '#166534', fontFamily: 'Inter, sans-serif', fontSize: '13px' }}>
                        {gap.answer}
                      </p>
                    </div>
                  )}

                  {/* Answer Input */}
                  {answeringIndex === index && (
                    <div style={{ marginTop: '12px' }}>
                      <div style={{ position: 'relative' }}>
                        <textarea
                          value={answerText}
                          onChange={(e) => setAnswerText(e.target.value)}
                          placeholder={isListening ? "Listening... speak now" : "Type your answer or click the mic to speak..."}
                          style={{
                            width: '100%',
                            minHeight: '80px',
                            padding: '12px',
                            paddingRight: '50px',
                            borderRadius: '8px',
                            border: isListening ? '2px solid #EF4444' : '1px solid #D4D4D8',
                            fontFamily: 'Inter, sans-serif',
                            fontSize: '14px',
                            resize: 'vertical',
                            outline: 'none',
                            backgroundColor: isListening ? '#FEF2F2' : 'white',
                            transition: 'all 0.2s'
                          }}
                        />
                        <div style={{ position: 'absolute', right: '8px', top: '8px' }}>
                          <VoiceInputButton
                            isListening={isListening}
                            onListeningChange={setIsListening}
                            onTranscript={(text) => setAnswerText(prev => prev ? `${prev} ${text}` : text)}
                            authHeaders={authHeaders}
                          />
                        </div>
                      </div>
                      {isListening && (
                        <p style={{
                          color: '#EF4444',
                          fontFamily: 'Inter, sans-serif',
                          fontSize: '12px',
                          marginTop: '4px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px'
                        }}>
                          <span style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            backgroundColor: '#EF4444',
                            animation: 'pulse 1s infinite'
                          }} />
                          Recording... click mic to stop
                        </p>
                      )}
                      <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                        <button
                          onClick={() => handleSubmitAnswer(gap, index)}
                          style={{
                            padding: '8px 16px',
                            borderRadius: '6px',
                            backgroundColor: '#F97316',
                            color: 'white',
                            border: 'none',
                            fontFamily: 'Inter, sans-serif',
                            fontSize: '13px',
                            fontWeight: 500,
                            cursor: 'pointer'
                          }}
                        >
                          Submit Answer
                        </button>
                        <button
                          onClick={() => {
                            setAnsweringIndex(null)
                            setAnswerText('')
                          }}
                          style={{
                            padding: '8px 16px',
                            borderRadius: '6px',
                            backgroundColor: '#F3F4F6',
                            color: '#374151',
                            border: 'none',
                            fontFamily: 'Inter, sans-serif',
                            fontSize: '13px',
                            fontWeight: 500,
                            cursor: 'pointer'
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Answer Button */}
                {!gap.answered && answeringIndex !== index && (
                  <button
                    onClick={() => setAnsweringIndex(index)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '6px',
                      backgroundColor: '#FFE2BF',
                      color: '#18181B',
                      border: 'none',
                      fontFamily: 'Inter, sans-serif',
                      fontSize: '12px',
                      fontWeight: 500,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    Answer
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function KnowledgeGaps() {
  const [activeItem, setActiveItem] = useState('Knowledge Gaps')
  const [projectGaps, setProjectGaps] = useState<ProjectGaps[]>([])
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'unanswered' | 'answered'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [generating, setGenerating] = useState(false)
  const [generationStatus, setGenerationStatus] = useState<string>('')
  const [completing, setCompleting] = useState(false)
  const [completionStatus, setCompletionStatus] = useState<string>('')

  const authHeaders = useAuthHeaders()
  const { token } = useAuth()

  useEffect(() => {
    if (token) {
      loadKnowledgeGaps()
    }
  }, [token])

  const generateQuestions = async () => {
    setGenerating(true)
    setGenerationStatus('Analyzing documents with GPT-4o...')
    try {
      // Use the correct knowledge/analyze endpoint
      const response = await axios.post(`${API_BASE}/knowledge/analyze`, {
        force: true,
        include_pending: true
      }, { headers: authHeaders })

      if (response.data.success) {
        const gapCount = response.data.results?.gaps?.length || 0
        const docsAnalyzed = response.data.results?.total_documents_analyzed || 0
        setGenerationStatus(`Found ${gapCount} knowledge gaps from ${docsAnalyzed} documents!`)
        // Reload gaps
        await loadKnowledgeGaps()
      } else {
        setGenerationStatus('Failed to analyze documents: ' + (response.data.error || 'Unknown error'))
      }
    } catch (error: any) {
      console.error('Error generating questions:', error)
      const errorMsg = error.response?.data?.error || error.message || 'Unknown error'
      setGenerationStatus('Error analyzing documents: ' + errorMsg)
    } finally {
      setGenerating(false)
      // Clear status after 5 seconds
      setTimeout(() => setGenerationStatus(''), 5000)
    }
  }

  const completeProcess = async () => {
    setCompleting(true)
    setCompletionStatus('Integrating answers into knowledge base...')
    try {
      const response = await axios.post(`${API_BASE}/knowledge/complete-process`, {
        mark_completed: true
      }, { headers: authHeaders })

      if (response.data.success) {
        const results = response.data.results
        setCompletionStatus(
          `Knowledge base updated! ${results.answers_integrated} answers integrated, ` +
          `${results.documents_indexed} documents indexed, ${results.chunks_created} searchable chunks created.`
        )
        // Reload gaps to show updated status
        await loadKnowledgeGaps()
      } else {
        setCompletionStatus('Failed to complete process: ' + (response.data.error || 'Unknown error'))
      }
    } catch (error: any) {
      console.error('Error completing process:', error)
      const errorMsg = error.response?.data?.error || error.message || 'Unknown error'
      setCompletionStatus('Error: ' + errorMsg)
    } finally {
      setCompleting(false)
      // Clear status after 8 seconds
      setTimeout(() => setCompletionStatus(''), 8000)
    }
  }

  const loadKnowledgeGaps = async () => {
    try {
      // Use the correct /api/knowledge/gaps endpoint with auth
      const response = await axios.get(`${API_BASE}/knowledge/gaps`, {
        headers: authHeaders
      })

      console.log('Knowledge gaps API response:', response.data)

      // Backend returns { success: true, gaps: [...], pagination: {...} }
      if (response.data.success && response.data.gaps) {
        // Group gaps by their title (each gap is a knowledge area with multiple questions)
        const grouped: Record<string, KnowledgeGap[]> = {}

        response.data.gaps.forEach((gap: any) => {
          // Use gap.title as the project/group name, fallback to category
          const groupName = gap.title || gap.category || 'General Knowledge Gaps'

          // Backend questions format: [{text: "...", answered: false}, ...]
          const questions = gap.questions || []

          // If no questions, use the description as a single question
          if (questions.length === 0 && gap.description) {
            const mappedGap: KnowledgeGap = {
              id: gap.id,
              type: gap.category || 'general',
              description: gap.description,
              project: groupName,
              project_id: gap.project_id,
              severity: gap.priority >= 4 ? 'high' : gap.priority <= 2 ? 'low' : 'medium',
              category: gap.category,
              is_standard: false,
              answered: gap.status === 'answered' || gap.status === 'verified' || gap.status === 'closed',
              answer: '',
              status: gap.status
            }
            if (!grouped[groupName]) {
              grouped[groupName] = []
            }
            grouped[groupName].push(mappedGap)
          } else {
            // Process each question in the gap
            questions.forEach((question: any, qIndex: number) => {
              // question can be {text: "...", answered: false} or just a string
              const questionText = typeof question === 'string' ? question : question.text || ''
              const isAnswered = typeof question === 'object' ? question.answered : false

              // Get answer if available from gap.answers array
              const answerObj = gap.answers?.find((a: any) => a.question_index === qIndex)

              const mappedGap: KnowledgeGap = {
                id: `${gap.id}_${qIndex}`, // Unique ID for each question
                type: gap.category || 'general',
                description: questionText,
                project: groupName,
                project_id: gap.project_id,
                severity: gap.priority >= 4 ? 'high' : gap.priority <= 2 ? 'low' : 'medium',
                category: gap.category,
                is_standard: false,
                answered: isAnswered || gap.status === 'answered' || gap.status === 'verified' || gap.status === 'closed',
                answer: answerObj?.answer_text || '',
                status: gap.status
              }

              if (!grouped[groupName]) {
                grouped[groupName] = []
              }
              grouped[groupName].push(mappedGap)
            })
          }
        })

        const projectList: ProjectGaps[] = Object.entries(grouped).map(([project, gaps]) => ({
          project,
          gaps,
          answeredCount: gaps.filter(g => g.answered).length,
          totalCount: gaps.length
        }))

        // Sort by completion (least complete first)
        projectList.sort((a, b) => {
          const aPercent = a.totalCount > 0 ? a.answeredCount / a.totalCount : 0
          const bPercent = b.totalCount > 0 ? b.answeredCount / b.totalCount : 0
          return aPercent - bPercent
        })

        console.log('Processed project gaps:', projectList)
        setProjectGaps(projectList)
      } else {
        console.log('No gaps found or API returned success: false', response.data)
        setProjectGaps([])
      }
    } catch (error: any) {
      console.error('Error loading knowledge gaps:', error)
      // Don't show error if it's just no gaps
      if (error.response?.status !== 404) {
        console.error('API Error:', error.response?.data?.error || error.message)
      }
    } finally {
      setLoading(false)
    }
  }

  const toggleProject = (project: string) => {
    setExpandedProjects(prev => {
      const next = new Set(prev)
      if (next.has(project)) {
        next.delete(project)
      } else {
        next.add(project)
      }
      return next
    })
  }

  const handleAnswerQuestion = async (gap: KnowledgeGap, answer: string) => {
    try {
      // Extract original gap ID and question index from composite ID (format: "gapId_questionIndex")
      const idParts = gap.id.split('_')
      const questionIndex = idParts.length > 1 ? parseInt(idParts[idParts.length - 1]) : 0
      // Join all parts except the last one (in case gap ID itself contains underscores)
      const originalGapId = idParts.length > 1 ? idParts.slice(0, -1).join('_') : gap.id

      // Use the correct /api/knowledge/gaps/<gap_id>/answers endpoint
      await axios.post(`${API_BASE}/knowledge/gaps/${originalGapId}/answers`, {
        question_index: questionIndex,
        answer_text: answer
      }, { headers: authHeaders })

      // Update local state
      setProjectGaps(prev => prev.map(pg => {
        if (pg.project === gap.project) {
          return {
            ...pg,
            gaps: pg.gaps.map(g =>
              g.id === gap.id && g.description === gap.description
                ? { ...g, answered: true, answer }
                : g
            ),
            answeredCount: pg.answeredCount + 1
          }
        }
        return pg
      }))
    } catch (error: any) {
      console.error('Error submitting answer:', error)
      const errorMsg = error.response?.data?.error || error.message || 'Unknown error'
      alert(`Failed to submit answer: ${errorMsg}`)
    }
  }

  // Filter projects based on search and filter
  const filteredProjects = projectGaps.filter(pg => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      const matchesProject = pg.project.toLowerCase().includes(query)
      const matchesQuestion = pg.gaps.some(g => g.description.toLowerCase().includes(query))
      if (!matchesProject && !matchesQuestion) return false
    }

    // Status filter
    if (filter === 'unanswered' && pg.answeredCount === pg.totalCount) return false
    if (filter === 'answered' && pg.answeredCount === 0) return false

    return true
  })

  const totalQuestions = projectGaps.reduce((sum, pg) => sum + pg.totalCount, 0)
  const totalAnswered = projectGaps.reduce((sum, pg) => sum + pg.answeredCount, 0)

  return (
    <div className="flex h-screen bg-primary overflow-hidden">
      <style dangerouslySetInnerHTML={{ __html: pulseKeyframes }} />
      <Sidebar activeItem={activeItem} onItemClick={setActiveItem} />

      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 bg-primary">
          <div>
            <h1
              style={{
                color: '#18181B',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '28px',
                fontWeight: 600,
                letterSpacing: '-0.56px',
                marginBottom: '8px'
              }}
            >
              Knowledge Gaps
            </h1>
            <p
              style={{
                color: '#71717A',
                fontFamily: 'Inter, sans-serif',
                fontSize: '15px',
                lineHeight: '22px'
              }}
            >
              Questions the AI needs answered to fully capture project knowledge before team transitions
            </p>
          </div>

          {/* Stats and Generate Button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '24px',
                padding: '16px 24px',
                backgroundColor: '#FFE2BF',
                borderRadius: '12px'
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <p style={{ color: '#18181B', fontFamily: '"Work Sans"', fontSize: '24px', fontWeight: 600 }}>
                  {totalQuestions}
                </p>
                <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px' }}>Total Questions</p>
              </div>
              <div style={{ width: '1px', height: '40px', backgroundColor: '#D4D4D8' }} />
              <div style={{ textAlign: 'center' }}>
                <p style={{ color: '#10B981', fontFamily: '"Work Sans"', fontSize: '24px', fontWeight: 600 }}>
                  {totalAnswered}
                </p>
                <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px' }}>Answered</p>
              </div>
              <div style={{ width: '1px', height: '40px', backgroundColor: '#D4D4D8' }} />
              <div style={{ textAlign: 'center' }}>
                <p style={{ color: '#F97316', fontFamily: '"Work Sans"', fontSize: '24px', fontWeight: 600 }}>
                  {totalQuestions - totalAnswered}
                </p>
                <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px' }}>Pending</p>
              </div>
            </div>

            {/* Generate Questions Button */}
            <button
              onClick={generateQuestions}
              disabled={generating}
              style={{
                padding: '12px 20px',
                borderRadius: '10px',
                backgroundColor: generating ? '#D1D5DB' : '#6B7280',
                color: 'white',
                border: 'none',
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                cursor: generating ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                whiteSpace: 'nowrap'
              }}
            >
              {generating ? (
                <>
                  <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                  </svg>
                  Analyzing...
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                  </svg>
                  Generate Questions
                </>
              )}
            </button>

            {/* Complete Process Button */}
            <button
              onClick={completeProcess}
              disabled={completing}
              style={{
                padding: '12px 20px',
                borderRadius: '10px',
                backgroundColor: completing ? '#D1D5DB' : '#10B981',
                color: 'white',
                border: 'none',
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                cursor: completing ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                whiteSpace: 'nowrap'
              }}
              title="Integrate answers into knowledge base for chat"
            >
              {completing ? (
                <>
                  <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                  </svg>
                  Processing...
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                    <polyline points="22 4 12 14.01 9 11.01" />
                  </svg>
                  Complete Process
                </>
              )}
            </button>
          </div>
        </div>

        {/* Generation Status */}
        {generationStatus && (
          <div className="px-8 pb-2">
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: generationStatus.includes('Error') ? '#FEE2E2' : '#D1FAE5',
                borderRadius: '8px',
                color: generationStatus.includes('Error') ? '#DC2626' : '#059669',
                fontFamily: 'Inter, sans-serif',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              {generationStatus.includes('Error') ? '!' : '✓'} {generationStatus}
            </div>
          </div>
        )}

        {/* Completion Status */}
        {completionStatus && (
          <div className="px-8 pb-2">
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: completionStatus.includes('Error') ? '#FEE2E2' : '#DBEAFE',
                borderRadius: '8px',
                color: completionStatus.includes('Error') ? '#DC2626' : '#1D4ED8',
                fontFamily: 'Inter, sans-serif',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              {completionStatus.includes('Error') ? '!' : '✓'} {completionStatus}
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="px-8 pb-4 bg-primary">
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <input
              type="text"
              placeholder="Search projects or questions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '320px',
                height: '42px',
                padding: '0 16px',
                borderRadius: '8px',
                border: '1px solid #D4D4D8',
                backgroundColor: '#FFE2BF',
                outline: 'none',
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px'
              }}
            />

            <div style={{ display: 'flex', gap: '8px' }}>
              {(['all', 'unanswered', 'answered'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    backgroundColor: filter === f ? '#FFE2BF' : '#FFF',
                    border: '1px solid #D4D4D8',
                    color: '#18181B',
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '13px',
                    fontWeight: filter === f ? 500 : 400,
                    cursor: 'pointer',
                    textTransform: 'capitalize'
                  }}
                >
                  {f === 'all' ? 'All Projects' : f}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Projects List */}
        <div className="flex-1 overflow-y-auto px-8 py-4 bg-primary">
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
              <p style={{ fontFamily: 'Inter', fontSize: '14px', color: '#71717A' }}>
                Loading knowledge gaps...
              </p>
            </div>
          ) : filteredProjects.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
              <p style={{ fontFamily: 'Inter', fontSize: '14px', color: '#71717A' }}>
                No projects found matching your criteria.
              </p>
            </div>
          ) : (
            <div style={{ maxWidth: '900px' }}>
              {filteredProjects.map(pg => (
                <ProjectCard
                  key={pg.project}
                  projectGaps={pg}
                  isExpanded={expandedProjects.has(pg.project)}
                  onToggle={() => toggleProject(pg.project)}
                  onAnswerQuestion={handleAnswerQuestion}
                  authHeaders={authHeaders}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
