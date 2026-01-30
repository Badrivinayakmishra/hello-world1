import React from 'react'

interface GapStatsProps {
  total: number
  answered: number
  pending: number
}

export default function GapStats({ total, answered, pending }: GapStatsProps) {
  const percentComplete = total > 0 ? Math.round((answered / total) * 100) : 0

  return (
    <div className="mb-6">
      {/* Progress Bar */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700" style={{ fontFamily: '"Work Sans", sans-serif' }}>
          Knowledge Transfer Progress
        </span>
        <span className="text-sm font-semibold" style={{ fontFamily: '"Work Sans", sans-serif', color: '#10B981' }}>
          {percentComplete}% Complete
        </span>
      </div>

      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden mb-4">
        <div
          className="h-full bg-gradient-to-r from-green-400 to-green-600 transition-all duration-500 rounded-full"
          style={{ width: `${percentComplete}%` }}
        />
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold mb-1" style={{ fontFamily: '"Work Sans", sans-serif', color: '#081028' }}>
            {total}
          </div>
          <div className="text-xs text-gray-500" style={{ fontFamily: '"Work Sans", sans-serif' }}>
            Total Gaps
          </div>
        </div>

        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold mb-1" style={{ fontFamily: '"Work Sans", sans-serif', color: '#10B981' }}>
            {answered}
          </div>
          <div className="text-xs text-gray-600" style={{ fontFamily: '"Work Sans", sans-serif' }}>
            Completed
          </div>
        </div>

        <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold mb-1" style={{ fontFamily: '"Work Sans", sans-serif', color: '#F59E0B' }}>
            {pending}
          </div>
          <div className="text-xs text-gray-600" style={{ fontFamily: '"Work Sans", sans-serif' }}>
            Pending
          </div>
        </div>
      </div>
    </div>
  )
}
