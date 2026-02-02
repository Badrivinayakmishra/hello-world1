'use client'

import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'

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
  started_at?: string
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : 'http://localhost:5003/api'

export default function SyncProgressModal({
  syncId,
  connectorType,
  onClose
}: SyncProgressModalProps) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [emailNotify, setEmailNotify] = useState(false)
  const [estimatedTime, setEstimatedTime] = useState<string>('Calculating...')
  const [elapsedTime, setElapsedTime] = useState<number>(0)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const startTimeRef = useRef<number>(Date.now())
  const eventSourceRef = useRef<EventSource | null>(null)
  const progressHistoryRef = useRef<Array<{ time: number; percent: number }>>([])
  const connectionTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Calculate estimated time remaining
  useEffect(() => {
    if (!progress || progress.status === 'complete' || progress.status === 'error') {
      setEstimatedTime('')
      return
    }

    const now = Date.now()
    const elapsed = (now - startTimeRef.current) / 1000 // seconds
    setElapsedTime(elapsed)

    // Calculate actual progress percentage (backend might send 0)
    const actualPercent = progress.total_items > 0
      ? (progress.processed_items / progress.total_items) * 100
      : progress.percent_complete

    const remaining = progress.total_items - progress.processed_items

    // Track progress history for better estimation
    if (actualPercent > 0 || progress.processed_items > 0) {
      progressHistoryRef.current.push({
        time: now,
        percent: actualPercent
      })

      // Keep last 10 data points
      if (progressHistoryRef.current.length > 10) {
        progressHistoryRef.current.shift()
      }

      // Try to calculate based on actual progress rate
      if (progressHistoryRef.current.length >= 2 && elapsed > 3) {
        const first = progressHistoryRef.current[0]
        const last = progressHistoryRef.current[progressHistoryRef.current.length - 1]

        const percentChange = last.percent - first.percent
        const timeChange = (last.time - first.time) / 1000 // seconds

        if (percentChange > 5 && timeChange > 0) {
          const percentPerSecond = percentChange / timeChange
          const remainingPercent = 100 - actualPercent
          const estimatedSeconds = remainingPercent / percentPerSecond

          // Format time
          if (estimatedSeconds < 60) {
            setEstimatedTime(`Est: ~${Math.ceil(estimatedSeconds)}s`)
          } else if (estimatedSeconds < 3600) {
            const mins = Math.ceil(estimatedSeconds / 60)
            setEstimatedTime(`Est: ~${mins} min`)
          } else {
            const hours = Math.floor(estimatedSeconds / 3600)
            const mins = Math.ceil((estimatedSeconds % 3600) / 60)
            setEstimatedTime(`Est: ~${hours}h ${mins}m`)
          }
          return
        }
      }
    }

    // Fallback: Estimate based on status and items remaining
    let estimatedSeconds = 30 // default guess

    if (progress.status === 'connecting') {
      estimatedSeconds = 10
    } else if (progress.status === 'syncing') {
      // Syncing: ~5-10 seconds per 10 items
      estimatedSeconds = Math.max(20, remaining * 0.5)
    } else if (progress.status === 'parsing') {
      // Parsing: ~2 seconds per document
      estimatedSeconds = Math.max(10, remaining * 2)
    } else if (progress.status === 'embedding') {
      // Embedding: ~3 seconds per document
      estimatedSeconds = Math.max(15, remaining * 3)
    }

    // Format fallback estimate
    if (estimatedSeconds < 60) {
      setEstimatedTime(`Est: ~${Math.ceil(estimatedSeconds)}s`)
    } else if (estimatedSeconds < 3600) {
      const mins = Math.ceil(estimatedSeconds / 60)
      setEstimatedTime(`Est: ~${mins} min`)
    } else {
      const hours = Math.floor(estimatedSeconds / 3600)
      const mins = Math.ceil((estimatedSeconds % 3600) / 60)
      setEstimatedTime(`Est: ~${hours}h ${mins}m`)
    }
  }, [progress])

  // Connect to SSE stream
  useEffect(() => {
    const token = localStorage.getItem('authToken')
    if (!token) {
      console.error('[SyncProgress] No auth token found')
      setConnectionError('Authentication required. Please log in again.')
      return
    }

    console.log('[SyncProgress] Connecting to SSE stream for sync:', syncId)

    // EventSource cannot send custom headers, so pass token as query param
    const streamUrl = `${API_BASE}/sync-progress/${syncId}/stream?token=${encodeURIComponent(token)}`
    console.log('[SyncProgress] Stream URL:', streamUrl.replace(/token=[^&]+/, 'token=***'))

    const es = new EventSource(streamUrl, { withCredentials: true })

    let hasReceivedAnyEvent = false

    // Set connection timeout - only if NO events received (even "connected")
    connectionTimeoutRef.current = setTimeout(() => {
      if (!hasReceivedAnyEvent) {
        console.error('[SyncProgress] Connection timeout - no events received')
        setConnectionError('Connection timeout. Check backend deployment.')
        es.close()
      }
    }, 30000) // 30 seconds instead of 10

    // Clear timeout when any event is received
    const clearConnectionTimeout = () => {
      hasReceivedAnyEvent = true
      if (connectionTimeoutRef.current) {
        clearTimeout(connectionTimeoutRef.current)
        connectionTimeoutRef.current = null
      }
    }

    es.addEventListener('connected', (event: MessageEvent) => {
      clearConnectionTimeout()
      console.log('[SyncProgress] Connected to SSE stream')
      setConnectionError(null)
    })

    es.addEventListener('current_state', (event: MessageEvent) => {
      clearConnectionTimeout()
      console.log('[SyncProgress] Current state:', event.data)
      const data = JSON.parse(event.data)
      setProgress(data)
      setConnectionError(null)
    })

    es.addEventListener('started', (event: MessageEvent) => {
      clearConnectionTimeout()
      console.log('[SyncProgress] Started:', event.data)
      const data = JSON.parse(event.data)
      setProgress(data)
      setConnectionError(null)
    })

    es.addEventListener('progress', (event: MessageEvent) => {
      clearConnectionTimeout()
      console.log('[SyncProgress] Progress update:', event.data)
      const data = JSON.parse(event.data)
      setProgress(data)
    })

    // Log ALL messages for debugging
    es.onmessage = (event: MessageEvent) => {
      console.log('[SyncProgress] Received message:', event)
    }

    es.addEventListener('complete', (event: MessageEvent) => {
      clearConnectionTimeout()
      console.log('[SyncProgress] Complete:', event.data)
      const data = JSON.parse(event.data)
      setProgress(data)

      // Send email notification if enabled
      if (emailNotify) {
        sendEmailNotification()
      }

      // Auto-close after 5 seconds
      setTimeout(() => {
        es.close()
        onClose()
      }, 5000)
    })

    es.addEventListener('error', (event: MessageEvent) => {
      try {
        if (event.data) {
          const data = JSON.parse(event.data)
          setProgress(data)
        }
      } catch (e) {
        console.error('Failed to parse error event:', e)
      }
    })

    es.onerror = (error) => {
      console.error('SSE connection error:', error)

      // EventSource automatically reconnects on transient errors
      // Only show error if connection is actually closed (readyState === 2)
      if (es.readyState === EventSource.CLOSED) {
        console.error('[SyncProgress] Connection closed permanently')
        setConnectionError('Connection lost. Please refresh and try again.')
      } else {
        console.log('[SyncProgress] Connection error, will auto-reconnect...')
      }
    }

    eventSourceRef.current = es

    return () => {
      console.log('[SyncProgress] Cleaning up SSE connection')
      if (connectionTimeoutRef.current) {
        clearTimeout(connectionTimeoutRef.current)
      }
      es.close()
    }
  }, [syncId]) // Only reconnect if syncId changes (which it shouldn't)

  const sendEmailNotification = async () => {
    try {
      const token = localStorage.getItem('authToken')
      await axios.post(
        `${API_BASE}/sync-progress/${syncId}/notify`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      )
    } catch (error) {
      console.error('Failed to send email notification:', error)
    }
  }

  const getStatusIcon = () => {
    if (!progress) return null

    switch (progress.status) {
      case 'complete':
        return (
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: '#D1FAE5',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <svg width="32" height="32" fill="none" viewBox="0 0 24 24">
              <path
                stroke="#10B981"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        )
      case 'error':
        return (
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: '#FEE2E2',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <svg width="32" height="32" fill="none" viewBox="0 0 24 24">
              <path
                stroke="#DC2626"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </div>
        )
      default:
        return (
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: '#DBEAFE',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            animation: 'spin 2s linear infinite'
          }}>
            <style>{`
              @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
              }
            `}</style>
            <svg width="32" height="32" fill="none" viewBox="0 0 24 24">
              <circle
                cx="12"
                cy="12"
                r="10"
                stroke="#3B82F6"
                strokeWidth="3"
                strokeDasharray="60"
                strokeLinecap="round"
              />
            </svg>
          </div>
        )
    }
  }

  const getStatusText = () => {
    if (!progress) return 'Connecting...'

    // Use backend's stage message if available (it's more detailed)
    if (progress.stage && progress.status !== 'complete' && progress.status !== 'error') {
      return progress.stage
    }

    // Fallback to status-based messages
    switch (progress.status) {
      case 'connecting':
        return 'Connecting to service...'
      case 'syncing':
        return 'Fetching documents...'
      case 'parsing':
        return 'Parsing documents...'
      case 'embedding':
        return 'Creating embeddings and indexing...'
      case 'complete':
        return 'Sync completed successfully!'
      case 'error':
        return 'Sync failed'
      default:
        return 'Processing...'
    }
  }

  if (!progress) {
    return (
      <div style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999
      }}>
        <div style={{
          backgroundColor: 'white',
          borderRadius: '12px',
          padding: '32px',
          maxWidth: '500px',
          width: '90%',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              width: '48px',
              height: '48px',
              margin: '0 auto',
              border: '4px solid #E5E7EB',
              borderTopColor: '#3B82F6',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite'
            }}></div>
            <p style={{
              marginTop: '16px',
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '14px',
              color: '#6B7280'
            }}>
              Connecting to sync service...
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Calculate progress percentage - use backend value or calculate from items
  const progressPercent = Math.min(
    progress.percent_complete > 0
      ? progress.percent_complete
      : progress.total_items > 0
        ? (progress.processed_items / progress.total_items) * 100
        : 0,
    100
  )

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: 'white',
        borderRadius: '12px',
        padding: '32px',
        maxWidth: '500px',
        width: '100%',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <h2 style={{
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '20px',
            fontWeight: 600,
            color: '#081028',
            margin: 0
          }}>
            Syncing {connectorType.charAt(0).toUpperCase() + connectorType.slice(1)}
          </h2>
          {(progress.status === 'complete' || progress.status === 'error' || connectionError) && (
            <button
              onClick={onClose}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '4px',
                color: '#9CA3AF'
              }}
            >
              <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
                <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Connection Error Banner */}
        {connectionError && (
          <div style={{
            marginBottom: '24px',
            padding: '16px',
            backgroundColor: '#FEF2F2',
            border: '1px solid #FCA5A5',
            borderRadius: '8px'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px'
            }}>
              <svg width="20" height="20" fill="none" viewBox="0 0 24 24" style={{ flexShrink: 0, marginTop: '2px' }}>
                <path fill="#DC2626" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
              </svg>
              <div>
                <p style={{
                  fontFamily: '"Work Sans", sans-serif',
                  fontSize: '14px',
                  fontWeight: 600,
                  color: '#DC2626',
                  margin: '0 0 4px 0'
                }}>
                  Connection Error
                </p>
                <p style={{
                  fontFamily: '"Work Sans", sans-serif',
                  fontSize: '13px',
                  color: '#991B1B',
                  margin: 0,
                  lineHeight: '1.5'
                }}>
                  {connectionError}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Status Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '24px' }}>
          {getStatusIcon()}
        </div>

        {/* Status Text */}
        <div style={{ textAlign: 'center', marginBottom: '8px' }}>
          <p style={{
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '16px',
            fontWeight: 600,
            color: '#081028',
            margin: 0
          }}>
            {getStatusText()}
          </p>
        </div>

        {/* Current Item */}
        {progress.current_item && progress.status !== 'complete' && progress.status !== 'error' && (
          <div style={{ textAlign: 'center', marginBottom: '20px' }}>
            <p style={{
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '13px',
              color: '#6B7280',
              margin: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              padding: '0 20px'
            }}>
              {progress.current_item}
            </p>
          </div>
        )}

        {/* Estimated Time */}
        {progress.status !== 'complete' && progress.status !== 'error' && estimatedTime && (
          <div style={{
            textAlign: 'right',
            marginBottom: '12px',
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '12px',
            color: '#6B7280'
          }}>
            <span>{estimatedTime}</span>
          </div>
        )}

        {/* Progress Bar */}
        {progress.total_items > 0 && (
          <div style={{ marginBottom: '24px' }}>
            <div style={{
              width: '100%',
              height: '8px',
              backgroundColor: '#E5E7EB',
              borderRadius: '999px',
              overflow: 'hidden'
            }}>
              <div style={{
                width: `${progressPercent}%`,
                height: '100%',
                backgroundColor: progress.status === 'error' ? '#DC2626' : progress.status === 'complete' ? '#10B981' : '#3B82F6',
                transition: 'width 0.3s ease-out',
                borderRadius: '999px'
              }}></div>
            </div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginTop: '8px',
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '13px',
              color: '#6B7280'
            }}>
              <span>{progress.processed_items} / {progress.total_items} documents</span>
              <span style={{ fontWeight: 600 }}>{Math.round(progressPercent)}%</span>
            </div>
          </div>
        )}

        {/* Live Stats */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: '12px',
          marginBottom: '24px'
        }}>
          <div style={{
            padding: '16px',
            backgroundColor: '#F9FAFB',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <div style={{
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '24px',
              fontWeight: 700,
              color: '#3B82F6',
              marginBottom: '4px'
            }}>
              {progress.total_items}
            </div>
            <div style={{
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '11px',
              color: '#6B7280',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              Found
            </div>
          </div>

          <div style={{
            padding: '16px',
            backgroundColor: '#F0FDF4',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <div style={{
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '24px',
              fontWeight: 700,
              color: '#10B981',
              marginBottom: '4px'
            }}>
              {progress.processed_items}
            </div>
            <div style={{
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '11px',
              color: '#6B7280',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              Processed
            </div>
          </div>

          <div style={{
            padding: '16px',
            backgroundColor: progress.failed_items > 0 ? '#FEF2F2' : '#F9FAFB',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <div style={{
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '24px',
              fontWeight: 700,
              color: progress.failed_items > 0 ? '#DC2626' : '#6B7280',
              marginBottom: '4px'
            }}>
              {progress.failed_items}
            </div>
            <div style={{
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '11px',
              color: '#6B7280',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              Failed
            </div>
          </div>
        </div>

        {/* Email Notification Toggle */}
        {progress.status !== 'complete' && progress.status !== 'error' && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 16px',
            backgroundColor: '#F9FAFB',
            borderRadius: '8px',
            marginBottom: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
                <path
                  stroke="#6B7280"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                />
              </svg>
              <span style={{
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '13px',
                color: '#081028',
                fontWeight: 500
              }}>
                Email me when complete
              </span>
            </div>
            <button
              onClick={() => setEmailNotify(!emailNotify)}
              style={{
                width: '44px',
                height: '24px',
                borderRadius: '999px',
                backgroundColor: emailNotify ? '#3B82F6' : '#E5E7EB',
                border: 'none',
                cursor: 'pointer',
                position: 'relative',
                transition: 'background-color 0.2s'
              }}
            >
              <div style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                backgroundColor: 'white',
                position: 'absolute',
                top: '2px',
                left: emailNotify ? '22px' : '2px',
                transition: 'left 0.2s',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
              }}></div>
            </button>
          </div>
        )}

        {/* Error Message */}
        {progress.error_message && (
          <div style={{
            padding: '16px',
            backgroundColor: '#FEF2F2',
            border: '1px solid #FCA5A5',
            borderRadius: '8px',
            marginBottom: '16px'
          }}>
            <p style={{
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '13px',
              color: '#DC2626',
              margin: 0
            }}>
              {progress.error_message}
            </p>
          </div>
        )}

        {/* Success Message */}
        {progress.status === 'complete' && (
          <div style={{
            padding: '16px',
            backgroundColor: '#F0FDF4',
            border: '1px solid #86EFAC',
            borderRadius: '8px'
          }}>
            <p style={{
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '13px',
              color: '#10B981',
              margin: 0,
              textAlign: 'center'
            }}>
              ✓ Successfully synced {progress.processed_items} {progress.processed_items === 1 ? 'document' : 'documents'}
              {emailNotify && ' • Email notification sent'}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
