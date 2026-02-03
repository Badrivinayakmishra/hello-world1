'use client'

import React, { useState, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { validateSignup, getPasswordStrength, validatePasswordMatch } from '@/utils/validation'

// Catalyst-style color palette with 2nd Brain branding
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
}

export default function SignupPage() {
  const router = useRouter()
  const { signup, isAuthenticated, isLoading: authLoading } = useAuth()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [organizationName, setOrganizationName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [acceptTerms, setAcceptTerms] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(false)

  // Password strength indicator
  const passwordStrength = getPasswordStrength(password)

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      router.push('/documents')
    }
  }, [isAuthenticated, router])

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()

    // Validate form
    const validation = validateSignup({
      email,
      password,
      fullName,
      organizationName: organizationName || undefined,
    })

    const errors = { ...validation.errors }

    // Check password match
    const matchResult = validatePasswordMatch(password, confirmPassword)
    if (!matchResult.isValid && matchResult.error) {
      errors.confirmPassword = matchResult.error
    }

    // Check terms
    if (!acceptTerms) {
      errors.terms = 'You must accept the terms and conditions'
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }

    setFieldErrors({})
    setError('')
    setIsLoading(true)

    try {
      const result = await signup(email, password, fullName, organizationName || undefined)

      if (!result.success) {
        if (result.error?.includes('already exists')) {
          setError('An account with this email already exists.')
        } else {
          setError(result.error || 'Signup failed. Please try again.')
        }
      }
      // Success handled by AuthContext redirect
    } catch (err) {
      setError('Connection error. Please check your internet connection.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit()
    }
  }

  // Show loading spinner while checking auth
  if (authLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: colors.background,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            width: '40px',
            height: '40px',
            border: `3px solid ${colors.border}`,
            borderTopColor: colors.primary,
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
          }}
        />
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

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: colors.background,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header with logo */}
      <header
        style={{
          padding: '24px 32px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <Image src="/owl.png" alt="2nd Brain" width={36} height={45} />
        <span
          style={{
            fontSize: '20px',
            fontWeight: 600,
            color: colors.primary,
          }}
        >
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
            maxWidth: '460px',
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
            Create your account
          </h1>
          <p
            style={{
              fontSize: '15px',
              color: colors.textMuted,
              marginBottom: '32px',
              textAlign: 'center',
            }}
          >
            Start building your organizational knowledge base
          </p>

          {/* Error message */}
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
            {/* Full Name */}
            <div style={{ marginBottom: '20px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: colors.text,
                  marginBottom: '8px',
                }}
              >
                Full name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value)
                  setFieldErrors((prev) => ({ ...prev, fullName: '' }))
                }}
                onKeyPress={handleKeyPress}
                placeholder="John Doe"
                style={{
                  width: '100%',
                  height: '48px',
                  padding: '0 16px',
                  fontSize: '15px',
                  borderRadius: '8px',
                  border: `1px solid ${fieldErrors.fullName ? colors.error : colors.border}`,
                  backgroundColor: colors.card,
                  outline: 'none',
                  transition: 'border-color 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => (e.target.style.borderColor = colors.primary)}
                onBlur={(e) =>
                  (e.target.style.borderColor = fieldErrors.fullName ? colors.error : colors.border)
                }
              />
              {fieldErrors.fullName && (
                <p style={{ fontSize: '13px', color: colors.error, marginTop: '6px' }}>
                  {fieldErrors.fullName}
                </p>
              )}
            </div>

            {/* Email */}
            <div style={{ marginBottom: '20px' }}>
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
                  setFieldErrors((prev) => ({ ...prev, email: '' }))
                }}
                onKeyPress={handleKeyPress}
                placeholder="you@company.com"
                style={{
                  width: '100%',
                  height: '48px',
                  padding: '0 16px',
                  fontSize: '15px',
                  borderRadius: '8px',
                  border: `1px solid ${fieldErrors.email ? colors.error : colors.border}`,
                  backgroundColor: colors.card,
                  outline: 'none',
                  transition: 'border-color 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => (e.target.style.borderColor = colors.primary)}
                onBlur={(e) =>
                  (e.target.style.borderColor = fieldErrors.email ? colors.error : colors.border)
                }
              />
              {fieldErrors.email && (
                <p style={{ fontSize: '13px', color: colors.error, marginTop: '6px' }}>
                  {fieldErrors.email}
                </p>
              )}
            </div>

            {/* Password */}
            <div style={{ marginBottom: '20px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: colors.text,
                  marginBottom: '8px',
                }}
              >
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    setFieldErrors((prev) => ({ ...prev, password: '' }))
                  }}
                  onKeyPress={handleKeyPress}
                  placeholder="Create a strong password"
                  style={{
                    width: '100%',
                    height: '48px',
                    padding: '0 48px 0 16px',
                    fontSize: '15px',
                    borderRadius: '8px',
                    border: `1px solid ${fieldErrors.password ? colors.error : colors.border}`,
                    backgroundColor: colors.card,
                    outline: 'none',
                    transition: 'border-color 0.2s',
                    boxSizing: 'border-box',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = colors.primary)}
                  onBlur={(e) =>
                    (e.target.style.borderColor = fieldErrors.password
                      ? colors.error
                      : colors.border)
                  }
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '4px',
                  }}
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={colors.textMuted}
                    strokeWidth="2"
                  >
                    {showPassword ? (
                      <>
                        <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </>
                    ) : (
                      <>
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </>
                    )}
                  </svg>
                </button>
              </div>
              {/* Password strength indicator */}
              {password && (
                <div style={{ marginTop: '8px' }}>
                  <div
                    style={{
                      height: '4px',
                      backgroundColor: colors.border,
                      borderRadius: '2px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${(passwordStrength.score / 7) * 100}%`,
                        backgroundColor: passwordStrength.color,
                        transition: 'width 0.3s, background-color 0.3s',
                      }}
                    />
                  </div>
                  <p style={{ fontSize: '12px', color: passwordStrength.color, marginTop: '4px' }}>
                    Password strength:{' '}
                    {passwordStrength.level.charAt(0).toUpperCase() + passwordStrength.level.slice(1)}
                  </p>
                </div>
              )}
              {fieldErrors.password && (
                <p style={{ fontSize: '13px', color: colors.error, marginTop: '6px' }}>
                  {fieldErrors.password}
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div style={{ marginBottom: '20px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: colors.text,
                  marginBottom: '8px',
                }}
              >
                Confirm password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value)
                    setFieldErrors((prev) => ({ ...prev, confirmPassword: '' }))
                  }}
                  onKeyPress={handleKeyPress}
                  placeholder="Confirm your password"
                  style={{
                    width: '100%',
                    height: '48px',
                    padding: '0 48px 0 16px',
                    fontSize: '15px',
                    borderRadius: '8px',
                    border: `1px solid ${fieldErrors.confirmPassword ? colors.error : colors.border}`,
                    backgroundColor: colors.card,
                    outline: 'none',
                    transition: 'border-color 0.2s',
                    boxSizing: 'border-box',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = colors.primary)}
                  onBlur={(e) =>
                    (e.target.style.borderColor = fieldErrors.confirmPassword
                      ? colors.error
                      : colors.border)
                  }
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '4px',
                  }}
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={colors.textMuted}
                    strokeWidth="2"
                  >
                    {showConfirmPassword ? (
                      <>
                        <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </>
                    ) : (
                      <>
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </>
                    )}
                  </svg>
                </button>
              </div>
              {fieldErrors.confirmPassword && (
                <p style={{ fontSize: '13px', color: colors.error, marginTop: '6px' }}>
                  {fieldErrors.confirmPassword}
                </p>
              )}
            </div>

            {/* Organization Name (optional) */}
            <div style={{ marginBottom: '20px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: colors.text,
                  marginBottom: '8px',
                }}
              >
                Organization name{' '}
                <span style={{ color: colors.textMuted, fontWeight: 400 }}>(optional)</span>
              </label>
              <input
                type="text"
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Your company or team name"
                style={{
                  width: '100%',
                  height: '48px',
                  padding: '0 16px',
                  fontSize: '15px',
                  borderRadius: '8px',
                  border: `1px solid ${colors.border}`,
                  backgroundColor: colors.card,
                  outline: 'none',
                  transition: 'border-color 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => (e.target.style.borderColor = colors.primary)}
                onBlur={(e) => (e.target.style.borderColor = colors.border)}
              />
            </div>

            {/* Terms checkbox */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                marginBottom: '24px',
              }}
            >
              <input
                type="checkbox"
                id="terms"
                checked={acceptTerms}
                onChange={(e) => {
                  setAcceptTerms(e.target.checked)
                  setFieldErrors((prev) => ({ ...prev, terms: '' }))
                }}
                style={{
                  width: '16px',
                  height: '16px',
                  marginTop: '2px',
                  cursor: 'pointer',
                  accentColor: colors.primary,
                }}
              />
              <label
                htmlFor="terms"
                style={{
                  fontSize: '14px',
                  color: colors.textMuted,
                  cursor: 'pointer',
                  lineHeight: '1.4',
                }}
              >
                I agree to the{' '}
                <Link href="/terms" style={{ color: colors.secondary, textDecoration: 'none' }}>
                  Terms of Service
                </Link>{' '}
                and{' '}
                <Link href="/privacy" style={{ color: colors.secondary, textDecoration: 'none' }}>
                  Privacy Policy
                </Link>
              </label>
            </div>
            {fieldErrors.terms && (
              <p style={{ fontSize: '13px', color: colors.error, marginTop: '-16px', marginBottom: '16px' }}>
                {fieldErrors.terms}
              </p>
            )}

            {/* Submit button */}
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
                if (!isLoading) {
                  e.currentTarget.style.backgroundColor = colors.primaryHover
                }
              }}
              onMouseLeave={(e) => {
                if (!isLoading) {
                  e.currentTarget.style.backgroundColor = colors.primary
                }
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
                  Creating account...
                </>
              ) : (
                'Create account'
              )}
            </button>
          </form>

          {/* Sign in link */}
          <p
            style={{
              textAlign: 'center',
              marginTop: '24px',
              fontSize: '14px',
              color: colors.textMuted,
            }}
          >
            Already have an account?{' '}
            <Link
              href="/login"
              style={{
                color: colors.secondary,
                fontWeight: 500,
                textDecoration: 'none',
              }}
            >
              Sign in
            </Link>
          </p>
        </div>
      </main>

      {/* Footer */}
      <footer
        style={{
          padding: '24px 32px',
          textAlign: 'center',
          color: colors.textMuted,
          fontSize: '13px',
        }}
      >
        <p>&copy; 2024 2nd Brain. All rights reserved.</p>
      </footer>

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
