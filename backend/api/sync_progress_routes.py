"""
Sync Progress API Routes
Server-Sent Events (SSE) endpoint for real-time sync progress updates.
"""

import json
import asyncio
from flask import Blueprint, Response, request, jsonify, g
from services.sync_progress_service import get_sync_progress_service
from services.auth_service import require_auth

sync_progress_bp = Blueprint('sync_progress', __name__, url_prefix='/api/sync-progress')

# CORS allowed origins
ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:3006',
    'https://twondbrain-frontend.onrender.com',
    'https://2ndbrain.onrender.com'
]


@sync_progress_bp.route('/<sync_id>/stream', methods=['GET', 'OPTIONS'])
def stream_progress(sync_id: str):
    """
    Server-Sent Events endpoint for real-time sync progress.

    GET /api/sync-progress/<sync_id>/stream?token=<jwt_token>

    Note: EventSource cannot send custom headers, so token is passed as query param

    Returns:
        SSE stream with progress events:
        - started: Sync has begun
        - progress: Progress updated
        - complete: Sync finished successfully
        - error: Sync failed
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        origin = request.headers.get('Origin', '')
        cors_origin = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[2]
        return Response('', status=200, headers={
            'Access-Control-Allow-Origin': cors_origin,
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Max-Age': '86400'
        })

    # Manual auth check for SSE (query param instead of header)
    from services.auth_service import JWTUtils

    print(f"[SSE] Stream request for sync_id: {sync_id}")

    token = request.args.get('token')
    if not token:
        print(f"[SSE] ERROR: No token provided in query params")
        return jsonify({"error": "Missing authorization token. Token must be passed as query parameter."}), 401

    payload, error = JWTUtils.decode_access_token(token)
    if error:
        print(f"[SSE] ERROR: Token validation failed: {error}")
        return jsonify({"error": f"Invalid token: {error}"}), 401

    # Store user info in Flask g object
    g.user_id = payload.get("sub")
    g.tenant_id = payload.get("tenant_id")
    g.email = payload.get("email")
    g.role = payload.get("role")

    print(f"[SSE] Authenticated user: {g.email} (tenant: {g.tenant_id})")

    service = get_sync_progress_service()

    def generate_events():
        """Generator for SSE events"""
        print(f"[SSE] Starting event generator for {sync_id}")

        # Send immediate connection confirmation
        yield f"event: connected\n"
        yield f"data: {json.dumps({'sync_id': sync_id, 'status': 'connected'})}\n\n"

        # Create event queue
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            queue = loop.run_until_complete(service.subscribe(sync_id))
            print(f"[SSE] Subscribed to sync {sync_id}")
        except Exception as e:
            print(f"[SSE] ERROR: Failed to subscribe: {e}")
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': f'Failed to subscribe to sync: {str(e)}'})}\n\n"
            loop.close()
            return

        # Send current state immediately so frontend has data
        try:
            current_state = service.get_progress(sync_id)
            if current_state:
                # current_state is already a dict
                print(f"[SSE] Sending current state: {current_state.get('status', 'unknown')}")
                yield f"event: current_state\n"
                yield f"data: {json.dumps(current_state)}\n\n"
            else:
                print(f"[SSE] No current state found for {sync_id}")
        except Exception as e:
            print(f"[SSE] ERROR getting current state: {e}")
            import traceback
            traceback.print_exc()

        try:
            # Keep-alive timeout
            timeout = 30  # seconds

            while True:
                try:
                    # Wait for next event with timeout
                    event = loop.run_until_complete(
                        asyncio.wait_for(queue.get(), timeout=timeout)
                    )

                    print(f"[SSE] Sending event: {event['event']} for {sync_id}")

                    # Send event to client
                    yield f"event: {event['event']}\n"
                    yield f"data: {json.dumps(event['data'])}\n\n"

                    # Stop after complete or error
                    if event['event'] in ['complete', 'error']:
                        print(f"[SSE] Sync {sync_id} finished, closing stream")
                        break

                except asyncio.TimeoutError:
                    # Send keep-alive comment
                    yield ": keep-alive\n\n"

        except Exception as e:
            print(f"[SSE] ERROR in event stream: {e}")
            import traceback
            traceback.print_exc()
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        finally:
            # Clean up
            print(f"[SSE] Cleaning up subscription for {sync_id}")
            service.unsubscribe(sync_id, queue)
            loop.close()

    # Get origin for CORS
    origin = request.headers.get('Origin', '')

    # Set CORS origin header if origin is allowed
    cors_origin = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[2]  # Default to production

    return Response(
        generate_events(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': cors_origin,
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
    )


@sync_progress_bp.route('/<sync_id>', methods=['GET'])
@require_auth
def get_progress(sync_id: str):
    """
    Get current progress state for a sync.

    GET /api/sync-progress/<sync_id>

    Returns:
        {
            "success": true,
            "progress": {
                "sync_id": "...",
                "status": "syncing",
                "stage": "Fetching emails...",
                "total_items": 100,
                "processed_items": 45,
                "failed_items": 2,
                "current_item": "Email from John",
                "percent_complete": 45.0,
                ...
            }
        }
    """
    service = get_sync_progress_service()
    progress = service.get_progress(sync_id)

    if progress:
        return jsonify({
            "success": True,
            "progress": progress
        })
    else:
        return jsonify({
            "success": False,
            "error": "Sync not found"
        }), 404
