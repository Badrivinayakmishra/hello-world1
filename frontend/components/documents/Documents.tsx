'use client'

import React, { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import axios from 'axios'
import { useAuth, useAuthHeaders } from '@/contexts/AuthContext'
import { useRouter } from 'next/navigation'
import DocumentViewer from './DocumentViewer'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003') + '/api'

// Modern Design System
const colors = {
  // Primary
  primary: '#2563EB',
  primaryHover: '#1D4ED8',
  primaryLight: '#EFF6FF',

  // Backgrounds
  pageBg: '#F8FAFC',
  cardBg: '#FFFFFF',

  // Text
  textPrimary: '#111827',
  textSecondary: '#6B7280',
  textMuted: '#9CA3AF',

  // Borders & Dividers
  border: '#E5E7EB',
  borderLight: '#F3F4F6',

  // Status Colors
  statusGreen: '#22C55E',
  statusOrange: '#F59E0B',
  statusRed: '#EF4444',
  statusBlue: '#3B82F6',
  statusPurple: '#8B5CF6',
}

const shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
}

interface Document {
  id: string
  name: string
  created: string
  lastModified: string
  type: string
  description: string
  category: 'Meetings' | 'Documents' | 'Personal Items' | 'Other Items' | 'Web Scraper' | 'Code'
  selected: boolean
  classification?: string
  source_type?: string
  folder_path?: string
  content?: string
  url?: string
  summary?: string
  quickSummary?: string
  score?: number
  classificationConfidence?: number
}

interface FullDocument {
  id: string
  title: string
  content: string
  content_html?: string
  classification?: string
  source_type?: string
  sender?: string
  sender_email?: string
  recipients?: string[]
  source_created_at?: string
  summary?: string
  metadata?: any
}

// Status mapping for visual indicators
const getStatusInfo = (classification?: string, sourceType?: string) => {
  if (classification === 'work') return { label: 'Active', color: colors.statusGreen }
  if (classification === 'personal') return { label: 'Personal', color: colors.statusOrange }
  if (classification === 'spam') return { label: 'Archived', color: colors.statusRed }
  if (sourceType === 'webscraper') return { label: 'Scraped', color: colors.statusBlue }
  if (sourceType === 'github') return { label: 'Code', color: colors.statusPurple }
  return { label: 'Pending', color: colors.textMuted }
}

