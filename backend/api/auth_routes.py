"""
Authentication API Routes
REST endpoints for user authentication, registration, and session management.
"""

from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import Session

from database.models import SessionLocal, User, Tenant
from services.auth_service import (
    AuthService, SignupData,
    get_token_from_header, require_auth, JWTUtils
)


# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def get_db():
    """Get database session"""
    return SessionLocal()


def get_client_info():
    """Get client IP and user agent from request"""
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', '')[:500]
    return ip, user_agent


# ============================================================================
# SIGNUP
# ============================================================================

@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    Register a new user and organization.

    Request body:
    {
        "email": "user@example.com",
        "password": "SecurePassword123",
        "full_name": "John Doe",
        "organization_name": "Acme Corp" (optional)
    }

    Response:
    {
        "success": true,
        "user": { ... },
        "tokens": {
            "access_token": "...",
            "refresh_token": "...",
            "token_type": "Bearer",
            "expires_in": 604800
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        # Validate required fields
        required_fields = ['email', 'password', 'full_name']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400

        ip, user_agent = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)

            signup_data = SignupData(
                email=data['email'],
                password=data['password'],
                full_name=data['full_name'],
                organization_name=data.get('organization_name'),
                invite_code=data.get('invite_code')
            )

            result = auth_service.signup(signup_data, ip, user_agent)

            if not result.success:
                return jsonify({
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code
                }), 400

            return jsonify({
                "success": True,
                "user": result.user.to_dict(),
                "tenant": result.user.tenant.to_dict(),
                "tokens": {
                    "access_token": result.tokens.access_token,
                    "refresh_token": result.tokens.refresh_token,
                    "token_type": result.tokens.token_type,
                    "expires_in": 604800  # 7 days in seconds
                }
            }), 201

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Signup failed: {str(e)}"
        }), 500


