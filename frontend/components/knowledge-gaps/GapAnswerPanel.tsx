import React from 'react'
import VoiceRecorder from './VoiceRecorder'

interface Gap {
  id: string
  description: string
  project: string
  answered?: boolean
  answer?: string
  category?: string
  priority?: string
  evidence?: string
  context?: string
  suggested_sources?: string[]
  detection_method?: string
}

interface GapAnswerPanelProps {
  gap: Gap
  answer: string
  onAnswerChange: (text: string) => void
  onSubmit: () => void
  isSubmitting: boolean
  onClose: () => void
  onFeedback?: (helpful: boolean) => void
  authHeaders: any
}

export default function GapAnswerPanel({
  gap,
  answer,
  onAnswerChange,
  onSubmit,
  isSubmitting,
  onClose,
  onFeedback,
  authHeaders
}: GapAnswerPanelProps) {
  return (
    <div
      className="flex-1 bg-white border-l border-gray-200 flex flex-col"
      style={{
        minWidth: '400px',
        maxWidth: '600px'
      }}
    >
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-start justify-between mb-2">
          <h3
            className="text-lg font-semibold pr-4"
            style={{ fontFamily: '"Work Sans", sans-serif', color: '#081028' }}
          >
            {gap.description}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 flex-shrink-0"
          >
            ✕
          </button>
        </div>

        {/* Metadata */}
        <div className="flex items-center gap-2 flex-wrap text-xs text-gray-500">
          <span>📁 {gap.project}</span>
          {gap.category && <span>• {gap.category}</span>}
          {gap.priority && <span>• Priority: {gap.priority}</span>}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {/* Why This Gap? */}
        {gap.evidence && (
          <div className="bg-blue-50 border-l-4 border-blue-400 p-4 rounded">
            <h4 className="text-sm font-semibold mb-2" style={{ color: '#1E40AF' }}>
              💡 Why This Gap?
            </h4>
            <p className="text-sm text-gray-700 leading-relaxed">
              {gap.evidence}
            </p>
          </div>
        )}

        {/* Additional Context */}
        {gap.context && (
          <div className="bg-gray-50 p-4 rounded border border-gray-200">
            <h4 className="text-sm font-semibold mb-2 text-gray-700">
              📖 Context
            </h4>
            <p className="text-sm text-gray-600 leading-relaxed">
              {gap.context}
            </p>
          </div>
        )}

        {/* Suggested Sources */}
        {gap.suggested_sources && gap.suggested_sources.length > 0 && (
          <div className="bg-green-50 p-4 rounded border border-green-200">
            <h4 className="text-sm font-semibold mb-2 text-green-800">
              📚 Review These Documents
            </h4>
            <ul className="text-sm text-gray-700 space-y-1">
              {gap.suggested_sources.map((source, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-green-600">•</span>
                  <span>{source}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Detection Method (for transparency) */}
        {gap.detection_method && (
          <div className="text-xs text-gray-400 italic">
            🔍 Detected via: {gap.detection_method}
          </div>
        )}

        {/* Answer Section */}
        {!gap.answered ? (
          <div className="space-y-4 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-semibold text-gray-700">
              Your Answer
            </h4>

            {/* Voice Recorder */}
            <VoiceRecorder
              onTranscriptionComplete={onAnswerChange}
              authHeaders={authHeaders}
            />

            {/* Text Input */}
            <textarea
              value={answer}
              onChange={(e) => onAnswerChange(e.target.value)}
              placeholder="Type your answer here, or use voice recording above..."
              className="w-full min-h-[120px] p-3 border border-gray-300 rounded-lg resize-vertical outline-none focus:border-blue-500 text-sm"
              style={{ fontFamily: '"Work Sans", sans-serif' }}
            />

            {/* Submit Button */}
            <button
              onClick={onSubmit}
              disabled={!answer.trim() || isSubmitting}
              className="w-full py-3 rounded-lg font-medium text-sm transition-colors"
              style={{
                backgroundColor: answer.trim() ? '#081028' : '#E5E7EB',
                color: answer.trim() ? 'white' : '#9CA3AF',
                cursor: answer.trim() ? 'pointer' : 'not-allowed',
                fontFamily: '"Work Sans", sans-serif'
              }}
            >
              {isSubmitting ? 'Saving Answer...' : 'Save Answer'}
            </button>
          </div>
        ) : (
          <div className="space-y-4 pt-4 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-green-700">
                ✓ Your Answer
              </h4>
              {onFeedback && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Was this helpful?</span>
                  <button
                    onClick={() => onFeedback(true)}
                    className="px-2 py-1 text-xs bg-green-100 hover:bg-green-200 rounded"
                  >
                    👍 Yes
                  </button>
                  <button
                    onClick={() => onFeedback(false)}
                    className="px-2 py-1 text-xs bg-red-100 hover:bg-red-200 rounded"
                  >
                    👎 No
                  </button>
                </div>
              )}
            </div>

            <div className="bg-green-50 p-4 rounded border border-green-200">
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                {gap.answer}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
