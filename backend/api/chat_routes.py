"""
Chat History API Routes
REST endpoints for managing chat conversations and messages.
Provides tenant-isolated chat history persistence.
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
from collections import defaultdict
import time
from functools import wraps
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from database.models import (
    SessionLocal, ChatConversation, ChatMessage, User
)
from services.auth_service import require_auth


# Create blueprint
chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')

# Constants for validation
MAX_MESSAGE_LENGTH = 50000  # 50KB max message size
MAX_TITLE_LENGTH = 255
MAX_BULK_IDS = 100

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMITS = {
    'create_conversation': 30,    # 30 new conversations per minute
    'add_message': 60,            # 60 messages per minute
    'list_conversations': 120,    # 120 list requests per minute
    'search': 30,                 # 30 searches per minute
    'default': 60                 # default limit
}

# Simple in-memory rate limiter (use Redis for production multi-instance)
_rate_limit_store: Dict[str, Dict[str, Tuple[int, float]]] = defaultdict(dict)


def rate_limit(action: str = 'default'):
    """Rate limiting decorator for chat endpoints"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Get user identifier
            user_key = f"{g.tenant_id}:{g.user_id}"
            limit = RATE_LIMITS.get(action, RATE_LIMITS['default'])

            now = time.time()
            store = _rate_limit_store[action]

            # Get current count and window start
            count, window_start = store.get(user_key, (0, now))

            # Reset if window expired
            if now - window_start >= RATE_LIMIT_WINDOW:
                count = 0
                window_start = now

            # Check limit
            if count >= limit:
                return jsonify({
                    "success": False,
                    "error": f"Rate limit exceeded. Max {limit} requests per minute for this action."
                }), 429

            # Increment counter
            store[user_key] = (count + 1, window_start)

            return f(*args, **kwargs)
        return wrapper
    return decorator


def get_db():
    """Get database session"""
    return SessionLocal()


def generate_title_from_content(content: str) -> str:
    """Generate a short title from message content"""
    # Take first 50 chars, cut at last complete word
    if len(content) <= 50:
        return content
    truncated = content[:50]
    last_space = truncated.rfind(' ')
    if last_space > 20:
        return truncated[:last_space] + "..."
    return truncated + "..."


# ============================================================================
# CONVERSATIONS
# ============================================================================

