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


@sync_progress_bp.route('/<sync_id>/stream', methods=['GET'])
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
    # Manual auth check for SSE (query param instead of header)
    from services.auth_service import JWTUtils

    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Missing authorization token"}), 401

    payload, error = JWTUtils.decode_access_token(token)
    if error:
        return jsonify({"error": error}), 401

    # Store user info in Flask g object
    g.user_id = payload.get("sub")
    g.tenant_id = payload.get("tenant_id")
    g.email = payload.get("email")
    g.role = payload.get("role")

    service = get_sync_progress_service()

    def generate_events():
        """Generator for SSE events"""
        # Create event queue
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        queue = loop.run_until_complete(service.subscribe(sync_id))

        try:
            # Keep-alive timeout
            timeout = 30  # seconds

            while True:
                try:
                    # Wait for next event with timeout
                    event = loop.run_until_complete(
                        asyncio.wait_for(queue.get(), timeout=timeout)
                    )

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
            print(f"[SSE] Error in event stream: {e}")
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        finally:
            # Clean up
            service.unsubscribe(sync_id, queue)
            loop.close()

    return Response(
        generate_events(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Connection': 'keep-alive'
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
