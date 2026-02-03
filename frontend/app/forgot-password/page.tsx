'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { validateEmail } from '@/utils/validation'
import { authApi } from '@/utils/api'

// Catalyst-style color palette
const colors = {
  primary: '#1e3a5f',
  primaryHover: '#152a45',
  secondary: '#0d9488',
  background: '#f8fafc',
  card: '#ffffff',
  text: '#1e293b',
  textMuted: '#64748b',
  border: '#e2e8f0',
  error: '#dc2626',
  errorBg: '#fef2f2',
  success: '#22c55e',
  successBg: '#f0fdf4',
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()

    // Validate email
    const emailResult = validateEmail(email)
    if (!emailResult.isValid) {
      setError(emailResult.error || 'Invalid email')
      return
    }

    setError('')
    setIsLoading(true)

    try {
      await authApi.forgotPassword(email)
      setIsSubmitted(true)
    } catch (err) {
      // Always show success to prevent email enumeration
      setIsSubmitted(true)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit()
    }
  }

  if (isSubmitted) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: colors.background,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <header
          style={{
            padding: '24px 32px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <Image src="/owl.png" alt="2nd Brain" width={36} height={45} />
          <span style={{ fontSize: '20px', fontWeight: 600, color: colors.primary }}>
            2nd Brain
          </span>
        </header>

        {/* Main content */}
        <main
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px 20px',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '420px',
              backgroundColor: colors.card,
              borderRadius: '16px',
              boxShadow: '0 4px 24px rgba(0, 0, 0, 0.08)',
              padding: '40px',
              textAlign: 'center',
            }}
          >
            {/* Success icon */}
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: colors.successBg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 24px',
              }}
            >
              <svg
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="none"
                stroke={colors.success}
                strokeWidth="2"
              >
                <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>

            <h1
              style={{
                fontSize: '24px',
                fontWeight: 700,
                color: colors.text,
                marginBottom: '12px',
              }}
            >
              Check your email
            </h1>
            <p
              style={{
                fontSize: '15px',
                color: colors.textMuted,
                marginBottom: '24px',
                lineHeight: '1.5',
              }}
            >
              If an account exists for <strong>{email}</strong>, we've sent password reset
              instructions to that address.
            </p>

            <Link
              href="/login"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                color: colors.secondary,
                fontSize: '15px',
                fontWeight: 500,
                textDecoration: 'none',
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              Back to sign in
            </Link>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: colors.background,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header */}
      <header
        style={{
          padding: '24px 32px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <Image src="/owl.png" alt="2nd Brain" width={36} height={45} />
        <span style={{ fontSize: '20px', fontWeight: 600, color: colors.primary }}>
          2nd Brain
        </span>
      </header>

      {/* Main content */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px 20px',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: '420px',
            backgroundColor: colors.card,
            borderRadius: '16px',
            boxShadow: '0 4px 24px rgba(0, 0, 0, 0.08)',
            padding: '40px',
          }}
        >
          {/* Title */}
          <h1
            style={{
              fontSize: '28px',
              fontWeight: 700,
              color: colors.text,
              marginBottom: '8px',
              textAlign: 'center',
            }}
          >
            Forgot password?
          </h1>
          <p
            style={{
              fontSize: '15px',
              color: colors.textMuted,
              marginBottom: '32px',
              textAlign: 'center',
            }}
          >
            Enter your email and we'll send you reset instructions
          </p>

          {/* Error */}
          {error && (
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: colors.errorBg,
                borderRadius: '8px',
                marginBottom: '24px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM10 6v4m0 4h.01"
                  stroke={colors.error}
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
              <span style={{ fontSize: '14px', color: colors.error }}>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '24px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: colors.text,
                  marginBottom: '8px',
                }}
              >
                Email address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setError('')
                }}
                onKeyPress={handleKeyPress}
                placeholder="you@company.com"
                style={{
                  width: '100%',
                  height: '48px',
                  padding: '0 16px',
                  fontSize: '15px',
                  borderRadius: '8px',
                  border: `1px solid ${error ? colors.error : colors.border}`,
                  backgroundColor: colors.card,
                  outline: 'none',
                  transition: 'border-color 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => (e.target.style.borderColor = colors.primary)}
                onBlur={(e) => (e.target.style.borderColor = error ? colors.error : colors.border)}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              style={{
                width: '100%',
                height: '48px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: isLoading ? colors.textMuted : colors.primary,
                color: '#ffffff',
                fontSize: '15px',
                fontWeight: 600,
                cursor: isLoading ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
              onMouseEnter={(e) => {
                if (!isLoading) e.currentTarget.style.backgroundColor = colors.primaryHover
              }}
              onMouseLeave={(e) => {
                if (!isLoading) e.currentTarget.style.backgroundColor = colors.primary
              }}
            >
              {isLoading ? (
                <>
                  <div
                    style={{
                      width: '18px',
                      height: '18px',
                      border: '2px solid rgba(255,255,255,0.3)',
                      borderTopColor: '#fff',
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite',
                    }}
                  />
                  Sending...
                </>
              ) : (
                'Send reset instructions'
              )}
            </button>
          </form>

          <p
            style={{
              textAlign: 'center',
              marginTop: '24px',
              fontSize: '14px',
              color: colors.textMuted,
            }}
          >
            <Link
              href="/login"
              style={{
                color: colors.secondary,
                fontWeight: 500,
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              Back to sign in
            </Link>
          </p>
        </div>
      </main>

      <style jsx>{`
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  )
}
