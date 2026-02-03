/**
 * Session Manager
 * Handles token storage, session lifecycle, inactivity timeout, and auto-refresh.
 * Based on catalyst-research-match implementation.
 */

// Configuration
const SESSION_CONFIG = {
  INACTIVITY_TIMEOUT: 30 * 60 * 1000, // 30 minutes
  WARNING_BEFORE_TIMEOUT: 2 * 60 * 1000, // 2 minutes before timeout (28 min)
  REFRESH_INTERVAL: 25 * 60 * 1000, // Refresh at 25 minutes
  STORAGE_KEYS: {
    ACCESS_TOKEN: 'accessToken',
    REFRESH_TOKEN: 'refreshToken',
    USER_ID: 'userId',
    USER_EMAIL: 'userEmail',
    USER_TYPE: 'userType',
    USER_NAME: 'userName',
    TENANT_ID: 'tenantId',
    SESSION_START: 'sessionStart',
  },
};

// Activity events to track
const ACTIVITY_EVENTS = ['mousedown', 'keydown', 'scroll', 'touchstart', 'click'];

// Callback types
type SessionCallback = () => void;
type WarningCallback = (timeRemaining: number) => void;

class SessionManager {
  private static instance: SessionManager;
  private inactivityTimer: NodeJS.Timeout | null = null;
  private refreshTimer: NodeJS.Timeout | null = null;
  private warningTimer: NodeJS.Timeout | null = null;
  private onSessionExpiredCallback: SessionCallback | null = null;
  private onSessionWarningCallback: WarningCallback | null = null;
  private activityListenersAttached = false;

  private constructor() {
    // Private constructor for singleton
  }

  static getInstance(): SessionManager {
    if (!SessionManager.instance) {
      SessionManager.instance = new SessionManager();
    }
    return SessionManager.instance;
  }

