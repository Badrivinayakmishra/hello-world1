"""
CSRF Protection Middleware
Double-submit cookie pattern for state-changing requests.
"""

import secrets
import hashlib
from typing import Optional
from functools import wraps
from flask import request, jsonify, g, make_response
from datetime import datetime, timedelta


# CSRF Configuration
CSRF_TOKEN_LENGTH = 32  # bytes
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_EXPIRY = 3600  # 1 hour in seconds

# Methods that require CSRF protection
PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths that don't require CSRF (e.g., login, signup - they get a new token)
CSRF_EXEMPT_PATHS = {
    "/api/auth/login",
    "/api/auth/signup",
    "/api/auth/refresh",
    "/api/auth/csrf-token",
    "/api/auth/forgot-password",  # Needs to work without existing session
}


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def hash_token(token: str) -> str:
    """Hash a CSRF token for comparison."""
    return hashlib.sha256(token.encode()).hexdigest()


def set_csrf_cookie(response, token: str, secure: bool = False):
    """
    Set CSRF token in a cookie.

    Args:
        response: Flask response object
        token: The CSRF token
        secure: Whether to set Secure flag (True in production)
    """
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=False,  # Must be readable by JavaScript
        secure=secure,
        samesite='Lax',  # Prevents CSRF from external sites
        max_age=CSRF_TOKEN_EXPIRY,
        path='/'
    )
    return response


def get_csrf_from_request() -> Optional[str]:
    """
    Extract CSRF token from request.
    Checks header first, then form data.
    """
    # Check header first (preferred method)
    token = request.headers.get(CSRF_HEADER_NAME)
    if token:
        return token

    # Check form data
    token = request.form.get('csrf_token')
    if token:
        return token

    # Check JSON body
    if request.is_json:
        data = request.get_json(silent=True)
        if data and isinstance(data, dict):
            token = data.get('csrf_token')
            if token:
                return token

    return None


def get_csrf_from_cookie() -> Optional[str]:
    """Extract CSRF token from cookie."""
    return request.cookies.get(CSRF_COOKIE_NAME)


def validate_csrf_token(request_token: str, cookie_token: str) -> bool:
    """
    Validate CSRF token using double-submit pattern.
    Compares the token from request (header/body) with cookie token.
    """
    if not request_token or not cookie_token:
        return False

    # Use constant-time comparison to prevent timing attacks
    return secrets.compare_digest(request_token, cookie_token)


# ============================================================================
# CSRF MIDDLEWARE DECORATOR
# ============================================================================

def csrf_protect(f):
    """
    Decorator to add CSRF protection to Flask routes.

    Usage:
        @csrf_protect
        @require_auth
        def my_endpoint():
            pass
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Skip CSRF check for non-protected methods
        if request.method not in PROTECTED_METHODS:
            return f(*args, **kwargs)

        # Skip CSRF check for exempt paths
        if request.path in CSRF_EXEMPT_PATHS:
            return f(*args, **kwargs)

        # Get tokens
        request_token = get_csrf_from_request()
        cookie_token = get_csrf_from_cookie()

        # Validate
        if not validate_csrf_token(request_token, cookie_token):
            return jsonify({
                "success": False,
                "error": "Invalid or missing CSRF token",
                "error_code": "CSRF_VALIDATION_FAILED"
            }), 403

        return f(*args, **kwargs)

    return decorated


def csrf_exempt(f):
    """
    Decorator to explicitly exempt a route from CSRF protection.
    Use sparingly and only for endpoints that have other security measures.

    Usage:
        @csrf_exempt
        @csrf_protect  # Will be skipped
        def webhook_endpoint():
            pass
    """
    f._csrf_exempt = True
    return f


# ============================================================================
# CSRF TOKEN ENDPOINT
# ============================================================================

def get_csrf_token_endpoint():
    """
    Flask route handler for /api/auth/csrf-token
    Returns a new CSRF token and sets it in cookie.

    Usage:
        from middleware.csrf import get_csrf_token_endpoint

        @auth_bp.route('/csrf-token', methods=['GET'])
        def csrf_token():
            return get_csrf_token_endpoint()
    """
    token = generate_csrf_token()

    # Determine if we should use secure cookie
    secure = request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https'

    response = make_response(jsonify({
        "success": True,
        "csrf_token": token
    }))

    set_csrf_cookie(response, token, secure=secure)

    return response


# ============================================================================
# RESPONSE HELPER
# ============================================================================

def add_csrf_to_response(response, token: Optional[str] = None):
    """
    Helper to add CSRF token to a response.
    Useful for login/signup to set initial CSRF token.

    Args:
        response: Flask response object
        token: Optional token (generates new one if not provided)
    """
    if token is None:
        token = generate_csrf_token()

    secure = request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https'
    set_csrf_cookie(response, token, secure=secure)

    return response, token


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
# Example 1: Protect a route
@app.route('/api/documents', methods=['POST'])
@csrf_protect
@require_auth
def create_document():
    return {"created": True}


# Example 2: Add CSRF token to login response
@app.route('/api/auth/login', methods=['POST'])
def login():
    # ... authentication logic ...
    response = make_response(jsonify({"user": user_data}))
    response, _ = add_csrf_to_response(response)
    return response


# Example 3: Get CSRF token endpoint
@auth_bp.route('/csrf-token', methods=['GET'])
def csrf_token():
    return get_csrf_token_endpoint()


# Frontend usage:
# 1. Call GET /api/auth/csrf-token to get token
# 2. Include X-CSRF-Token header in all POST/PUT/PATCH/DELETE requests
# 3. Token is also set in cookie, so backend can validate both match
"""