export default function Documents() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [filteredDocuments, setFilteredDocuments] = useState<Document[]>([])
  const [activeCategory, setActiveCategory] = useState<string>('All Items')
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [viewingDocument, setViewingDocument] = useState<FullDocument | null>(null)
  const [loadingDocument, setLoadingDocument] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [displayLimit, setDisplayLimit] = useState(50)
  const [sortField, setSortField] = useState<string>('created')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [activeFilters, setActiveFilters] = useState<string[]>([])
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set())

  const authHeaders = useAuthHeaders()
  const { token, user, logout } = useAuth()
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (token) {
      loadDocuments()
    }
  }, [token])

  useEffect(() => {
    filterDocuments()
  }, [documents, activeCategory, searchQuery, sortField, sortDirection])

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenuId(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const loadDocuments = async () => {
    try {
      const response = await axios.get(`${API_BASE}/documents?limit=100`, {
        headers: authHeaders
      })

      if (response.data.success) {
        const apiDocs = response.data.documents
        const docs: Document[] = apiDocs.map((doc: any, index: number) => {
          let category: Document['category'] = 'Other Items'
          const title = doc.title?.toLowerCase() || ''
          const sourceType = doc.source_type?.toLowerCase() || ''
          const classification = doc.classification?.toLowerCase() || ''
          const folderPath = doc.metadata?.folder_path?.toLowerCase() || ''

          // Categorization logic
          if (sourceType === 'webscraper' || sourceType?.includes('webscraper')) {
            category = 'Web Scraper'
          } else if (sourceType?.includes('code') || /\.(js|ts|py|jsx|tsx|java|cpp|go|rs)$/i.test(title)) {
            category = 'Code'
          } else if (classification === 'personal' || classification === 'spam') {
            category = 'Personal Items'
          } else if (classification === 'work') {
            if (/meeting|schedule|agenda|discussion/i.test(title)) {
              category = 'Meetings'
            } else {
              category = 'Documents'
            }
          } else if (sourceType === 'box' || sourceType === 'file') {
            category = 'Documents'
          }

          const createdDate = doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'Unknown'
          let displayName = doc.title || 'Untitled Document'
          if (sourceType === 'github' && displayName.includes(' - ')) {
            displayName = displayName.split(' - ').pop() || displayName
          }

          // Quick summary
          let quickSummary = ''
          if (sourceType === 'github') {
            quickSummary = 'GitHub Repository'
          } else if (doc.summary?.trim()) {
            quickSummary = doc.summary.split(' ').slice(0, 8).join(' ')
            if (doc.summary.split(' ').length > 8) quickSummary += '...'
          } else if (doc.content?.trim()) {
            const words = doc.content.trim().split(/\s+/).slice(0, 8).join(' ')
            quickSummary = words + '...'
          } else {
            quickSummary = `${sourceType || 'Document'} file`
          }

          // Document type
          let docType = 'Document'
          if (sourceType === 'github') docType = 'Code'
          else if (sourceType === 'webscraper') docType = 'Web Page'
          else if (sourceType === 'email') docType = 'Email'
          else if (sourceType === 'box') docType = 'Box File'

          // Calculate personal likelihood percentage from classification confidence
          // If classified as personal/spam, confidence is the personal %
          // If classified as work, personal % = 100 - confidence
          let personalPercent = 50 // Default for unknown
          if (doc.classification_confidence !== null && doc.classification_confidence !== undefined) {
            const confidence = doc.classification_confidence * 100
            if (classification === 'personal' || classification === 'spam') {
              personalPercent = Math.round(confidence)
            } else if (classification === 'work') {
              personalPercent = Math.round(100 - confidence)
            } else {
              personalPercent = 50 // Unknown classification
            }
          }

          return {
            id: doc.id || `doc_${index}`,
            name: displayName,
            created: createdDate,
            lastModified: doc.source_created_at ? new Date(doc.source_created_at).toLocaleDateString() : createdDate,
            type: docType,
            description: doc.summary || doc.title || 'No description',
            category,
            selected: false,
            classification: doc.classification,
            source_type: doc.source_type,
            url: doc.metadata?.url || doc.metadata?.source_url,
            content: doc.content,
            summary: doc.summary,
            quickSummary,
            score: personalPercent,
            classificationConfidence: doc.classification_confidence
          }
        })
        setDocuments(docs)
      }
    } catch (error) {
      console.error('Error loading documents:', error)
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  const filterDocuments = () => {
    let filtered = [...documents]

    if (activeCategory !== 'All Items') {
      filtered = filtered.filter(d => d.category === activeCategory)
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(d =>
        d.name.toLowerCase().includes(query) ||
        d.description.toLowerCase().includes(query) ||
        d.type.toLowerCase().includes(query)
      )
    }

    // Sort
    filtered.sort((a, b) => {
      let aVal = a[sortField as keyof Document] || ''
      let bVal = b[sortField as keyof Document] || ''
      if (sortDirection === 'asc') {
        return String(aVal).localeCompare(String(bVal))
      }
      return String(bVal).localeCompare(String(aVal))
    })

    setFilteredDocuments(filtered)
  }

  const viewDocument = async (documentId: string) => {
    setLoadingDocument(true)
    try {
      const response = await axios.get(`${API_BASE}/documents/${documentId}`, {
        headers: authHeaders
      })
      if (response.data.success) {
        setViewingDocument(response.data.document)
      }
    } catch (error) {
      console.error('Error loading document:', error)
    } finally {
      setLoadingDocument(false)
    }
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    try {
      const formData = new FormData()
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i])
      }
      const response = await axios.post(`${API_BASE}/documents/upload`, formData, {
        headers: { ...authHeaders, 'Content-Type': 'multipart/form-data' }
      })
      if (response.data.success) {
        loadDocuments()
      }
    } catch (error) {
      console.error('Error uploading files:', error)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDeleteDocument = async (documentId: string, documentName: string) => {
    if (!confirm(`Are you sure you want to delete "${documentName}"?`)) return

    try {
      const response = await axios.delete(`${API_BASE}/documents/${documentId}`, {
        headers: authHeaders
      })
      if (response.data.success) {
        loadDocuments()
      }
    } catch (error) {
      console.error('Error deleting document:', error)
    }
    setOpenMenuId(null)
  }

  const toggleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const removeFilter = (filter: string) => {
    setActiveFilters(prev => prev.filter(f => f !== filter))
  }

  const toggleDocSelection = (docId: string) => {
    setSelectedDocs(prev => {
      const newSet = new Set(prev)
      if (newSet.has(docId)) {
        newSet.delete(docId)
      } else {
        newSet.add(docId)
      }
      return newSet
    })
  }

  const toggleSelectAll = () => {
    if (selectedDocs.size === filteredDocuments.slice(0, displayLimit).length) {
      setSelectedDocs(new Set())
    } else {
      setSelectedDocs(new Set(filteredDocuments.slice(0, displayLimit).map(d => d.id)))
    }
  }

  const handleBulkDelete = async () => {
    if (selectedDocs.size === 0) return

    const count = selectedDocs.size
    if (!confirm(`Are you sure you want to delete ${count} document${count > 1 ? 's' : ''}?`)) return

    try {
      // Delete each selected document - convert Set to Array for iteration
      const docIds = Array.from(selectedDocs)
      for (let i = 0; i < docIds.length; i++) {
        await axios.delete(`${API_BASE}/documents/${docIds[i]}`, {
          headers: authHeaders
        })
      }
      setSelectedDocs(new Set())
      loadDocuments()
    } catch (error) {
      console.error('Error deleting documents:', error)
      alert('Failed to delete some documents')
    }
  }

  const handleMoveToCategory = async (docId: string, newCategory: string) => {
    // For now, this updates the local state. In production, you'd call an API to update the category.
    setDocuments(prev => prev.map(doc =>
      doc.id === docId ? { ...doc, category: newCategory as Document['category'] } : doc
    ))
    setOpenMenuId(null)
  }

  const handleBulkMoveToCategory = async (newCategory: string) => {
    if (selectedDocs.size === 0) return

    setDocuments(prev => prev.map(doc =>
      selectedDocs.has(doc.id) ? { ...doc, category: newCategory as Document['category'] } : doc
    ))
    setSelectedDocs(new Set())
  }

  const counts = {
    all: documents.length,
    meetings: documents.filter(d => d.category === 'Meetings').length,
    documents: documents.filter(d => d.category === 'Documents').length,
    personal: documents.filter(d => d.category === 'Personal Items').length,
    code: documents.filter(d => d.category === 'Code').length,
    other: documents.filter(d => d.category === 'Other Items').length,
    webscraper: documents.filter(d => d.category === 'Web Scraper').length
  }

  // Folder Card Component
  const FolderCard = ({ title, count, size, active, onClick }: {
    title: string
    count: number
    size: string
    active: boolean
    onClick: () => void
  }) => (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '16px 20px',
        backgroundColor: colors.cardBg,
        border: `1px solid ${active ? colors.primary : colors.border}`,
        borderRadius: '10px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        minWidth: '200px',
        boxShadow: active ? `0 0 0 1px ${colors.primary}` : shadows.sm,
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.borderColor = colors.textMuted
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.borderColor = colors.border
      }}
    >
      <div style={{
        width: '40px',
        height: '40px',
        backgroundColor: colors.borderLight,
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill={colors.textMuted}>
          <path d="M3 7V17C3 18.1046 3.89543 19 5 19H19C20.1046 19 21 18.1046 21 17V9C21 7.89543 20.1046 7 19 7H13L11 5H5C3.89543 5 3 5.89543 3 7Z"/>
        </svg>
      </div>
      <div style={{ textAlign: 'left' }}>
        <div style={{
          fontSize: '14px',
          fontWeight: 600,
          color: colors.textPrimary,
          marginBottom: '2px',
        }}>
          {title}
        </div>
        <div style={{
          fontSize: '12px',
          color: colors.textMuted,
        }}>
          {count} files | {size}
        </div>
      </div>
    </button>
  )

  // Filter Pill Component
  const FilterPill = ({ label, active, hasClose, onClick, onClose }: {
    label: string
    active?: boolean
    hasClose?: boolean
    onClick?: () => void
    onClose?: () => void
  }) => (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '8px 14px',
        backgroundColor: active ? colors.primaryLight : colors.cardBg,
        border: `1px solid ${active ? colors.primary : colors.border}`,
        borderRadius: '20px',
        cursor: 'pointer',
        fontSize: '13px',
        fontWeight: 500,
        color: active ? colors.primary : colors.textSecondary,
        transition: 'all 0.15s ease',
      }}
    >
      {label}
      {hasClose && (
        <span
          onClick={(e) => { e.stopPropagation(); onClose?.() }}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            backgroundColor: colors.primary,
            color: '#fff',
            fontSize: '10px',
            marginLeft: '2px',
          }}
        >
          ×
        </span>
      )}
    </button>
  )

  // Sort Icon Component
  const SortIcon = ({ field }: { field: string }) => (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      style={{
        marginLeft: '4px',
        opacity: sortField === field ? 1 : 0.3,
        transform: sortField === field && sortDirection === 'asc' ? 'rotate(180deg)' : 'none',
        transition: 'all 0.15s ease'
      }}
    >
      <path d="M6 8L2 4H10L6 8Z" fill={colors.textMuted}/>
    </svg>
  )

  // Progress Bar Component - shows personal likelihood %
  // Green = likely work (low %), Orange/Red = likely personal (high %)
  const ProgressBar = ({ value }: { value: number }) => {
    // Color gradient: green (0%) -> yellow (50%) -> orange (75%) -> red (100%)
    let barColor = colors.statusGreen
    if (value > 75) {
      barColor = colors.statusRed
    } else if (value > 50) {
      barColor = colors.statusOrange
    } else if (value > 25) {
      barColor = '#EAB308' // Yellow
    }

    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{
          flex: 1,
          height: '8px',
          backgroundColor: colors.borderLight,
          borderRadius: '4px',
          overflow: 'hidden',
        }}>
          <div style={{
            width: `${value}%`,
            height: '100%',
            backgroundColor: barColor,
            borderRadius: '4px',
            transition: 'width 0.3s ease',
          }} />
        </div>
        <span style={{ fontSize: '13px', color: colors.textPrimary, fontWeight: 500, minWidth: '35px' }}>
          {value}%
        </span>
      </div>
    )
  }

  // Status Indicator Component
  const StatusIndicator = ({ status, color }: { status: string; color: string }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        backgroundColor: color,
      }} />
      <span style={{ fontSize: '13px', color: color, fontWeight: 500 }}>
        {status}
      </span>
    </div>
  )

  // Action Menu Component - with Move to category options
  const ActionMenu = ({ docId, docName }: { docId: string; docName: string }) => {
    const categories = [
      { label: 'Documents', value: 'Documents' },
      { label: 'Code', value: 'Code' },
      { label: 'Meetings', value: 'Meetings' },
      { label: 'Web Scraper', value: 'Web Scraper' },
      { label: 'Personal Items', value: 'Personal Items' },
      { label: 'Other Items', value: 'Other Items' },
    ]

    return (
      <div style={{ position: 'relative' }} ref={openMenuId === docId ? menuRef : null}>
        <button
          onClick={(e) => {
            e.stopPropagation()
            setOpenMenuId(openMenuId === docId ? null : docId)
          }}
          style={{
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'transparent',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            transition: 'background-color 0.15s ease',
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.borderLight}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill={colors.textMuted}>
            <circle cx="8" cy="3" r="1.5"/>
            <circle cx="8" cy="8" r="1.5"/>
            <circle cx="8" cy="13" r="1.5"/>
          </svg>
        </button>

        {openMenuId === docId && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            backgroundColor: colors.cardBg,
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            boxShadow: shadows.lg,
            minWidth: '180px',
            zIndex: 100,
            overflow: 'hidden',
          }}>
            {/* View Options */}
            <button
              onClick={(e) => { e.stopPropagation(); viewDocument(docId); setOpenMenuId(null) }}
              style={{
                width: '100%',
                padding: '10px 14px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                backgroundColor: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontSize: '13px',
                color: colors.textPrimary,
                textAlign: 'left',
                transition: 'background-color 0.15s ease',
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.borderLight}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <span>📄</span> View Document
            </button>

            <div style={{ height: '1px', backgroundColor: colors.border, margin: '4px 0' }} />

            {/* Move to Section */}
            <div style={{ padding: '6px 14px', fontSize: '11px', fontWeight: 600, color: colors.textMuted, textTransform: 'uppercase' }}>
              Move to
            </div>
            {categories.map((cat) => (
              <button
                key={cat.value}
                onClick={(e) => { e.stopPropagation(); handleMoveToCategory(docId, cat.value) }}
                style={{
                  width: '100%',
                  padding: '8px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '13px',
                  color: colors.textSecondary,
                  textAlign: 'left',
                  transition: 'background-color 0.15s ease',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.borderLight}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <span>📁</span> {cat.label}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: colors.pageBg }}>
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
          <img
            src="/owl.png"
            alt="Second Brain Logo"
            style={{
              width: '36px',
              height: '36px',
              objectFit: 'contain',
            }}
          />
          <span style={{
            fontSize: '18px',
            fontWeight: 700,
            color: colors.textPrimary,
            letterSpacing: '-0.02em',
          }}>
            Second Brain
          </span>
        </div>

        {/* Center Navigation */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
          {[
            { label: 'Chat', path: '/' },
            { label: 'Documents', path: '/documents', active: true },
            { label: 'Knowledge Gaps', path: '/knowledge-gaps' },
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
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!item.active) {
                  e.currentTarget.style.color = colors.textPrimary
                }
              }}
              onMouseLeave={(e) => {
                if (!item.active) {
                  e.currentTarget.style.color = colors.textSecondary
                }
              }}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Right Cluster */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button style={{
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'transparent',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={colors.textMuted} strokeWidth="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
          </button>
          <button style={{
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'transparent',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={colors.textMuted} strokeWidth="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
          </button>
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
              transition: 'all 0.15s ease',
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

      {/* Main Content */}
      <main style={{ padding: '32px' }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '32px',
        }}>
          <h1 style={{
            fontSize: '28px',
            fontWeight: 700,
            color: colors.textPrimary,
            margin: 0,
          }}>
            Documents
          </h1>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 20px',
                backgroundColor: uploading ? colors.textMuted : colors.primary,
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '14px',
                fontWeight: 500,
                cursor: uploading ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!uploading) e.currentTarget.style.backgroundColor = colors.primaryHover
              }}
              onMouseLeave={(e) => {
                if (!uploading) e.currentTarget.style.backgroundColor = colors.primary
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              {uploading ? 'Uploading...' : 'Add Document'}
            </button>
            <button
              onClick={() => router.push('/knowledge-gaps')}
              disabled={documents.length === 0}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 20px',
                backgroundColor: documents.length === 0 ? colors.textMuted : colors.statusGreen,
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '14px',
                fontWeight: 500,
                cursor: documents.length === 0 ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (documents.length > 0) e.currentTarget.style.backgroundColor = '#16A34A'
              }}
              onMouseLeave={(e) => {
                if (documents.length > 0) e.currentTarget.style.backgroundColor = colors.statusGreen
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8"/>
                <path d="m21 21-4.35-4.35"/>
              </svg>
              Find Gaps
            </button>
          </div>
        </div>

        {/* Folders Section */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '16px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h2 style={{
                fontSize: '16px',
                fontWeight: 600,
                color: colors.textPrimary,
                margin: 0,
              }}>
                Folders
              </h2>
              <button style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 10px',
                backgroundColor: 'transparent',
                border: 'none',
                color: colors.primary,
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
              }}>
                + New folder
              </button>
            </div>
            <button style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 10px',
              backgroundColor: 'transparent',
              border: 'none',
              color: colors.primary,
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
            }}>
              + View all
            </button>
          </div>

          <div style={{
            display: 'flex',
            gap: '16px',
            overflowX: 'auto',
            paddingBottom: '8px',
          }}>
            <FolderCard
              title="All Documents"
              count={counts.all}
              size={`${Math.floor(counts.all * 0.8)} MB`}
              active={activeCategory === 'All Items'}
              onClick={() => setActiveCategory('All Items')}
            />
            <FolderCard
              title="Work Documents"
              count={counts.documents}
              size={`${Math.floor(counts.documents * 1.2)} MB`}
              active={activeCategory === 'Documents'}
              onClick={() => setActiveCategory('Documents')}
            />
            <FolderCard
              title="Code Files"
              count={counts.code}
              size={`${Math.floor(counts.code * 0.5)} MB`}
              active={activeCategory === 'Code'}
              onClick={() => setActiveCategory('Code')}
            />
            <FolderCard
              title="Web Scraper"
              count={counts.webscraper}
              size={`${Math.floor(counts.webscraper * 0.3)} MB`}
              active={activeCategory === 'Web Scraper'}
              onClick={() => setActiveCategory('Web Scraper')}
            />
            <FolderCard
              title="Personal & Other"
              count={counts.personal + counts.other}
              size={`${Math.floor((counts.personal + counts.other) * 0.6)} MB`}
              active={activeCategory === 'Personal Items' || activeCategory === 'Other Items'}
              onClick={() => setActiveCategory('Personal Items')}
            />
          </div>
        </div>

        {/* Files Section */}
        <div style={{
          backgroundColor: colors.cardBg,
          borderRadius: '12px',
          border: `1px solid ${colors.border}`,
          boxShadow: shadows.sm,
          overflow: 'hidden',
        }}>
          {/* Filter Bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: `1px solid ${colors.border}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <FilterPill label="Sort by: latest" />
              <FilterPill label="Filter keywords" />
              <FilterPill label="Type" />
              <FilterPill label="Source" />
              <FilterPill label="Status" />
              {activeFilters.map(filter => (
                <FilterPill
                  key={filter}
                  label={filter}
                  active
                  hasClose
                  onClose={() => removeFilter(filter)}
                />
              ))}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {/* Bulk Actions - show when items selected */}
              {selectedDocs.size > 0 && (
                <>
                  <span style={{ fontSize: '13px', color: colors.textSecondary }}>
                    {selectedDocs.size} selected
                  </span>
                  {/* Bulk Move Dropdown */}
                  <select
                    onChange={(e) => {
                      if (e.target.value) {
                        handleBulkMoveToCategory(e.target.value)
                        e.target.value = ''
                      }
                    }}
                    style={{
                      padding: '8px 12px',
                      backgroundColor: colors.cardBg,
                      border: `1px solid ${colors.border}`,
                      borderRadius: '6px',
                      fontSize: '13px',
                      color: colors.textSecondary,
                      cursor: 'pointer',
                    }}
                  >
                    <option value="">Move to...</option>
                    <option value="Documents">Documents</option>
                    <option value="Code">Code</option>
                    <option value="Meetings">Meetings</option>
                    <option value="Web Scraper">Web Scraper</option>
                    <option value="Personal Items">Personal Items</option>
                    <option value="Other Items">Other Items</option>
                  </select>
                  {/* Bulk Delete Button */}
                  <button
                    onClick={handleBulkDelete}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 14px',
                      backgroundColor: colors.statusRed,
                      border: 'none',
                      borderRadius: '6px',
                      color: '#fff',
                      fontSize: '13px',
                      fontWeight: 500,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#DC2626'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = colors.statusRed}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                    Delete
                  </button>
                </>
              )}
              {/* Search */}
              <div style={{ position: 'relative', minWidth: '200px' }}>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search"
                  style={{
                    width: '100%',
                    padding: '10px 16px',
                    paddingLeft: '40px',
                    backgroundColor: colors.borderLight,
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '14px',
                    color: colors.textPrimary,
                    outline: 'none',
                  }}
                />
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke={colors.textMuted}
                  strokeWidth="2"
                  style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }}
                >
                  <circle cx="11" cy="11" r="8"/>
                  <path d="m21 21-4.35-4.35"/>
                </svg>
              </div>
            </div>
          </div>

          {/* Table */}
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
          ) : filteredDocuments.length === 0 ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '80px',
              gap: '16px',
            }}>
              <div style={{ fontSize: '48px', opacity: 0.4 }}>📂</div>
              <h3 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
                {searchQuery ? 'No documents found' : 'No documents yet'}
              </h3>
              <p style={{ fontSize: '14px', color: colors.textMuted, margin: 0 }}>
                {searchQuery
                  ? `No documents match "${searchQuery}"`
                  : 'Connect your tools or upload documents to get started'}
              </p>
            </div>
          ) : (
            <>
              {/* Table Header */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '24px 2fr 1.2fr 1fr 1fr 100px 140px 48px',
                gap: '16px',
                padding: '12px 20px',
                backgroundColor: colors.cardBg,
                borderBottom: `1px solid ${colors.border}`,
              }}>
                <div>
                  <input
                    type="checkbox"
                    checked={selectedDocs.size === filteredDocuments.slice(0, displayLimit).length && filteredDocuments.length > 0}
                    onChange={toggleSelectAll}
                    style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                  />
                </div>
                {[
                  { label: 'Document', field: 'name' },
                  { label: 'Type', field: 'type' },
                  { label: 'Source', field: 'source_type' },
                  { label: 'Date', field: 'created' },
                  { label: 'Status', field: 'classification' },
                  { label: 'Personal %', field: 'score' },
                ].map((col) => (
                  <button
                    key={col.field}
                    onClick={() => toggleSort(col.field)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      fontSize: '12px',
                      fontWeight: 500,
                      color: colors.textMuted,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      cursor: 'pointer',
                    }}
                  >
                    {col.label}
                    <SortIcon field={col.field} />
                  </button>
                ))}
                <div />
              </div>

              {/* Table Body */}
              <div>
                {filteredDocuments.slice(0, displayLimit).map((doc) => {
                  const status = getStatusInfo(doc.classification, doc.source_type)
                  const isSelected = selectedDocs.has(doc.id)
                  return (
                    <div
                      key={doc.id}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '24px 2fr 1.2fr 1fr 1fr 100px 140px 48px',
                        gap: '16px',
                        padding: '16px 20px',
                        alignItems: 'center',
                        borderBottom: `1px solid ${colors.borderLight}`,
                        transition: 'background-color 0.15s ease',
                        cursor: 'pointer',
                        backgroundColor: isSelected ? colors.primaryLight : 'transparent',
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected) e.currentTarget.style.backgroundColor = colors.borderLight
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent'
                      }}
                      onClick={() => viewDocument(doc.id)}
                    >
                      <div onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedDocs.has(doc.id)}
                          onChange={() => toggleDocSelection(doc.id)}
                          style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                        />
                      </div>

                      {/* Document Name */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', overflow: 'hidden' }}>
                        <div style={{
                          width: '32px',
                          height: '32px',
                          backgroundColor: colors.borderLight,
                          borderRadius: '6px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill={colors.textMuted}>
                            <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z"/>
                          </svg>
                        </div>
                        <span style={{
                          fontSize: '14px',
                          fontWeight: 500,
                          color: colors.textPrimary,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}>
                          {doc.name}
                        </span>
                      </div>

                      {/* Type */}
                      <span style={{ fontSize: '13px', color: colors.textSecondary }}>
                        {doc.type}
                      </span>

                      {/* Source */}
                      <span style={{ fontSize: '13px', color: colors.textSecondary }}>
                        {doc.source_type || 'Upload'}
                      </span>

                      {/* Date */}
                      <span style={{ fontSize: '13px', color: colors.textSecondary }}>
                        {doc.created}
                      </span>

                      {/* Status */}
                      <StatusIndicator status={status.label} color={status.color} />

                      {/* Score */}
                      <ProgressBar value={doc.score || 75} />

                      {/* Actions */}
                      <div onClick={(e) => e.stopPropagation()}>
                        <ActionMenu docId={doc.id} docName={doc.name} />
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Load More */}
              {filteredDocuments.length > displayLimit && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  padding: '20px',
                  borderTop: `1px solid ${colors.border}`,
                }}>
                  <button
                    onClick={() => setDisplayLimit(prev => prev + 50)}
                    style={{
                      padding: '10px 24px',
                      backgroundColor: 'transparent',
                      border: `1px solid ${colors.border}`,
                      borderRadius: '8px',
                      color: colors.textSecondary,
                      fontSize: '14px',
                      fontWeight: 500,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.borderColor = colors.textMuted}
                    onMouseLeave={(e) => e.currentTarget.style.borderColor = colors.border}
                  >
                    Show More ({filteredDocuments.length - displayLimit} remaining)
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* Document Viewer Modal */}
      {viewingDocument && (
        <DocumentViewer
          document={viewingDocument}
          onClose={() => setViewingDocument(null)}
        />
      )}

      {/* Loading Overlay */}
      {loadingDocument && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            backgroundColor: colors.cardBg,
            borderRadius: '12px',
            padding: '32px',
            boxShadow: shadows.lg,
          }}>
            <span style={{ fontSize: '15px', fontWeight: 500, color: colors.textPrimary }}>
              Loading document...
            </span>
          </div>
        </div>
      )}

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.xls"
        onChange={handleFileUpload}
        style={{ display: 'none' }}
      />
    </div>
  )
}