# ============================================================================
# LOGIN
# ============================================================================

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user with email and password.

    Request body:
    {
        "email": "user@example.com",
        "password": "SecurePassword123"
    }

    Response:
    {
        "success": true,
        "user": { ... },
        "tokens": { ... }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({
                "success": False,
                "error": "Email and password are required"
            }), 400

        ip, user_agent = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            result = auth_service.login(email, password, ip, user_agent)

            if not result.success:
                status_code = 401
                if result.error_code == "ACCOUNT_LOCKED":
                    status_code = 423
                elif result.error_code == "TENANT_INACTIVE":
                    status_code = 403

                return jsonify({
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code
                }), status_code

            return jsonify({
                "success": True,
                "user": result.user.to_dict(),
                "tenant": result.user.tenant.to_dict(),
                "tokens": {
                    "access_token": result.tokens.access_token,
                    "refresh_token": result.tokens.refresh_token,
                    "token_type": result.tokens.token_type,
                    "expires_in": 604800
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Login failed: {str(e)}"
        }), 500


# ============================================================================
# REFRESH TOKEN
# ============================================================================

@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    Refresh access token using refresh token.

    Request body:
    {
        "refresh_token": "..."
    }

    Response:
    {
        "success": true,
        "tokens": { ... }
    }
    """
    try:
        data = request.get_json()

        if not data or not data.get('refresh_token'):
            return jsonify({
                "success": False,
                "error": "Refresh token is required"
            }), 400

        ip, user_agent = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            result = auth_service.refresh_tokens(
                data['refresh_token'],
                ip,
                user_agent
            )

            if not result.success:
                return jsonify({
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code
                }), 401

            return jsonify({
                "success": True,
                "tokens": {
                    "access_token": result.tokens.access_token,
                    "refresh_token": result.tokens.refresh_token,
                    "token_type": result.tokens.token_type,
                    "expires_in": 604800
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Token refresh failed: {str(e)}"
        }), 500


# ============================================================================
# LOGOUT
# ============================================================================

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Logout current session.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true
    }
    """
    try:
        token = get_token_from_header(request.headers.get("Authorization", ""))

        if not token:
            return jsonify({"success": True})

        ip, _ = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            auth_service.logout(token, ip)
            return jsonify({"success": True})
        finally:
            db.close()

    except Exception:
        return jsonify({"success": True})


@auth_bp.route('/logout-all', methods=['POST'])
@require_auth
def logout_all():
    """
    Logout all sessions except current one.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true,
        "sessions_revoked": 3
    }
    """
    try:
        token = get_token_from_header(request.headers.get("Authorization", ""))
        payload, _ = JWTUtils.decode_access_token(token)
        current_jti = payload.get("jti") if payload else None

        ip, _ = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            count = auth_service.logout_all_sessions(
                g.user_id,
                except_current_jti=current_jti,
                ip_address=ip
            )
            return jsonify({
                "success": True,
                "sessions_revoked": count
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# CURRENT USER
# ============================================================================

@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    Get current authenticated user info.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true,
        "user": { ... },
        "tenant": { ... }
    }
    """
    try:
        db = get_db()
        try:
            user = db.query(User).filter(User.id == g.user_id).first()

            if not user:
                return jsonify({
                    "success": False,
                    "error": "User not found"
                }), 404

            return jsonify({
                "success": True,
                "user": user.to_dict(),
                "tenant": user.tenant.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# CHANGE PASSWORD
# ============================================================================

@auth_bp.route('/password', methods=['PUT'])
@require_auth
def change_password():
    """
    Change current user's password.

    Headers:
        Authorization: Bearer <access_token>

    Request body:
    {
        "current_password": "OldPassword123",
        "new_password": "NewPassword456",
        "logout_other_sessions": true (optional, default true)
    }

    Response:
    {
        "success": true
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        current_password = data.get('current_password')
        new_password = data.get('new_password')
        logout_others = data.get('logout_other_sessions', True)

        if not current_password or not new_password:
            return jsonify({
                "success": False,
                "error": "Current password and new password are required"
            }), 400

        ip, _ = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            success, error = auth_service.change_password(
                g.user_id,
                current_password,
                new_password,
                logout_others,
                ip
            )

            if not success:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            return jsonify({"success": True})

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# UPDATE PROFILE
# ============================================================================

@auth_bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile():
    """
    Update current user's profile.

    Headers:
        Authorization: Bearer <access_token>

    Request body:
    {
        "full_name": "John Doe",
        "timezone": "America/Los_Angeles",
        "preferences": { ... }
    }

    Response:
    {
        "success": true,
        "user": { ... }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        db = get_db()
        try:
            user = db.query(User).filter(User.id == g.user_id).first()

            if not user:
                return jsonify({
                    "success": False,
                    "error": "User not found"
                }), 404

            # Update allowed fields
            if 'full_name' in data:
                user.full_name = data['full_name']
            if 'timezone' in data:
                user.timezone = data['timezone']
            if 'preferences' in data and isinstance(data['preferences'], dict):
                user.preferences = {**user.preferences, **data['preferences']}

            db.commit()

            return jsonify({
                "success": True,
                "user": user.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# SESSIONS LIST
# ============================================================================

@auth_bp.route('/sessions', methods=['GET'])
@require_auth
def list_sessions():
    """
    List all active sessions for current user.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true,
        "sessions": [
            {
                "id": "...",
                "device_info": "...",
                "ip_address": "...",
                "created_at": "...",
                "last_used_at": "...",
                "is_current": true
            }
        ]
    }
    """
    try:
        from database.models import UserSession

        # Get current token JTI
        token = get_token_from_header(request.headers.get("Authorization", ""))
        payload, _ = JWTUtils.decode_access_token(token)
        current_jti = payload.get("jti") if payload else None

        db = get_db()
        try:
            sessions = db.query(UserSession).filter(
                UserSession.user_id == g.user_id,
                UserSession.is_revoked == False,
                UserSession.expires_at > db.func.now()
            ).order_by(UserSession.last_used_at.desc()).all()

            session_list = []
            for s in sessions:
                session_list.append({
                    "id": s.id,
                    "device_info": s.device_info,
                    "ip_address": s.ip_address,
                    "location": s.location,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
                    "is_current": s.access_token_jti == current_jti
                })

            return jsonify({
                "success": True,
                "sessions": session_list
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@auth_bp.route('/sessions/<session_id>', methods=['DELETE'])
@require_auth
def revoke_session(session_id):
    """
    Revoke a specific session.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true
    }
    """
    try:
        from database.models import UserSession

        db = get_db()
        try:
            session = db.query(UserSession).filter(
                UserSession.id == session_id,
                UserSession.user_id == g.user_id
            ).first()

            if not session:
                return jsonify({
                    "success": False,
                    "error": "Session not found"
                }), 404

            session.is_revoked = True
            session.revoked_at = db.func.now()
            session.revoked_reason = "user_revoked"

            db.commit()

            return jsonify({"success": True})

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
