'use client'

import React, { useState, useEffect, Suspense } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { validatePassword, validatePasswordMatch, getPasswordStrength } from '@/utils/validation'
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

function ResetPasswordContent() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [isValidToken, setIsValidToken] = useState<boolean | null>(null)

  const passwordStrength = getPasswordStrength(password)

  // Verify token on mount
  useEffect(() => {
    if (!token) {
      setIsValidToken(false)
      return
    }

    authApi
      .verifyResetToken(token)
      .then((data: any) => {
        setIsValidToken(data.valid === true)
      })
      .catch(() => {
        setIsValidToken(false)
      })
  }, [token])

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()

    // Validate
    const errors: Record<string, string> = {}

    const passwordResult = validatePassword(password)
    if (!passwordResult.isValid && passwordResult.error) {
      errors.password = passwordResult.error
    }

    const matchResult = validatePasswordMatch(password, confirmPassword)
    if (!matchResult.isValid && matchResult.error) {
      errors.confirmPassword = matchResult.error
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }

    setFieldErrors({})
    setError('')
    setIsLoading(true)

    try {
      const result: any = await authApi.resetPassword(token!, password)

      if (result.success) {
        setIsSuccess(true)
      } else {
        setError(result.error || 'Failed to reset password. Please try again.')
      }
    } catch (err: any) {
      setError(err.message || 'Failed to reset password. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  // Loading state while checking token
  if (isValidToken === null) {
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

  // Invalid or expired token
  if (!isValidToken) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: colors.background,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
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
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: colors.errorBg,
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
                stroke={colors.error}
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
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
              Invalid or expired link
            </h1>
            <p
              style={{
                fontSize: '15px',
                color: colors.textMuted,
                marginBottom: '24px',
              }}
            >
              This password reset link is invalid or has expired. Please request a new one.
            </p>

            <Link
              href="/forgot-password"
              style={{
                display: 'inline-block',
                padding: '12px 24px',
                backgroundColor: colors.primary,
                color: '#fff',
                borderRadius: '8px',
                fontSize: '15px',
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              Request new link
            </Link>
          </div>
        </main>
      </div>
    )
  }

  // Success state
  if (isSuccess) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: colors.background,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
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
              Password reset successful!
            </h1>
            <p
              style={{
                fontSize: '15px',
                color: colors.textMuted,
                marginBottom: '24px',
              }}
            >
              Your password has been reset. You can now sign in with your new password.
            </p>

            <Link
              href="/login"
              style={{
                display: 'inline-block',
                padding: '12px 24px',
                backgroundColor: colors.primary,
                color: '#fff',
                borderRadius: '8px',
                fontSize: '15px',
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              Sign in
            </Link>
          </div>
        </main>
      </div>
    )
  }

  // Reset form
  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: colors.background,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
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
          <h1
            style={{
              fontSize: '28px',
              fontWeight: 700,
              color: colors.text,
              marginBottom: '8px',
              textAlign: 'center',
            }}
          >
            Set new password
          </h1>
          <p
            style={{
              fontSize: '15px',
              color: colors.textMuted,
              marginBottom: '32px',
              textAlign: 'center',
            }}
          >
            Create a strong password for your account
          </p>

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

          <form onSubmit={handleSubmit}>
            {/* New Password */}
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
                New password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    setFieldErrors((prev) => ({ ...prev, password: '' }))
                  }}
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
                        transition: 'width 0.3s',
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
                Confirm new password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value)
                    setFieldErrors((prev) => ({ ...prev, confirmPassword: '' }))
                  }}
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
                  Resetting password...
                </>
              ) : (
                'Reset password'
              )}
            </button>
          </form>
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

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div
          style={{
            minHeight: '100vh',
            backgroundColor: '#f8fafc',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              width: '40px',
              height: '40px',
              border: '3px solid #e2e8f0',
              borderTopColor: '#1e3a5f',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }}
          />
        </div>
      }
    >
      <ResetPasswordContent />
    </Suspense>
  )
}
