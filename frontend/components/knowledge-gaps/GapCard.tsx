import React from 'react'

interface GapCardProps {
  gap: {
    id: string
    description: string
    project: string
    answered?: boolean
    answer?: string
    category?: string
    priority?: string
    quality_score?: number
    evidence?: string
    detection_method?: string
  }
  index: number
  isSelected: boolean
  onClick: () => void
}

const getCategoryColor = (category?: string) => {
  switch (category?.toLowerCase()) {
    case 'decision':
      return { bg: '#DBEAFE', text: '#1E40AF' }
    case 'technical':
      return { bg: '#F3E8FF', text: '#6B21A8' }
    case 'process':
      return { bg: '#FEF3C7', text: '#92400E' }
    case 'context':
      return { bg: '#D1FAE5', text: '#065F46' }
    default:
      return { bg: '#F3F4F6', text: '#4B5563' }
  }
}

const getPriorityColor = (priority?: string) => {
  switch (priority?.toLowerCase()) {
    case 'high':
      return { bg: '#FEE2E2', text: '#991B1B', icon: '🔴' }
    case 'medium':
      return { bg: '#FEF3C7', text: '#92400E', icon: '🟡' }
    case 'low':
      return { bg: '#E0E7FF', text: '#3730A3', icon: '🟢' }
    default:
      return { bg: '#F3F4F6', text: '#6B7280', icon: '⚪' }
  }
}

export default function GapCard({ gap, index, isSelected, onClick }: GapCardProps) {
  const categoryColor = getCategoryColor(gap.category)
  const priorityColor = getPriorityColor(gap.priority)

  return (
    <div
      onClick={onClick}
      className="cursor-pointer transition-all"
      style={{
        padding: '16px 20px',
        borderRadius: '8px',
        backgroundColor: isSelected ? '#FFE2BF' : 'white',
        border: isSelected ? '2px solid #081028' : '1px solid rgba(8, 16, 40, 0.06)'
      }}
    >
      <div className="flex items-start gap-3">
        {/* Number/Checkmark */}
        <span
          className="font-work font-semibold min-w-[24px]"
          style={{
            color: gap.answered ? '#10B981' : '#7E89AC',
            fontSize: '13px'
          }}
        >
          {gap.answered ? '✓' : `${index + 1}.`}
        </span>

        {/* Content */}
        <div className="flex-1">
          {/* Question */}
          <p
            className="font-work mb-2"
            style={{
              color: '#081028',
              fontSize: '14px',
              lineHeight: '1.5',
              fontWeight: gap.answered ? 400 : 500
            }}
          >
            {gap.description}
          </p>

          {/* Metadata Row */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Category Badge */}
            {gap.category && (
              <span
                className="px-2 py-0.5 rounded text-xs font-medium"
                style={{
                  backgroundColor: categoryColor.bg,
                  color: categoryColor.text
                }}
              >
                {gap.category}
              </span>
            )}

            {/* Priority Badge */}
            {gap.priority && (
              <span
                className="px-2 py-0.5 rounded text-xs font-medium flex items-center gap-1"
                style={{
                  backgroundColor: priorityColor.bg,
                  color: priorityColor.text
                }}
              >
                <span>{priorityColor.icon}</span>
                {gap.priority}
              </span>
            )}

            {/* Quality Score */}
            {gap.quality_score !== undefined && gap.quality_score > 0 && (
              <span className="text-xs text-gray-500 flex items-center gap-1">
                ⭐ {Math.round(gap.quality_score * 100)}%
              </span>
            )}

            {/* Project */}
            <span className="text-xs text-gray-500">
              📁 {gap.project}
            </span>
          </div>

          {/* Evidence Snippet */}
          {gap.evidence && !gap.answered && (
            <div className="mt-2 p-2 bg-gray-50 rounded text-xs text-gray-600 italic border-l-2 border-gray-300">
              💡 {gap.evidence}
            </div>
          )}

          {/* Detection Method (subtle) */}
          {gap.detection_method && !gap.answered && (
            <div className="mt-1 text-xs text-gray-400">
              🔍 {gap.detection_method}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