  /**
   * Initialize a new session with tokens and user data
   */
  initializeSession(
    accessToken: string,
    refreshToken: string,
    userData: {
      userId: string;
      userEmail: string;
      userName: string;
      userType?: string;
      tenantId: string;
    }
  ): void {
    // Store tokens
    localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.ACCESS_TOKEN, accessToken);
    localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.REFRESH_TOKEN, refreshToken);

    // Store user data
    localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.USER_ID, userData.userId);
    localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.USER_EMAIL, userData.userEmail);
    localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.USER_NAME, userData.userName);
    localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.TENANT_ID, userData.tenantId);

    if (userData.userType) {
      localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.USER_TYPE, userData.userType);
    }

    // Mark session start time
    localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.SESSION_START, Date.now().toString());

    // Start timers
    this.startTimers();

    // Attach activity listeners
    this.attachActivityListeners();
  }

  /**
   * Start all session timers
   */
  private startTimers(): void {
    this.resetInactivityTimer();
    this.startRefreshTimer();
  }

  /**
   * Reset the inactivity timer (called on user activity)
   */
  private resetInactivityTimer(): void {
    // Clear existing timers
    if (this.inactivityTimer) {
      clearTimeout(this.inactivityTimer);
    }
    if (this.warningTimer) {
      clearTimeout(this.warningTimer);
    }

    // Set warning timer (fires 2 min before timeout)
    const warningTime = SESSION_CONFIG.INACTIVITY_TIMEOUT - SESSION_CONFIG.WARNING_BEFORE_TIMEOUT;
    this.warningTimer = setTimeout(() => {
      if (this.onSessionWarningCallback) {
        this.onSessionWarningCallback(SESSION_CONFIG.WARNING_BEFORE_TIMEOUT);
      }
    }, warningTime);

    // Set inactivity timer
    this.inactivityTimer = setTimeout(() => {
      this.handleSessionExpired();
    }, SESSION_CONFIG.INACTIVITY_TIMEOUT);
  }

  /**
   * Start the token refresh timer
   */
  private startRefreshTimer(): void {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
    }

    this.refreshTimer = setInterval(async () => {
      await this.refreshAccessToken();
    }, SESSION_CONFIG.REFRESH_INTERVAL);
  }

  /**
   * Refresh the access token using the refresh token
   */
  async refreshAccessToken(): Promise<boolean> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      console.log('[SessionManager] No refresh token available');
      return false;
    }

    try {
      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Include cookies
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        console.error('[SessionManager] Token refresh failed');
        this.handleSessionExpired();
        return false;
      }

      const data = await response.json();

      if (data.success && data.tokens) {
        // Update stored tokens
        localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.ACCESS_TOKEN, data.tokens.access_token);
        if (data.tokens.refresh_token) {
          localStorage.setItem(SESSION_CONFIG.STORAGE_KEYS.REFRESH_TOKEN, data.tokens.refresh_token);
        }
        console.log('[SessionManager] Token refreshed successfully');
        return true;
      }

      return false;
    } catch (error) {
      console.error('[SessionManager] Token refresh error:', error);
      return false;
    }
  }

  /**
   * Handle session expiration
   */
  private handleSessionExpired(): void {
    console.log('[SessionManager] Session expired');
    this.clearSession();

    if (this.onSessionExpiredCallback) {
      this.onSessionExpiredCallback();
    }
  }

  /**
   * Clear all session data and timers
   */
  clearSession(): void {
    // Clear timers
    if (this.inactivityTimer) {
      clearTimeout(this.inactivityTimer);
      this.inactivityTimer = null;
    }
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
    if (this.warningTimer) {
      clearTimeout(this.warningTimer);
      this.warningTimer = null;
    }

    // Remove activity listeners
    this.detachActivityListeners();

    // Clear storage
    Object.values(SESSION_CONFIG.STORAGE_KEYS).forEach((key) => {
      localStorage.removeItem(key);
    });
  }

  /**
   * Logout and clear session
   */
  async logout(): Promise<void> {
    try {
      const accessToken = this.getAccessToken();

      // Call logout API
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        credentials: 'include',
      });
    } catch (error) {
      console.error('[SessionManager] Logout API error:', error);
    }

    this.clearSession();
  }

  /**
   * Attach activity listeners to reset inactivity timer
   */
  private attachActivityListeners(): void {
    if (this.activityListenersAttached || typeof window === 'undefined') {
      return;
    }

    ACTIVITY_EVENTS.forEach((event) => {
      window.addEventListener(event, this.handleActivity);
    });

    this.activityListenersAttached = true;
  }

  /**
   * Detach activity listeners
   */
  private detachActivityListeners(): void {
    if (!this.activityListenersAttached || typeof window === 'undefined') {
      return;
    }

    ACTIVITY_EVENTS.forEach((event) => {
      window.removeEventListener(event, this.handleActivity);
    });

    this.activityListenersAttached = false;
  }

  /**
   * Handle user activity
   */
  private handleActivity = (): void => {
    this.resetInactivityTimer();
  };

  /**
   * Extend session (reset inactivity timer)
   */
  extendSession(): void {
    this.resetInactivityTimer();
  }

  // ========================================
  // GETTERS
  // ========================================

  getAccessToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(SESSION_CONFIG.STORAGE_KEYS.ACCESS_TOKEN);
  }

  getRefreshToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(SESSION_CONFIG.STORAGE_KEYS.REFRESH_TOKEN);
  }

  getUserId(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(SESSION_CONFIG.STORAGE_KEYS.USER_ID);
  }

  getUserEmail(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(SESSION_CONFIG.STORAGE_KEYS.USER_EMAIL);
  }

  getUserName(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(SESSION_CONFIG.STORAGE_KEYS.USER_NAME);
  }

  getUserType(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(SESSION_CONFIG.STORAGE_KEYS.USER_TYPE);
  }

  getTenantId(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(SESSION_CONFIG.STORAGE_KEYS.TENANT_ID);
  }

  isLoggedIn(): boolean {
    return !!this.getAccessToken() && !!this.getUserId();
  }

  /**
   * Get time remaining before timeout (in milliseconds)
   */
  getTimeRemaining(): number {
    const sessionStart = localStorage.getItem(SESSION_CONFIG.STORAGE_KEYS.SESSION_START);
    if (!sessionStart) return 0;

    const elapsed = Date.now() - parseInt(sessionStart, 10);
    const remaining = SESSION_CONFIG.INACTIVITY_TIMEOUT - elapsed;
    return Math.max(0, remaining);
  }

  /**
   * Get formatted time remaining (e.g., "5:30")
   */
  getTimeRemainingFormatted(): string {
    const remaining = this.getTimeRemaining();
    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }

  // ========================================
  // CALLBACKS
  // ========================================

  setOnSessionExpired(callback: SessionCallback): void {
    this.onSessionExpiredCallback = callback;
  }

  setOnSessionWarning(callback: WarningCallback): void {
    this.onSessionWarningCallback = callback;
  }
}

// Export singleton instance
export const sessionManager = SessionManager.getInstance();
export default sessionManager;
