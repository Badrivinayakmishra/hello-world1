import React from 'react'

interface AnalysisMode {
  id: string
  name: string
  description: string
  time: string
  quality: string
  recommended?: boolean
}

const modes: AnalysisMode[] = [
  {
    id: 'simple',
    name: 'Quick',
    description: 'Fast single-pass analysis for basic gaps',
    time: '~2 min',
    quality: 'Basic'
  },
  {
    id: 'intelligent',
    name: 'Standard',
    description: 'NLP-powered analysis with frame detection',
    time: '~5 min',
    quality: 'High',
    recommended: true
  },
  {
    id: 'v3',
    name: 'Advanced',
    description: '6-stage GPT-4 analysis with knowledge graph',
    time: '~10 min',
    quality: 'Excellent'
  }
]

interface AnalysisModeSelectorProps {
  selectedMode: string
  onModeChange: (mode: string) => void
  isAnalyzing: boolean
}

export default function AnalysisModeSelector({
  selectedMode,
  onModeChange,
  isAnalyzing
}: AnalysisModeSelectorProps) {
  const [showInfo, setShowInfo] = React.useState(false)

  return (
    <div className="relative">
      {/* Mode Selector */}
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700" style={{ fontFamily: '"Work Sans", sans-serif' }}>
          Analysis Mode:
        </label>
        <select
          value={selectedMode}
          onChange={(e) => onModeChange(e.target.value)}
          disabled={isAnalyzing}
          className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm outline-none focus:border-gray-500 bg-white disabled:bg-gray-100"
          style={{
            fontFamily: '"Work Sans", sans-serif',
            color: '#081028'
          }}
        >
          {modes.map((mode) => (
            <option key={mode.id} value={mode.id}>
              {mode.name} {mode.recommended ? '(Recommended)' : ''} - {mode.time}
            </option>
          ))}
        </select>

        {/* Info Button */}
        <button
          onClick={() => setShowInfo(!showInfo)}
          className="w-5 h-5 rounded-full bg-gray-200 hover:bg-gray-300 flex items-center justify-center text-xs text-gray-600"
        >
          ?
        </button>
      </div>

      {/* Info Popup */}
      {showInfo && (
        <div
          className="absolute top-full mt-2 left-0 z-10 bg-white border border-gray-300 rounded-lg shadow-lg p-4 w-96"
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-sm" style={{ fontFamily: '"Work Sans", sans-serif', color: '#081028' }}>
              Analysis Modes Explained
            </h3>
            <button
              onClick={() => setShowInfo(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          <div className="space-y-3">
            {modes.map((mode) => (
              <div
                key={mode.id}
                className={`p-2 rounded ${selectedMode === mode.id ? 'bg-blue-50 border border-blue-200' : 'bg-gray-50'}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-xs" style={{ color: '#081028' }}>
                    {mode.name} {mode.recommended && <span className="text-blue-600">★</span>}
                  </span>
                  <span className="text-xs text-gray-500">{mode.time}</span>
                </div>
                <p className="text-xs text-gray-600 mb-1">{mode.description}</p>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-gray-500">Quality:</span>
                  <span className={`font-medium ${
                    mode.quality === 'Excellent' ? 'text-green-600' :
                    mode.quality === 'High' ? 'text-blue-600' :
                    'text-gray-600'
                  }`}>
                    {mode.quality}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
            <strong>💡 Tip:</strong> Standard mode offers the best balance of speed and quality for most use cases.
          </div>
        </div>
      )}
    </div>
  )
}
