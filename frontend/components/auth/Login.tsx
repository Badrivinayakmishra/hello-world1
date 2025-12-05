'use client'

import React, { useState } from 'react'
import Image from 'next/image'
import { useAuth } from '@/contexts/AuthContext'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { login, isLoading: authLoading } = useAuth()

  const handleLogin = async () => {
    if (!email || !password) {
      setError('Please enter both email and password')
      return
    }

    setIsLoading(true)
    setError('')

    const result = await login(email, password)

    if (!result.success) {
      setError(result.error || 'Login failed')
    }
    // If successful, AuthContext will handle redirect

    setIsLoading(false)
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
      handleLogin()
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

      {/* Main content - Login Card */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '24px',
          backgroundColor: '#FFE2BF',
          padding: '48px',
          borderRadius: '16px',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)',
          minWidth: '400px'
        }}
      >
        <h2
          style={{
            color: '#081028',
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '28px',
            fontWeight: 600,
            marginBottom: '8px'
          }}
        >
          Welcome Back
        </h2>

        <p
          style={{
            color: '#7E89AC',
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '14px',
            marginBottom: '16px'
          }}
        >
          Sign in to access your knowledge base
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
            placeholder="Enter your password"
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

        {/* Login button */}
        <button
          onClick={handleLogin}
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
            marginTop: '16px',
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
          {isLoading ? 'Signing in...' : 'Sign In'}
        </button>

        {/* Demo credentials hint */}
        <div
          style={{
            marginTop: '16px',
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
            Demo Accounts:
          </p>
          <p
            style={{
              color: '#081028',
              fontFamily: '"Work Sans", monospace',
              fontSize: '11px',
              marginBottom: '4px'
            }}
          >
            BEAT: rishi2205@ucla.edu / BEAT
          </p>
          <p
            style={{
              color: '#081028',
              fontFamily: '"Work Sans", monospace',
              fontSize: '11px'
            }}
          >
            Enron: rishitjain2205@gmail.com / Enron
          </p>
        </div>
      </div>
    </div>
  )
}
