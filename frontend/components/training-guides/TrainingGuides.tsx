'use client'

import React, { useState, useEffect } from 'react'
import Sidebar from '../shared/Sidebar'
import Image from 'next/image'
import axios from 'axios'

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003') + '/api'

interface Material {
  id: string
  name: string
  description: string
  file: string
  download_url: string
  thumbnail: string | null
  category: string
}

const MaterialCard = ({ material, type }: { material: Material, type: string }) => {
  const getCategoryIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case 'development':
        return '/Development.svg'
      case 'design':
        return '/Pencil.svg'
      case 'marketing':
        return '/marketing.svg'
      default:
        return '/Development.svg'
    }
  }

  return (
    <div 
      className="flex flex-col items-start gap-[30px] bg-secondary rounded-xl overflow-hidden border border-gray-200 hover:shadow-lg transition-shadow cursor-pointer"
      style={{
        width: '328px',
        height: '380px'
      }}
    >
      {/* Thumbnail Preview */}
      <div 
        className="w-full bg-gray-200 flex items-center justify-center overflow-hidden"
        style={{ height: '200px' }}
      >
        {material.thumbnail ? (
          <img 
            src={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003'}${material.thumbnail}`}
            alt={material.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-orange-300 to-orange-500 flex items-center justify-center">
            <span className="text-white font-work text-lg font-semibold">
              {material.name.substring(0, 20)}...
            </span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="px-5 pb-5 flex-1 flex flex-col justify-between w-full">
        {/* Top section */}
        <div>
          <h3 className="text-neutral-800 font-work text-base font-semibold mb-2">
            {material.name}
          </h3>
          <p className="text-gray-600 font-sans text-sm line-clamp-2">
            {material.description}
          </p>
        </div>

        {/* Divider */}
        <div 
          className="my-3"
          style={{
            width: '100%',
            height: '0',
            borderTop: '0.6px solid #0B1739'
          }}
        />

        {/* Bottom section - Category tag */}
        <div className="flex items-center justify-between">
          <div 
            className="flex items-center gap-2 px-[6px] py-[3px] rounded-sm border"
            style={{
              borderColor: '#FFE2BF',
              backgroundColor: '#FFE2BF'
            }}
          >
            <Image 
              src={getCategoryIcon(material.category)} 
              alt={material.category}
              width={14}
              height={14}
            />
            <span 
              className="font-work font-medium"
              style={{
                color: '#081028',
                fontSize: '14px',
                lineHeight: '14px'
              }}
            >
              {material.category}
            </span>
          </div>
          
          {/* Three dots - placeholder for later */}
          <div className="text-gray-400 text-lg">•••</div>
        </div>
      </div>
    </div>
  )
}

export default function TrainingGuides() {
  const [activeItem, setActiveItem] = useState('Training Guides')
  const [materials, setMaterials] = useState<{ videos: Material[], documents: Material[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadMaterials()
  }, [])

  const loadMaterials = async () => {
    try {
      const response = await axios.get(`${API_BASE}/training-materials`)
      if (response.data.success) {
        setMaterials(response.data.materials)
      }
    } catch (error) {
      console.error('Error loading materials:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen bg-primary overflow-hidden">
      {/* Sidebar */}
      <Sidebar activeItem={activeItem} onItemClick={setActiveItem} />

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <div className="flex items-center px-8 py-4 bg-primary">
          <div className="flex-1 flex justify-center">
            <h1 className="text-neutral-800 font-work text-xl font-semibold">
              Training Guides
            </h1>
          </div>

          <div className="flex items-center gap-4">
            <input
              type="text"
              placeholder="Search for..."
              className="h-[42px] px-4 rounded border border-neutral-500 bg-secondary text-sm outline-none"
              style={{ width: '352px' }}
            />
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto px-8 py-6">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-neutral-800 font-work text-lg">Loading materials...</div>
            </div>
          ) : (
            <div 
              className="flex items-start gap-[30px]"
            >
              {/* Training Videos Column */}
              <div 
                className="flex flex-col items-start gap-[30px]"
              >
                <div className="flex items-center gap-2">
                  <h2 
                    className="font-work font-medium"
                    style={{
                      color: '#081028',
                      fontSize: '14px',
                      lineHeight: '14px'
                    }}
                  >
                    Training Videos
                  </h2>
                  <div 
                    className="flex items-center px-[5px] py-[1px] rounded-sm border"
                    style={{
                      borderColor: '#FFE2BF',
                      backgroundColor: '#FFE2BF'
                    }}
                  >
                    <span 
                      className="font-work font-medium text-xs"
                      style={{ color: '#081028' }}
                    >
                      10+ hrs
                    </span>
                  </div>
                </div>

                <div className="flex flex-col gap-[30px]">
                  {materials?.videos.map((video) => (
                    <MaterialCard key={video.id} material={video} type="video" />
                  ))}
                </div>
              </div>

              {/* Documents Column */}
              <div 
                className="flex flex-col items-start gap-[30px]"
              >
                <div className="flex items-center gap-2">
                  <h2 
                    className="font-work font-medium"
                    style={{
                      color: '#081028',
                      fontSize: '14px',
                      lineHeight: '14px'
                    }}
                  >
                    Documents
                  </h2>
                  <div 
                    className="flex items-center px-[5px] py-[1px] rounded-sm border"
                    style={{
                      borderColor: '#FFE2BF',
                      backgroundColor: '#FFE2BF'
                    }}
                  >
                    <span 
                      className="font-work font-medium text-xs"
                      style={{ color: '#081028' }}
                    >
                      20 min approx.
                    </span>
                  </div>
                </div>

                <div className="flex flex-col gap-[30px]">
                  {materials?.documents.map((doc) => (
                    <MaterialCard key={doc.id} material={doc} type="document" />
                  ))}
                </div>
              </div>

              {/* Employee Recorded Videos Column */}
              <div 
                className="flex flex-col items-start gap-[30px]"
              >
                <div className="flex items-center gap-2">
                  <h2 
                    className="font-work font-medium"
                    style={{
                      color: '#081028',
                      fontSize: '14px',
                      lineHeight: '14px'
                    }}
                  >
                    Employee Recorded Videos
                  </h2>
                  <div 
                    className="flex items-center px-[5px] py-[1px] rounded-sm border"
                    style={{
                      borderColor: '#FFE2BF',
                      backgroundColor: '#FFE2BF'
                    }}
                  >
                    <span 
                      className="font-work font-medium text-xs"
                      style={{ color: '#081028' }}
                    >
                      1 hr approx.
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-center h-64 text-gray-400 font-sans text-sm">
                  No recordings yet
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