@chat_bp.route('/conversations', methods=['GET'])
@require_auth
@rate_limit('list_conversations')
def list_conversations():
    """
    List all conversations for the current user/tenant.

    Query params:
    - include_archived: bool (default: false)
    - limit: int (default: 50, max: 100)
    - offset: int (default: 0)

    Returns conversations sorted by last_message_at descending.
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id

        include_archived = request.args.get('include_archived', 'false').lower() == 'true'
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))

        # Subquery to count messages per conversation (avoids N+1)
        message_count_subq = db.query(
            ChatMessage.conversation_id,
            func.count(ChatMessage.id).label('message_count')
        ).filter(
            ChatMessage.tenant_id == tenant_id
        ).group_by(ChatMessage.conversation_id).subquery()

        # Query conversations with message counts in single query
        query = db.query(
            ChatConversation,
            func.coalesce(message_count_subq.c.message_count, 0).label('message_count')
        ).outerjoin(
            message_count_subq,
            ChatConversation.id == message_count_subq.c.conversation_id
        ).filter(
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id
        )

        if not include_archived:
            query = query.filter(ChatConversation.is_archived == False)

        # Sort: pinned first, then by last_message_at
        query = query.order_by(
            ChatConversation.is_pinned.desc(),
            ChatConversation.last_message_at.desc()
        )

        # Get total count (use window function approach for efficiency)
        total_query = db.query(ChatConversation).filter(
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id
        )
        if not include_archived:
            total_query = total_query.filter(ChatConversation.is_archived == False)
        total = total_query.count()

        # Apply pagination
        results = query.offset(offset).limit(limit).all()

        # Build response without triggering lazy loads
        conversations_data = []
        for conv, msg_count in results:
            conversations_data.append({
                "id": conv.id,
                "tenant_id": conv.tenant_id,
                "user_id": conv.user_id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
                "is_archived": conv.is_archived,
                "is_pinned": conv.is_pinned,
                "message_count": msg_count
            })

        return jsonify({
            "success": True,
            "conversations": conversations_data,
            "total": total,
            "limit": limit,
            "offset": offset
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@chat_bp.route('/conversations', methods=['POST'])
@require_auth
@rate_limit('create_conversation')
def create_conversation():
    """
    Create a new conversation.

    Request body:
    {
        "title": "Optional title" (optional - auto-generated if not provided)
    }

    Returns the created conversation.
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id
        data = request.get_json() or {}

        conversation = ChatConversation(
            tenant_id=tenant_id,
            user_id=user_id,
            title=data.get('title'),
            is_archived=False,
            is_pinned=False
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return jsonify({
            "success": True,
            "conversation": conversation.to_dict()
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@chat_bp.route('/conversations/<conversation_id>', methods=['GET'])
@require_auth
def get_conversation(conversation_id: str):
    """
    Get a conversation with all its messages.

    Returns the conversation with messages sorted by created_at ascending.
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id

        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id
        ).first()

        if not conversation:
            return jsonify({
                "success": False,
                "error": "Conversation not found"
            }), 404

        return jsonify({
            "success": True,
            "conversation": conversation.to_dict(include_messages=True)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@chat_bp.route('/conversations/<conversation_id>', methods=['PUT'])
@require_auth
def update_conversation(conversation_id: str):
    """
    Update a conversation (title, archive status, pin status).

    Request body:
    {
        "title": "New title" (optional),
        "is_archived": true/false (optional),
        "is_pinned": true/false (optional)
    }
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id
        data = request.get_json() or {}

        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id
        ).first()

        if not conversation:
            return jsonify({
                "success": False,
                "error": "Conversation not found"
            }), 404

        # Update fields if provided
        if 'title' in data:
            conversation.title = data['title']
        if 'is_archived' in data:
            conversation.is_archived = bool(data['is_archived'])
        if 'is_pinned' in data:
            conversation.is_pinned = bool(data['is_pinned'])

        db.commit()
        db.refresh(conversation)

        return jsonify({
            "success": True,
            "conversation": conversation.to_dict()
        })

    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@chat_bp.route('/conversations/<conversation_id>', methods=['DELETE'])
@require_auth
def delete_conversation(conversation_id: str):
    """
    Delete a conversation and all its messages.
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id

        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id
        ).first()

        if not conversation:
            return jsonify({
                "success": False,
                "error": "Conversation not found"
            }), 404

        db.delete(conversation)  # Cascade deletes messages
        db.commit()

        return jsonify({
            "success": True,
            "message": "Conversation deleted"
        })

    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


# ============================================================================
# MESSAGES
# ============================================================================

@chat_bp.route('/conversations/<conversation_id>/messages', methods=['POST'])
@require_auth
@rate_limit('add_message')
def add_message(conversation_id: str):
    """
    Add a message to a conversation.

    Request body:
    {
        "role": "user" or "assistant",
        "content": "Message content",
        "sources": [...] (optional - for assistant messages),
        "metadata": {...} (optional)
    }
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        if not data.get('role') or not data.get('content'):
            return jsonify({
                "success": False,
                "error": "role and content are required"
            }), 400

        if data['role'] not in ['user', 'assistant']:
            return jsonify({
                "success": False,
                "error": "role must be 'user' or 'assistant'"
            }), 400

        # Validate content size to prevent abuse
        if len(data['content']) > MAX_MESSAGE_LENGTH:
            return jsonify({
                "success": False,
                "error": f"Message content exceeds maximum length of {MAX_MESSAGE_LENGTH} characters"
            }), 400

        # Verify conversation exists and belongs to user
        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id
        ).first()

        if not conversation:
            return jsonify({
                "success": False,
                "error": "Conversation not found"
            }), 404

        # Create message
        message = ChatMessage(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role=data['role'],
            content=data['content'],
            sources=data.get('sources', []),
            extra_data=data.get('metadata', {})  # API accepts 'metadata', stored as 'extra_data'
        )

        db.add(message)

        # Update conversation's last_message_at
        conversation.last_message_at = datetime.now(timezone.utc)

        # Auto-generate title if this is the first user message and no title set
        if not conversation.title and data['role'] == 'user':
            conversation.title = generate_title_from_content(data['content'])

        db.commit()
        db.refresh(message)

        return jsonify({
            "success": True,
            "message": message.to_dict()
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@chat_bp.route('/conversations/<conversation_id>/messages', methods=['GET'])
@require_auth
def get_messages(conversation_id: str):
    """
    Get all messages in a conversation.

    Query params:
    - limit: int (default: 100, max: 500)
    - before_id: string (for pagination - get messages before this ID)
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id

        limit = min(int(request.args.get('limit', 100)), 500)
        before_id = request.args.get('before_id')

        # Verify conversation access
        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id
        ).first()

        if not conversation:
            return jsonify({
                "success": False,
                "error": "Conversation not found"
            }), 404

        # Build query
        query = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.tenant_id == tenant_id
        )

        if before_id:
            # SECURITY: Include tenant_id filter to prevent cross-tenant probing
            before_msg = db.query(ChatMessage).filter(
                ChatMessage.id == before_id,
                ChatMessage.tenant_id == tenant_id,
                ChatMessage.conversation_id == conversation_id
            ).first()
            if before_msg:
                query = query.filter(
                    ChatMessage.created_at < before_msg.created_at
                )

        messages = query.order_by(
            ChatMessage.created_at.asc()
        ).limit(limit).all()

        return jsonify({
            "success": True,
            "messages": [m.to_dict() for m in messages],
            "conversation_id": conversation_id
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


# ============================================================================
# BULK OPERATIONS
# ============================================================================

@chat_bp.route('/conversations/bulk-archive', methods=['POST'])
@require_auth
def bulk_archive_conversations():
    """
    Archive multiple conversations.

    Request body:
    {
        "conversation_ids": ["id1", "id2", ...]
    }
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id
        data = request.get_json() or {}

        conversation_ids = data.get('conversation_ids', [])
        if not conversation_ids:
            return jsonify({
                "success": False,
                "error": "conversation_ids is required"
            }), 400

        # Limit bulk operations to prevent abuse
        if len(conversation_ids) > MAX_BULK_IDS:
            return jsonify({
                "success": False,
                "error": f"Cannot process more than {MAX_BULK_IDS} conversations at once"
            }), 400

        updated = db.query(ChatConversation).filter(
            ChatConversation.id.in_(conversation_ids),
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id
        ).update(
            {"is_archived": True},
            synchronize_session=False
        )

        db.commit()

        return jsonify({
            "success": True,
            "archived_count": updated
        })

    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@chat_bp.route('/conversations/bulk-delete', methods=['POST'])
@require_auth
def bulk_delete_conversations():
    """
    Delete multiple conversations.

    Request body:
    {
        "conversation_ids": ["id1", "id2", ...]
    }
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id
        data = request.get_json() or {}

        conversation_ids = data.get('conversation_ids', [])
        if not conversation_ids:
            return jsonify({
                "success": False,
                "error": "conversation_ids is required"
            }), 400

        # Limit bulk operations to prevent abuse
        if len(conversation_ids) > MAX_BULK_IDS:
            return jsonify({
                "success": False,
                "error": f"Cannot process more than {MAX_BULK_IDS} conversations at once"
            }), 400

        deleted = db.query(ChatConversation).filter(
            ChatConversation.id.in_(conversation_ids),
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id
        ).delete(synchronize_session=False)

        db.commit()

        return jsonify({
            "success": True,
            "deleted_count": deleted
        })

    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


# ============================================================================
# SEARCH
# ============================================================================

@chat_bp.route('/search', methods=['GET'])
@require_auth
@rate_limit('search')
def search_conversations():
    """
    Search conversations by content.

    Query params:
    - q: search query (required, 2-100 chars)
    - limit: int (default: 20, max: 50)
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        user_id = g.user_id

        query_text = request.args.get('q', '').strip()
        if not query_text:
            return jsonify({
                "success": False,
                "error": "Search query 'q' is required"
            }), 400

        # Validate query length
        if len(query_text) < 2:
            return jsonify({
                "success": False,
                "error": "Search query must be at least 2 characters"
            }), 400

        if len(query_text) > 100:
            return jsonify({
                "success": False,
                "error": "Search query must be at most 100 characters"
            }), 400

        limit = min(int(request.args.get('limit', 20)), 50)

        # Search in message content and conversation titles
        # Using LIKE - for production, consider PostgreSQL full-text search or Elasticsearch
        search_pattern = f"%{query_text}%"

        # Use EXISTS for better performance than IN subquery
        message_exists = db.query(ChatMessage.id).filter(
            ChatMessage.conversation_id == ChatConversation.id,
            ChatMessage.tenant_id == tenant_id,
            ChatMessage.content.ilike(search_pattern)
        ).exists()

        # Find conversations with matching messages or titles
        matching_conversations = db.query(ChatConversation).filter(
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.user_id == user_id,
            ChatConversation.is_archived == False
        ).filter(
            db.or_(
                ChatConversation.title.ilike(search_pattern),
                message_exists
            )
        ).order_by(
            ChatConversation.last_message_at.desc()
        ).limit(limit).all()

        # Build response without lazy loading messages
        conversations_data = [{
            "id": c.id,
            "title": c.title,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
            "is_pinned": c.is_pinned
        } for c in matching_conversations]

        return jsonify({
            "success": True,
            "query": query_text,
            "conversations": conversations_data,
            "count": len(matching_conversations)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()
