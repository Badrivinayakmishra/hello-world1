'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import { useAuth } from '@/contexts/AuthContext'

type AuthMode = 'login' | 'signup'

export default function Login() {
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [organizationName, setOrganizationName] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { login, signup, isLoading: authLoading } = useAuth()

  const handleSubmit = async () => {
    if (!email || !password) {
      setError('Please enter both email and password')
      return
    }

    if (mode === 'signup' && !fullName) {
      setError('Please enter your full name')
      return
    }

    setIsLoading(true)
    setError('')

    let result
    if (mode === 'login') {
      result = await login(email, password)
    } else {
      result = await signup(email, password, fullName, organizationName || undefined)
    }

    if (!result.success) {
      setError(result.error || `${mode === 'login' ? 'Login' : 'Signup'} failed`)
    }
    // If successful, AuthContext will handle redirect

    setIsLoading(false)
  }

  const toggleMode = () => {
    setMode(mode === 'login' ? 'signup' : 'login')
    setError('')
    // Clear form when switching modes
    if (mode === 'login') {
      setFullName('')
      setOrganizationName('')
    }
  }

  // Show loading while checking existing auth
  if (authLoading) {
    return (
      <div
        style={{
          width: '100vw',
          height: '100vh',
          backgroundColor: '#FFF3E4',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '32px',
            height: '32px',
            border: '2px solid #e5e7eb',
            borderTopColor: '#27266A',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 16px'
          }}></div>
          <p style={{ color: '#6b7280' }}>Loading...</p>
        </div>
      </div>
    )
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit()
    }
  }

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        backgroundColor: '#FFF3E4',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center'
      }}
    >
      {/* Logo at top left */}
      <div
        style={{
          position: 'absolute',
          top: '32px',
          left: '32px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}
      >
        <div style={{ width: '41px', height: '51px', aspectRatio: '41/51' }}>
          <Image
            src="/owl.png"
            alt="2nd Brain Logo"
            width={41}
            height={51}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        </div>
        <h1
          style={{
            color: '#081028',
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '20px',
            fontWeight: 600,
            lineHeight: '22px'
          }}
        >
          2nd Brain
        </h1>
      </div>

      {/* Main content - Auth Card */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '20px',
          backgroundColor: '#FFE2BF',
          padding: '48px',
          borderRadius: '16px',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)',
          minWidth: '420px',
          maxWidth: '480px'
        }}
      >
        <h2
          style={{
            color: '#081028',
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '28px',
            fontWeight: 600,
            marginBottom: '4px'
          }}
        >
          {mode === 'login' ? 'Welcome Back' : 'Create Account'}
        </h2>

        <p
          style={{
            color: '#7E89AC',
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '14px',
            marginBottom: '8px',
            textAlign: 'center'
          }}
        >
          {mode === 'login'
            ? 'Sign in to access your knowledge base'
            : 'Start capturing your organizational knowledge'}
        </p>

        {/* Error message */}
        {error && (
          <div
            style={{
              width: '100%',
              padding: '12px 16px',
              backgroundColor: '#fee2e2',
              borderRadius: '8px',
              color: '#dc2626',
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '14px',
              textAlign: 'center'
            }}
          >
            {error}
          </div>
        )}

        {/* Full Name input (signup only) */}
        {mode === 'signup' && (
          <div style={{ width: '100%' }}>
            <label
              style={{
                display: 'block',
                color: '#081028',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                marginBottom: '8px'
              }}
            >
              Full Name
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="John Doe"
              style={{
                width: '100%',
                height: '50px',
                padding: '0 16px',
                borderRadius: '8px',
                border: '1px solid #7E89AC',
                backgroundColor: '#FFF3E4',
                fontSize: '16px',
                fontFamily: '"Work Sans", sans-serif',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>
        )}

        {/* Email input */}
        <div style={{ width: '100%' }}>
          <label
            style={{
              display: 'block',
              color: '#081028',
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '14px',
              fontWeight: 500,
              marginBottom: '8px'
            }}
          >
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="your.email@company.com"
            style={{
              width: '100%',
              height: '50px',
              padding: '0 16px',
              borderRadius: '8px',
              border: '1px solid #7E89AC',
              backgroundColor: '#FFF3E4',
              fontSize: '16px',
              fontFamily: '"Work Sans", sans-serif',
              outline: 'none',
              boxSizing: 'border-box'
            }}
          />
        </div>

        {/* Password input */}
        <div style={{ width: '100%' }}>
          <label
            style={{
              display: 'block',
              color: '#081028',
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '14px',
              fontWeight: 500,
              marginBottom: '8px'
            }}
          >
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={mode === 'signup' ? 'Min 8 chars, uppercase, lowercase, digit' : 'Enter your password'}
            style={{
              width: '100%',
              height: '50px',
              padding: '0 16px',
              borderRadius: '8px',
              border: '1px solid #7E89AC',
              backgroundColor: '#FFF3E4',
              fontSize: '16px',
              fontFamily: '"Work Sans", sans-serif',
              outline: 'none',
              boxSizing: 'border-box'
            }}
          />
        </div>

        {/* Organization Name input (signup only) */}
        {mode === 'signup' && (
          <div style={{ width: '100%' }}>
            <label
              style={{
                display: 'block',
                color: '#081028',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                marginBottom: '8px'
              }}
            >
              Organization Name <span style={{ color: '#7E89AC', fontWeight: 400 }}>(optional)</span>
            </label>
            <input
              type="text"
              value={organizationName}
              onChange={(e) => setOrganizationName(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Acme Research Lab"
              style={{
                width: '100%',
                height: '50px',
                padding: '0 16px',
                borderRadius: '8px',
                border: '1px solid #7E89AC',
                backgroundColor: '#FFF3E4',
                fontSize: '16px',
                fontFamily: '"Work Sans", sans-serif',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>
        )}

        {/* Submit button */}
        <button
          onClick={handleSubmit}
          disabled={isLoading}
          style={{
            width: '100%',
            height: '50px',
            borderRadius: '8px',
            border: 'none',
            backgroundColor: isLoading ? '#9ca3af' : '#27266A',
            color: '#ffffff',
            fontSize: '16px',
            fontWeight: 600,
            fontFamily: '"Work Sans", sans-serif',
            cursor: isLoading ? 'not-allowed' : 'pointer',
            marginTop: '8px',
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            if (!isLoading) {
              e.currentTarget.style.backgroundColor = '#1e1b4b'
            }
          }}
          onMouseLeave={(e) => {
            if (!isLoading) {
              e.currentTarget.style.backgroundColor = '#27266A'
            }
          }}
        >
          {isLoading
            ? (mode === 'login' ? 'Signing in...' : 'Creating account...')
            : (mode === 'login' ? 'Sign In' : 'Create Account')}
        </button>

        {/* Toggle mode link */}
        <div
          style={{
            marginTop: '8px',
            textAlign: 'center'
          }}
        >
          <p
            style={{
              color: '#7E89AC',
              fontFamily: '"Work Sans", sans-serif',
              fontSize: '14px'
            }}
          >
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              onClick={toggleMode}
              style={{
                background: 'none',
                border: 'none',
                color: '#27266A',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
                textDecoration: 'underline'
              }}
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>

        {/* Info box for new users */}
        {mode === 'signup' && (
          <div
            style={{
              marginTop: '8px',
              padding: '16px',
              backgroundColor: 'rgba(39, 38, 106, 0.1)',
              borderRadius: '8px',
              width: '100%'
            }}
          >
            <p
              style={{
                color: '#27266A',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '12px',
                fontWeight: 600,
                marginBottom: '8px'
              }}
            >
              What happens next:
            </p>
            <ul
              style={{
                color: '#081028',
                fontFamily: '"Work Sans", sans-serif',
                fontSize: '11px',
                margin: 0,
                paddingLeft: '16px'
              }}
            >
              <li style={{ marginBottom: '4px' }}>Connect your Gmail, Slack, or Box</li>
              <li style={{ marginBottom: '4px' }}>We'll import your documents</li>
              <li style={{ marginBottom: '4px' }}>Review which items are work-related</li>
              <li>Start asking questions to your AI knowledge base</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
