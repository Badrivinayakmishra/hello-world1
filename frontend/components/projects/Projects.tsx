'use client'

import React, { useState, useEffect } from 'react'
import Sidebar from '../shared/Sidebar'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003') + '/api'

interface Project {
  id: string
  name: string
  description: string
  document_count: number
  status: string
}

const StatusBadge = ({ status }: { status: string }) => {
  const colors: Record<string, { bg: string; text: string; border: string }> = {
    active: { bg: '#D1FAE5', text: '#059669', border: '#6EE7B7' },
    completed: { bg: '#E0E7FF', text: '#3730A3', border: '#A5B4FC' },
    archived: { bg: '#F3F4F6', text: '#6B7280', border: '#D1D5DB' }
  }
  const color = colors[status] || colors.active

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
      {status}
    </span>
  )
}

const ProjectCard = ({
  project,
  isExpanded,
  onToggle
}: {
  project: Project
  isExpanded: boolean
  onToggle: () => void
}) => {
  return (
    <div
      style={{
        borderRadius: '12px',
        border: '1px solid #D4D4D8',
        backgroundColor: '#FFF',
        overflow: 'hidden',
        marginBottom: '12px'
      }}
    >
      {/* Project Header */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 20px',
          backgroundColor: isExpanded ? '#FFF9F2' : '#FFF',
          cursor: 'pointer',
          transition: 'background-color 0.2s'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
          <span style={{ fontSize: '20px' }}>📁</span>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
              <h3
                style={{
                  color: '#18181B',
                  fontFamily: '"Work Sans", sans-serif',
                  fontSize: '16px',
                  fontWeight: 600,
                  margin: 0
                }}
              >
                {project.name}
              </h3>
              <StatusBadge status={project.status} />
            </div>
            {project.description && (
              <p
                style={{
                  color: '#71717A',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '13px',
                  lineHeight: '18px',
                  margin: 0
                }}
              >
                {project.description}
              </p>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              backgroundColor: '#FFE2BF',
              padding: '6px 12px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <span style={{ fontSize: '12px' }}>📄</span>
            <span
              style={{
                color: '#F97316',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px',
                fontWeight: 600
              }}
            >
              {project.document_count}
            </span>
          </div>
          <span style={{ fontSize: '12px', color: '#9CA3AF' }}>
            {isExpanded ? '▲' : '▼'}
          </span>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div
          style={{
            padding: '20px',
            borderTop: '1px solid #E5E7EB',
            backgroundColor: '#FAFAFA'
          }}
        >
          <div style={{ marginBottom: '16px' }}>
            <h4
              style={{
                color: '#18181B',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px',
                fontWeight: 600,
                marginBottom: '8px'
              }}
            >
              Project Details
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px', margin: '0 0 4px' }}>
                  Documents
                </p>
                <p style={{ color: '#18181B', fontFamily: '"Work Sans"', fontSize: '14px', fontWeight: 500, margin: 0 }}>
                  {project.document_count}
                </p>
              </div>
              <div>
                <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px', margin: '0 0 4px' }}>
                  Status
                </p>
                <StatusBadge status={project.status} />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Projects() {
  const [activeItem, setActiveItem] = useState('Projects')
  const [projects, setProjects] = useState<Project[]>([])
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'completed' | 'archived'>('all')

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    try {
      const response = await axios.get(`${API_BASE}/projects`)

      if (response.data.projects) {
        const projectList: Project[] = response.data.projects.map((p: any) => ({
          id: p.id || `project_${Math.random().toString(36).substr(2, 9)}`,
          name: p.name,
          description: p.description || '',
          document_count: p.document_count || 0,
          status: p.status || 'active'
        }))

        setProjects(projectList)
      }
    } catch (error) {
      console.error('Error loading projects:', error)
    } finally {
      setLoading(false)
    }
  }


  const toggleProject = (projectId: string) => {
    setExpandedProjects(prev => {
      const next = new Set(prev)
      if (next.has(projectId)) {
        next.delete(projectId)
      } else {
        next.add(projectId)
      }
      return next
    })
  }

  // Filter projects
  const filteredProjects = projects.filter(p => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      const matchesName = p.name.toLowerCase().includes(query)
      const matchesDescription = p.description.toLowerCase().includes(query)
      if (!matchesName && !matchesDescription) return false
    }
    // Status filter
    if (statusFilter !== 'all' && p.status !== statusFilter) return false
    return true
  })

  const totalProjects = projects.length
  const totalDocuments = projects.reduce((sum, p) => sum + p.document_count, 0)

  return (
    <div className="flex h-screen bg-primary overflow-hidden">
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
              Projects
            </h1>
            <p
              style={{
                color: '#71717A',
                fontFamily: 'Inter, sans-serif',
                fontSize: '15px',
                lineHeight: '22px'
              }}
            >
              Content-based project discovery using LLM clustering
            </p>
          </div>

          {/* Stats */}
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
                {totalProjects}
              </p>
              <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px' }}>Projects</p>
            </div>
            <div style={{ width: '1px', height: '40px', backgroundColor: '#D4D4D8' }} />
            <div style={{ textAlign: 'center' }}>
              <p style={{ color: '#F97316', fontFamily: '"Work Sans"', fontSize: '24px', fontWeight: 600 }}>
                {totalDocuments}
              </p>
              <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '12px' }}>Documents</p>
            </div>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="px-8 pb-4 bg-primary">
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <input
              type="text"
              placeholder="Search projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '320px',
                height: '42px',
                padding: '0 16px',
                borderRadius: '8px',
                border: '1px solid #D4D4D8',
                backgroundColor: '#FFF',
                outline: 'none',
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px'
              }}
            />

            <div style={{ display: 'flex', gap: '8px' }}>
              {(['all', 'active', 'completed', 'archived'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setStatusFilter(f)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    backgroundColor: statusFilter === f ? '#FFE2BF' : '#FFF',
                    border: '1px solid #D4D4D8',
                    color: '#18181B',
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '13px',
                    fontWeight: statusFilter === f ? 500 : 400,
                    cursor: 'pointer',
                    textTransform: 'capitalize'
                  }}
                >
                  {f === 'all' ? 'All Status' : f}
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
                Loading projects...
              </p>
            </div>
          ) : filteredProjects.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '300px' }}>
              <div
                style={{
                  width: '80px',
                  height: '80px',
                  borderRadius: '50%',
                  backgroundColor: '#FFE2BF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '16px'
                }}
              >
                <span style={{ fontSize: '32px' }}>📁</span>
              </div>
              <h3 style={{ color: '#18181B', fontFamily: '"Work Sans"', fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
                No projects found
              </h3>
              <p style={{ color: '#71717A', fontFamily: 'Inter', fontSize: '14px', textAlign: 'center', maxWidth: '400px' }}>
                {searchQuery || statusFilter !== 'all'
                  ? 'Try adjusting your search or filters.'
                  : 'No projects available yet.'}
              </p>
            </div>
          ) : (
            <div style={{ maxWidth: '1000px' }}>
              {filteredProjects.map(project => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  isExpanded={expandedProjects.has(project.id)}
                  onToggle={() => toggleProject(project.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
