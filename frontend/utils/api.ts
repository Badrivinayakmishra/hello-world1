/**
 * API Client
 * Handles API requests with automatic token injection and refresh.
 * Based on catalyst-research-match implementation.
 */

import { sessionManager } from './sessionManager';

// API configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5003';

// Request options type
interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

// API response type
interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  error_code?: string;
}

/**
 * Make an API request with automatic token handling
 */
async function apiRequest<T = unknown>(
  endpoint: string,
  options: RequestOptions = {},
  isRetry = false
): Promise<T> {
  const { skipAuth = false, ...fetchOptions } = options;

  // Build URL
  const url = endpoint.startsWith('http')
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  // Build headers
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string>),
  };

  // Add authorization header if not skipping auth
  if (!skipAuth) {
    const token = sessionManager.getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  // Make request
  const response = await fetch(url, {
    ...fetchOptions,
    headers,
    credentials: 'include', // Include cookies for CSRF
  });

  // Handle 401 Unauthorized - try to refresh token
  if (response.status === 401 && !isRetry && !skipAuth) {
    console.log('[API] Received 401, attempting token refresh...');

    const refreshed = await sessionManager.refreshAccessToken();
    if (refreshed) {
      // Retry the original request with new token
      return apiRequest<T>(endpoint, options, true);
    }

    // Refresh failed - session expired
    throw new Error('Session expired. Please log in again.');
  }

  // Parse response
  const data = await response.json();

  // Handle non-success responses
  if (!response.ok) {
    const errorMessage = data.error || data.message || `Request failed with status ${response.status}`;
    const error = new Error(errorMessage) as Error & { code?: string; status?: number };
    error.code = data.error_code;
    error.status = response.status;
    throw error;
  }

  return data;
}

/**
 * API client with convenience methods
 */
export const api = {
  /**
   * GET request
   */
  async get<T = unknown>(endpoint: string, options?: RequestOptions): Promise<T> {
    return apiRequest<T>(endpoint, {
      method: 'GET',
      ...options,
    });
  },

  /**
   * POST request
   */
  async post<T = unknown>(
    endpoint: string,
    data?: Record<string, unknown> | FormData,
    options?: RequestOptions
  ): Promise<T> {
    const isFormData = data instanceof FormData;
    return apiRequest<T>(endpoint, {
      method: 'POST',
      body: isFormData ? data : JSON.stringify(data),
      ...(isFormData ? { headers: {} } : {}),
      ...options,
    });
  },

  /**
   * PUT request
   */
  async put<T = unknown>(
    endpoint: string,
    data?: Record<string, unknown>,
    options?: RequestOptions
  ): Promise<T> {
    return apiRequest<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
      ...options,
    });
  },

  /**
   * PATCH request
   */
  async patch<T = unknown>(
    endpoint: string,
    data?: Record<string, unknown>,
    options?: RequestOptions
  ): Promise<T> {
    return apiRequest<T>(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
      ...options,
    });
  },

  /**
   * DELETE request
   */
  async delete<T = unknown>(endpoint: string, options?: RequestOptions): Promise<T> {
    return apiRequest<T>(endpoint, {
      method: 'DELETE',
      ...options,
    });
  },
};

/**
 * Auth-specific API methods (skip auth header)
 */
export const authApi = {
  /**
   * Login
   */
  async login(email: string, password: string): Promise<ApiResponse> {
    return api.post('/api/auth/login', { email, password }, { skipAuth: true });
  },

  /**
   * Signup
   */
  async signup(
    email: string,
    password: string,
    fullName: string,
    organizationName?: string
  ): Promise<ApiResponse> {
    return api.post(
      '/api/auth/signup',
      {
        email,
        password,
        full_name: fullName,
        organization_name: organizationName,
      },
      { skipAuth: true }
    );
  },

  /**
   * Logout
   */
  async logout(): Promise<ApiResponse> {
    return api.post('/api/auth/logout');
  },

  /**
   * Get current user
   */
  async me(): Promise<ApiResponse> {
    return api.get('/api/auth/me');
  },

  /**
   * Refresh token
   */
  async refresh(refreshToken: string): Promise<ApiResponse> {
    return api.post('/api/auth/refresh', { refresh_token: refreshToken }, { skipAuth: true });
  },

  /**
   * Request password reset
   */
  async forgotPassword(email: string): Promise<ApiResponse> {
    return api.post('/api/auth/forgot-password', { email }, { skipAuth: true });
  },

  /**
   * Verify reset token
   */
  async verifyResetToken(token: string): Promise<ApiResponse> {
    return api.get(`/api/auth/verify-reset-token?token=${encodeURIComponent(token)}`, {
      skipAuth: true,
    });
  },

  /**
   * Reset password
   */
  async resetPassword(token: string, newPassword: string): Promise<ApiResponse> {
    return api.post(
      '/api/auth/reset-password',
      { token, new_password: newPassword },
      { skipAuth: true }
    );
  },

  /**
   * Change password (requires auth)
   */
  async changePassword(currentPassword: string, newPassword: string): Promise<ApiResponse> {
    return api.put('/api/auth/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },

  /**
   * Get CSRF token
   */
  async getCsrfToken(): Promise<ApiResponse> {
    return api.get('/api/auth/csrf-token', { skipAuth: true });
  },
};

export default api;
