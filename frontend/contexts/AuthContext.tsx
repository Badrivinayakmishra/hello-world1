'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter, usePathname } from 'next/navigation'

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

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  // Check auth on mount
  useEffect(() => {
    checkAuth()
  }, [])

  // Redirect based on auth state
  useEffect(() => {
    if (!isLoading) {
      const isAuthPage = pathname === '/login' || pathname === '/signup'

      if (!user && !isAuthPage) {
        // Not authenticated and not on auth page -> redirect to login
        router.push('/login')
      } else if (user && isAuthPage) {
        // Authenticated but on auth page -> redirect to home
        router.push('/')
      }
    }
  }, [user, isLoading, pathname, router])

  const checkAuth = async () => {
    const storedToken = localStorage.getItem('authToken')
    const storedUser = localStorage.getItem('user')
    const storedTenant = localStorage.getItem('tenant')

    if (!storedToken || !storedUser) {
      setIsLoading(false)
      return
    }

    try {
      // Verify token with backend
      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${storedToken}`
        }
      })

      const data = await response.json()

      if (data.success) {
        setUser(data.user)
        setTenant(data.tenant)
        setToken(storedToken)
      } else {
        // Token invalid, clear storage
        clearStorage()
      }
    } catch (err) {
      console.error('Auth check failed:', err)
      // Keep stored data if server is down (offline mode)
      try {
        setUser(JSON.parse(storedUser))
        if (storedTenant) setTenant(JSON.parse(storedTenant))
        setToken(storedToken)
      } catch {
        clearStorage()
      }
    } finally {
      setIsLoading(false)
    }
  }

  const clearStorage = () => {
    localStorage.removeItem('authToken')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('user')
    localStorage.removeItem('tenant')
  }

  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
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

        localStorage.setItem('authToken', accessToken)
        if (refreshTok) localStorage.setItem('refreshToken', refreshTok)
        localStorage.setItem('user', JSON.stringify(data.user))
        if (data.tenant) localStorage.setItem('tenant', JSON.stringify(data.tenant))

        return { success: true }
      } else {
        return { success: false, error: data.error || 'Login failed' }
      }
    } catch (err) {
      console.error('Login error:', err)
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

        localStorage.setItem('authToken', accessToken)
        if (refreshTok) localStorage.setItem('refreshToken', refreshTok)
        localStorage.setItem('user', JSON.stringify(data.user))
        if (data.tenant) localStorage.setItem('tenant', JSON.stringify(data.tenant))

        return { success: true }
      } else {
        return { success: false, error: data.error || 'Signup failed' }
      }
    } catch (err) {
      console.error('Signup error:', err)
      return { success: false, error: 'Unable to connect to server' }
    }
  }

  const logout = async () => {
    try {
      if (token) {
        await fetch(`${API_URL}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
      }
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      setUser(null)
      setTenant(null)
      setToken(null)
      setRefreshToken(null)
      clearStorage()
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
  const { token, tenant } = useAuth()

  return {
    'Authorization': token ? `Bearer ${token}` : '',
    'X-Tenant': tenant?.id || '',
    'Content-Type': 'application/json'
  }
}
