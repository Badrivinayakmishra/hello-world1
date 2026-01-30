'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '../shared/Sidebar'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import GapCard from './GapCard'
import GapFilters from './GapFilters'
import GapStats from './GapStats'
import GapAnswerPanel from './GapAnswerPanel'
import AnalysisModeSelector from './AnalysisModeSelector'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003') + '/api'

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
}

export default function KnowledgeGaps() {
  const router = useRouter()
  const [activeItem, setActiveItem] = useState('Knowledge Gaps')
  const [gaps, setGaps] = useState<KnowledgeGap[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [selectedGap, setSelectedGap] = useState<KnowledgeGap | null>(null)
  const [answer, setAnswer] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Filtering & Search
  const [filter, setFilter] = useState<'all' | 'unanswered' | 'answered'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedPriority, setSelectedPriority] = useState('')
  const [sortBy, setSortBy] = useState('default')

  // Analysis Mode
  const [analysisMode, setAnalysisMode] = useState('intelligent')

  // Video generation state
  const [showVideoModal, setShowVideoModal] = useState(false)
  const [videoTitle, setVideoTitle] = useState('')
  const [videoDescription, setVideoDescription] = useState('')
  const [includeAnswers, setIncludeAnswers] = useState(true)
  const [generatingVideo, setGeneratingVideo] = useState(false)
  const [videoProgress, setVideoProgress] = useState<{
    status: string
    progress_percent: number
    current_step: string
  } | null>(null)
  const [createdVideoId, setCreatedVideoId] = useState<string | null>(null)

  const authHeaders = useAuthHeaders()
  const { token } = useAuth()

  useEffect(() => {
    if (token) loadKnowledgeGaps()
  }, [token])

  useEffect(() => {
    if (selectedGap) {
      setAnswer(selectedGap.answer || '')
    }
  }, [selectedGap])

  const loadKnowledgeGaps = async () => {
    try {
      const response = await axios.get(`${API_BASE}/knowledge/gaps`, { headers: authHeaders })

      if (response.data.success && response.data.gaps) {
        const allGaps: KnowledgeGap[] = []

        response.data.gaps.forEach((gap: any) => {
          const groupName = gap.title || gap.category || 'General'
          const questions = gap.questions || []

          // Extract metadata from gap object
          const gapMetadata = {
            category: gap.category,
            priority: gap.priority || 'medium',
            quality_score: gap.quality_score,
            evidence: gap.evidence,
            context: gap.context || gap.description,
            detection_method: gap.detection_method || gap.source
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
                answered: isAnswered || gap.status === 'answered' || gap.status === 'verified' || gap.status === 'closed',
                answer: answerObj?.answer_text || '',
                ...gapMetadata
              })
            })
          }
        })

        setGaps(allGaps)
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
        mode: analysisMode
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

  const handleAnswerQuestion = async () => {
    if (!selectedGap || !answer.trim() || submitting) return

    setSubmitting(true)
    try {
      const idParts = selectedGap.id.split('_')
      const questionIndex = idParts.length > 1 ? parseInt(idParts[idParts.length - 1]) : 0
      const originalGapId = idParts.length > 1 ? idParts.slice(0, -1).join('_') : selectedGap.id

      await axios.post(`${API_BASE}/knowledge/gaps/${originalGapId}/answers`, {
        question_index: questionIndex,
        answer_text: answer
      }, { headers: authHeaders })

      setGaps(prev => prev.map(g =>
        g.id === selectedGap.id ? { ...g, answered: true, answer } : g
      ))

      setSelectedGap({ ...selectedGap, answered: true, answer })
      alert('Answer saved successfully!')
    } catch (error) {
      console.error('Error submitting answer:', error)
      alert('Failed to save answer. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleGapFeedback = async (helpful: boolean) => {
    if (!selectedGap) return

    try {
      const idParts = selectedGap.id.split('_')
      const originalGapId = idParts.length > 1 ? idParts.slice(0, -1).join('_') : selectedGap.id

      await axios.post(`${API_BASE}/knowledge/gaps/${originalGapId}/feedback`, {
        useful: helpful
      }, { headers: authHeaders })

      alert(helpful ? 'Thanks for the feedback!' : 'Feedback recorded. We\'ll improve gap detection.')
    } catch (error) {
      console.error('Error submitting feedback:', error)
    }
  }

  // Video generation functions
  const handleGenerateTrainingVideo = () => {
    if (gaps.length === 0) {
      alert('No gaps to create video from. Generate gaps first!')
      return
    }
    setShowVideoModal(true)
  }

  const createTrainingVideo = async () => {
    if (!videoTitle.trim()) {
      alert('Please enter a video title')
      return
    }

    setGeneratingVideo(true)
    try {
      const gapIds = gaps.map(g => {
        const gapId = g.id.includes('_') ? g.id.split('_')[0] : g.id
        return gapId
      }).filter((id, index, self) => self.indexOf(id) === index)

      const response = await axios.post(
        `${API_BASE}/videos`,
        {
          title: videoTitle,
          description: videoDescription || undefined,
          source_type: 'knowledge_gaps',
          source_ids: gapIds,
          include_answers: includeAnswers
        },
        { headers: authHeaders }
      )

      if (response.data.success) {
        const videoId = response.data.video.id
        setCreatedVideoId(videoId)
        pollVideoStatus(videoId)
      } else {
        alert('Failed to create video: ' + (response.data.error || 'Unknown error'))
        setGeneratingVideo(false)
      }
    } catch (error: any) {
      console.error('Error creating video:', error)
      alert('Failed to create video: ' + (error.response?.data?.error || error.message))
      setGeneratingVideo(false)
    }
  }

  const pollVideoStatus = async (videoId: string) => {
    try {
      const response = await axios.get(
        `${API_BASE}/videos/${videoId}/status`,
        { headers: authHeaders }
      )

      if (response.data.success) {
        setVideoProgress({
          status: response.data.status,
          progress_percent: response.data.progress_percent || 0,
          current_step: response.data.current_step || 'Processing...'
        })

        if (response.data.status === 'completed') {
          setTimeout(() => {
            setGeneratingVideo(false)
            setShowVideoModal(false)
            setVideoProgress(null)
            setCreatedVideoId(null)
            alert('Training video generated successfully! Redirecting to Training Guides...')
            router.push('/training-guides')
          }, 1500)
        } else if (response.data.status === 'failed') {
          setGeneratingVideo(false)
          setVideoProgress(null)
          alert('Video generation failed: ' + (response.data.error_message || 'Unknown error'))
        } else {
          setTimeout(() => pollVideoStatus(videoId), 3000)
        }
      }
    } catch (error: any) {
      console.error('Error polling video status:', error)
      setGeneratingVideo(false)
      setVideoProgress(null)
    }
  }

  // Filtering logic
  const getFilteredAndSortedGaps = () => {
    let filtered = gaps

    // Filter by status
    if (filter === 'answered') {
      filtered = filtered.filter(g => g.answered)
    } else if (filter === 'unanswered') {
      filtered = filtered.filter(g => !g.answered)
    }

    // Search
    if (searchQuery) {
      filtered = filtered.filter(g =>
        g.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        g.project.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    // Category filter
    if (selectedCategory) {
      filtered = filtered.filter(g => g.category === selectedCategory)
    }

    // Priority filter
    if (selectedPriority) {
      filtered = filtered.filter(g => g.priority === selectedPriority)
    }

    // Sort
    switch (sortBy) {
      case 'priority':
        const priorityOrder = { high: 0, medium: 1, low: 2 }
        filtered.sort((a, b) => {
          const aPri = a.priority?.toLowerCase() as keyof typeof priorityOrder || 'medium'
          const bPri = b.priority?.toLowerCase() as keyof typeof priorityOrder || 'medium'
          return priorityOrder[aPri] - priorityOrder[bPri]
        })
        break
      case 'unanswered':
        filtered.sort((a, b) => (a.answered === b.answered ? 0 : a.answered ? 1 : -1))
        break
      case 'quality':
        filtered.sort((a, b) => (b.quality_score || 0) - (a.quality_score || 0))
        break
      // default: keep original order
    }

    return filtered
  }

  const filteredGaps = getFilteredAndSortedGaps()
  const totalAnswered = gaps.filter(g => g.answered).length
  const totalPending = gaps.filter(g => !g.answered).length

  // Get categories and priorities for filters
  const categories = gaps.reduce((acc, g) => {
    if (g.category) acc[g.category] = (acc[g.category] || 0) + 1
    return acc
  }, {} as { [key: string]: number })

  const priorities = gaps.reduce((acc, g) => {
    if (g.priority) acc[g.priority] = (acc[g.priority] || 0) + 1
    return acc
  }, {} as { [key: string]: number })

  return (
    <div className="flex h-screen bg-primary overflow-hidden">
      <Sidebar activeItem={activeItem} onItemClick={setActiveItem} />

      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <div className="p-8 bg-primary border-b border-gray-200">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-semibold" style={{ fontFamily: '"Work Sans", sans-serif', color: '#081028' }}>
              Knowledge Gaps
            </h1>

            <div className="flex items-center gap-3">
              {gaps.length > 0 && (
                <button
                  onClick={handleGenerateTrainingVideo}
                  disabled={generatingVideo}
                  className="px-4 py-2 rounded-lg font-medium text-sm transition-colors"
                  style={{
                    backgroundColor: '#F97316',
                    color: 'white',
                    fontFamily: '"Work Sans", sans-serif',
                    cursor: generatingVideo ? 'wait' : 'pointer'
                  }}
                >
                  📹 Generate Training Video
                </button>
              )}

              <button
                onClick={generateQuestions}
                disabled={generating}
                className="px-4 py-2 rounded-lg font-medium text-sm transition-colors"
                style={{
                  backgroundColor: '#081028',
                  color: 'white',
                  fontFamily: '"Work Sans", sans-serif',
                  cursor: generating ? 'wait' : 'pointer'
                }}
              >
                {generating ? 'Analyzing...' : '🔍 Find Gaps'}
              </button>
            </div>
          </div>

          {/* Analysis Mode Selector */}
          <AnalysisModeSelector
            selectedMode={analysisMode}
            onModeChange={setAnalysisMode}
            isAnalyzing={generating}
          />

          {/* Stats */}
          {gaps.length > 0 && (
            <div className="mt-6">
              <GapStats
                total={gaps.length}
                answered={totalAnswered}
                pending={totalPending}
              />
            </div>
          )}

          {/* Filter Tabs */}
          {gaps.length > 0 && (
            <div className="flex gap-2 mt-4">
              {(['all', 'unanswered', 'answered'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className="px-4 py-2 rounded-lg font-medium text-sm transition-colors"
                  style={{
                    backgroundColor: filter === f ? '#081028' : 'transparent',
                    color: filter === f ? 'white' : '#7E89AC',
                    fontFamily: '"Work Sans", sans-serif'
                  }}
                >
                  {f === 'all' ? `All (${gaps.length})` :
                   f === 'unanswered' ? `Pending (${totalPending})` :
                   `Done (${totalAnswered})`}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden bg-secondary">
          {/* Questions List */}
          <div className={`${selectedGap ? 'w-1/2' : 'flex-1'} overflow-y-auto p-8`}>
            {loading ? (
              <div className="flex items-center justify-center h-64 text-gray-500">
                Loading gaps...
              </div>
            ) : gaps.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <p className="text-gray-600 mb-4">No knowledge gaps found yet</p>
                <button
                  onClick={generateQuestions}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
                >
                  🔍 Analyze Documents for Gaps
                </button>
              </div>
            ) : (
              <>
                {/* Filters */}
                <GapFilters
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                  selectedCategory={selectedCategory}
                  onCategoryChange={setSelectedCategory}
                  selectedPriority={selectedPriority}
                  onPriorityChange={setSelectedPriority}
                  sortBy={sortBy}
                  onSortChange={setSortBy}
                  categories={categories}
                  priorities={priorities}
                />

                {/* Gap Cards */}
                {filteredGaps.length === 0 ? (
                  <div className="text-center text-gray-500 py-12">
                    No gaps match your filters
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredGaps.map((gap, index) => (
                      <GapCard
                        key={gap.id}
                        gap={gap}
                        index={index}
                        isSelected={selectedGap?.id === gap.id}
                        onClick={() => setSelectedGap(gap)}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Answer Panel */}
          {selectedGap && (
            <GapAnswerPanel
              gap={selectedGap}
              answer={answer}
              onAnswerChange={setAnswer}
              onSubmit={handleAnswerQuestion}
              isSubmitting={submitting}
              onClose={() => setSelectedGap(null)}
              onFeedback={handleGapFeedback}
              authHeaders={authHeaders}
            />
          )}
        </div>
      </div>

      {/* Video Generation Modal */}
      {showVideoModal && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onClick={() => !generatingVideo && setShowVideoModal(false)}
        >
          <div
            className="bg-white rounded-xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-xl font-semibold mb-4" style={{ fontFamily: '"Work Sans", sans-serif' }}>
              Generate Training Video
            </h3>

            {!generatingVideo ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Video Title</label>
                  <input
                    type="text"
                    value={videoTitle}
                    onChange={(e) => setVideoTitle(e.target.value)}
                    placeholder="e.g., Q&A Training Session"
                    className="w-full px-3 py-2 border rounded-lg outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Description (Optional)</label>
                  <textarea
                    value={videoDescription}
                    onChange={(e) => setVideoDescription(e.target.value)}
                    placeholder="Brief description of the video content..."
                    className="w-full px-3 py-2 border rounded-lg outline-none focus:border-blue-500 resize-none"
                    rows={3}
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="include-answers"
                    checked={includeAnswers}
                    onChange={(e) => setIncludeAnswers(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <label htmlFor="include-answers" className="text-sm">
                    Include answered gaps (shows Q&A format)
                  </label>
                </div>

                <div className="flex gap-2 pt-4">
                  <button
                    onClick={createTrainingVideo}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    Create Video
                  </button>
                  <button
                    onClick={() => setShowVideoModal(false)}
                    className="px-4 py-2 border rounded-lg hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="text-center py-8">
                  <div className="text-4xl mb-4">🎬</div>
                  <p className="text-lg font-medium mb-2">Generating Video...</p>
                  <p className="text-sm text-gray-600 mb-4">
                    {videoProgress?.current_step || 'Processing...'}
                  </p>

                  <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-400 to-blue-600 transition-all duration-300"
                      style={{ width: `${videoProgress?.progress_percent || 0}%` }}
                    />
                  </div>

                  <p className="text-xs text-gray-500 mt-2">
                    {videoProgress?.progress_percent || 0}% complete
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
