'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { sessionManager } from '@/utils/sessionManager'
import { authApi } from '@/utils/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003'

interface User {
  id: string
  email: string
  full_name: string
  role: string
  tenant_id: string
  avatar_url?: string
  email_verified: boolean
  mfa_enabled: boolean
  created_at: string
  is_active: boolean
}

interface Tenant {
  id: string
  name: string
  slug: string
  plan: string
  storage_used_bytes: number
  storage_limit_bytes: number
  created_at: string
  is_active: boolean
}

interface AuthContextType {
  user: User | null
  tenant: Tenant | null
  token: string | null
  refreshToken: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>
  signup: (email: string, password: string, fullName: string, organizationName?: string) => Promise<{ success: boolean; error?: string }>
  logout: () => Promise<void>
}

// Public routes that don't require authentication
const PUBLIC_ROUTES = ['/login', '/signup', '/forgot-password', '/reset-password']

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  // Handle session expiration
  const handleSessionExpired = useCallback(() => {
    console.log('[Auth] Session expired')
    setUser(null)
    setTenant(null)
    setToken(null)
    setRefreshToken(null)
    router.push('/login')
  }, [router])

  // Check auth on mount
  useEffect(() => {
    // Set up session expiration handler
    sessionManager.setOnSessionExpired(handleSessionExpired)

    // Optional: Set up session warning handler
    sessionManager.setOnSessionWarning((timeRemaining) => {
      console.log(`[Auth] Session expiring in ${Math.round(timeRemaining / 1000)} seconds`)
    })

    checkAuth()
  }, [handleSessionExpired])

  // Redirect based on auth state
  useEffect(() => {
    if (!isLoading) {
      const isPublicRoute = PUBLIC_ROUTES.some(route => pathname?.startsWith(route))

      if (!user && !isPublicRoute) {
        // Not authenticated and not on public page -> redirect to login
        router.push('/login')
      } else if (user && pathname === '/login') {
        // Authenticated but on login page -> redirect to documents
        router.push('/documents')
      }
    }
  }, [user, isLoading, pathname, router])

  const checkAuth = async () => {
    // Check if we have stored auth data
    const storedToken = sessionManager.getAccessToken()
    const storedUserId = sessionManager.getUserId()

    if (!storedToken || !storedUserId) {
      setIsLoading(false)
      return
    }

    try {
      // Verify token with backend
      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${storedToken}`
        },
        credentials: 'include'
      })

      const data = await response.json()

      if (data.success) {
        setUser(data.user)
        setTenant(data.tenant)
        setToken(storedToken)
        setRefreshToken(sessionManager.getRefreshToken())
      } else {
        // Token invalid, clear storage
        sessionManager.clearSession()
      }
    } catch (err) {
      console.error('[Auth] Auth check failed:', err)
      // Keep stored data if server is down (offline mode)
      // But we need to at least set basic state
      setToken(storedToken)
      setRefreshToken(sessionManager.getRefreshToken())
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
        credentials: 'include' // Include cookies
      })

      const data = await response.json()

      if (data.success) {
        // V2 API returns tokens object with access_token
        const accessToken = data.tokens?.access_token || data.token
        const refreshTok = data.tokens?.refresh_token

        setUser(data.user)
        setTenant(data.tenant)
        setToken(accessToken)
        setRefreshToken(refreshTok)

        // Initialize session manager
        sessionManager.initializeSession(accessToken, refreshTok, {
          userId: data.user.id,
          userEmail: data.user.email,
          userName: data.user.full_name,
          userType: data.user.role,
          tenantId: data.user.tenant_id
        })

        // Redirect to documents page
        router.push('/documents')

        return { success: true }
      } else {
        return { success: false, error: data.error || 'Login failed' }
      }
    } catch (err) {
      console.error('[Auth] Login error:', err)
      return { success: false, error: 'Unable to connect to server' }
    }
  }

  const signup = async (
    email: string,
    password: string,
    fullName: string,
    organizationName?: string
  ): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(`${API_URL}/api/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          organization_name: organizationName
        }),
        credentials: 'include'
      })

      const data = await response.json()

      if (data.success) {
        // V2 API returns tokens object with access_token
        const accessToken = data.tokens?.access_token
        const refreshTok = data.tokens?.refresh_token

        setUser(data.user)
        setTenant(data.tenant)
        setToken(accessToken)
        setRefreshToken(refreshTok)

        // Initialize session manager
        sessionManager.initializeSession(accessToken, refreshTok, {
          userId: data.user.id,
          userEmail: data.user.email,
          userName: data.user.full_name,
          userType: data.user.role,
          tenantId: data.user.tenant_id
        })

        // Redirect to documents page
        router.push('/documents')

        return { success: true }
      } else {
        return { success: false, error: data.error || 'Signup failed' }
      }
    } catch (err) {
      console.error('[Auth] Signup error:', err)
      return { success: false, error: 'Unable to connect to server' }
    }
  }

  const logout = async () => {
    try {
      await sessionManager.logout()
    } catch (err) {
      console.error('[Auth] Logout error:', err)
    } finally {
      setUser(null)
      setTenant(null)
      setToken(null)
      setRefreshToken(null)
      router.push('/login')
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        tenant,
        token,
        refreshToken,
        isLoading,
        isAuthenticated: !!user,
        login,
        signup,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// Hook to get auth headers for API calls
export function useAuthHeaders() {
  const { token } = useAuth()

  return {
    'Authorization': token ? `Bearer ${token}` : '',
    'Content-Type': 'application/json'
  }
}
