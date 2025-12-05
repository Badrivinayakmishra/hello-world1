'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter, usePathname } from 'next/navigation'

const API_URL = 'http://localhost:5003'

interface User {
  email: string
  name: string
  tenant: string
  data_dir: string
}

interface AuthContextType {
  user: User | null
  token: string | null
  tenant: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
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
      const isLoginPage = pathname === '/login'

      if (!user && !isLoginPage) {
        // Not authenticated and not on login page -> redirect to login
        router.push('/login')
      } else if (user && isLoginPage) {
        // Authenticated but on login page -> redirect to home
        router.push('/')
      }
    }
  }, [user, isLoading, pathname, router])

  const checkAuth = async () => {
    const storedToken = localStorage.getItem('authToken')
    const storedUser = localStorage.getItem('user')

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
        setToken(storedToken)
      } else {
        // Token invalid, clear storage
        localStorage.removeItem('authToken')
        localStorage.removeItem('user')
        localStorage.removeItem('tenant')
      }
    } catch (err) {
      console.error('Auth check failed:', err)
      // Keep stored data if server is down (offline mode)
      try {
        setUser(JSON.parse(storedUser))
        setToken(storedToken)
      } catch {
        localStorage.removeItem('authToken')
        localStorage.removeItem('user')
        localStorage.removeItem('tenant')
      }
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
      })

      const data = await response.json()

      if (data.success) {
        setUser(data.user)
        setToken(data.token)
        localStorage.setItem('authToken', data.token)
        localStorage.setItem('user', JSON.stringify(data.user))
        localStorage.setItem('tenant', data.user.tenant)
        return { success: true }
      } else {
        return { success: false, error: data.error || 'Login failed' }
      }
    } catch (err) {
      console.error('Login error:', err)
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
      setToken(null)
      localStorage.removeItem('authToken')
      localStorage.removeItem('user')
      localStorage.removeItem('tenant')
      router.push('/login')
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        tenant: user?.tenant || null,
        isLoading,
        isAuthenticated: !!user,
        login,
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
    'X-Tenant': tenant || '',
    'Content-Type': 'application/json'
  }
}
