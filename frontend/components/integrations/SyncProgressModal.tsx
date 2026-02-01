'use client'

import React, { useState, useEffect } from 'react'

interface SyncProgressModalProps {
  syncId: string
  connectorType: string
  onClose: () => void
}

interface ProgressData {
  sync_id: string
  connector_type: string
  status: 'connecting' | 'syncing' | 'parsing' | 'embedding' | 'complete' | 'error'
  stage: string
  total_items: number
  processed_items: number
  failed_items: number
  current_item?: string
  error_message?: string
  percent_complete: number
}

export default function SyncProgressModal({
  syncId,
  connectorType,
  onClose
}: SyncProgressModalProps) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [eventSource, setEventSource] = useState<EventSource | null>(null)

  useEffect(() => {
    // Connect to SSE stream
    const es = new EventSource(
      `http://localhost:5003/api/sync-progress/${syncId}/stream`,
      { withCredentials: true }
    )

    es.addEventListener('current_state', (event: MessageEvent) => {
      const data = JSON.parse(event.data)
      setProgress(data)
    })

    es.addEventListener('started', (event: MessageEvent) => {
      const data = JSON.parse(event.data)
      setProgress(data)
    })

    es.addEventListener('progress', (event: MessageEvent) => {
      const data = JSON.parse(event.data)
      setProgress(data)
    })

    es.addEventListener('complete', (event: MessageEvent) => {
      const data = JSON.parse(event.data)
      setProgress(data)
      // Auto-close after 3 seconds
      setTimeout(() => {
        es.close()
        onClose()
      }, 3000)
    })

    es.addEventListener('error', (event: MessageEvent) => {
      const data = JSON.parse(event.data)
      setProgress(data)
    })

    es.onerror = () => {
      console.error('SSE connection error')
    }

    setEventSource(es)

    return () => {
      es.close()
    }
  }, [syncId, onClose])

  if (!progress) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 max-w-md w-full">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        </div>
      </div>
    )
  }

  const getStatusIcon = () => {
    if (progress.status === 'complete') {
      return (
        <svg className="h-12 w-12 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
    } else if (progress.status === 'error') {
      return (
        <svg className="h-12 w-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
    } else {
      return (
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      )
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">
            Syncing {connectorType.charAt(0).toUpperCase() + connectorType.slice(1)}
          </h2>
          {progress.status === 'complete' || progress.status === 'error' ? (
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          ) : null}
        </div>

        {/* Status Icon */}
        <div className="flex justify-center mb-4">
          {getStatusIcon()}
        </div>

        {/* Stage */}
        <div className="text-center mb-4">
          <p className="text-lg font-medium text-gray-900">{progress.stage}</p>
          {progress.current_item && (
            <p className="text-sm text-gray-500 mt-1 truncate">{progress.current_item}</p>
          )}
        </div>

        {/* Progress Bar */}
        {progress.total_items > 0 && (
          <div className="mb-4">
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${progress.percent_complete}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-sm text-gray-600 mt-2">
              <span>{progress.processed_items} / {progress.total_items}</span>
              <span>{Math.round(progress.percent_complete)}%</span>
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">{progress.total_items}</div>
            <div className="text-xs text-gray-500">Found</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{progress.processed_items}</div>
            <div className="text-xs text-gray-500">Processed</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">{progress.failed_items}</div>
            <div className="text-xs text-gray-500">Failed</div>
          </div>
        </div>

        {/* Error Message */}
        {progress.error_message && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-800">{progress.error_message}</p>
          </div>
        )}

        {/* Success Message */}
        {progress.status === 'complete' && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-sm text-green-800">
              Sync completed successfully! {progress.processed_items} items processed.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
