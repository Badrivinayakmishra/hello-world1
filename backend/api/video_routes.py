"""
Video API Routes
REST endpoints for video generation and management.
"""

from flask import Blueprint, request, jsonify, g, send_file, redirect
from pathlib import Path

from database.models import SessionLocal, Video, VideoStatus, utc_now
from services.auth_service import require_auth
from services.video_service import VideoService


# Create blueprint
video_bp = Blueprint('videos', __name__, url_prefix='/api/videos')


def get_db():
    """Get database session"""
    return SessionLocal()


# ============================================================================
# CREATE VIDEO
# ============================================================================

@video_bp.route('', methods=['POST'])
@require_auth
def create_video():
    """
    Create a new training video.

    Request body:
    {
        "title": "Onboarding Training",
        "description": "Introduction to our processes",
        "source_type": "documents" | "knowledge_gaps",
        "source_ids": ["id1", "id2", ...],
        "project_id": "..." (optional),
        "include_answers": true (for knowledge_gaps)
    }

    Response:
    {
        "success": true,
        "video": {
            "id": "...",
            "status": "queued",
            ...
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400

        title = data.get('title')
        source_type = data.get('source_type')
        source_ids = data.get('source_ids', [])

        if not title:
            return jsonify({
                "success": False,
                "error": "title required"
            }), 400

        if not source_type or source_type not in ['documents', 'knowledge_gaps']:
            return jsonify({
                "success": False,
                "error": "source_type must be 'documents' or 'knowledge_gaps'"
            }), 400

        if not source_ids:
            return jsonify({
                "success": False,
                "error": "source_ids required"
            }), 400

        db = get_db()
        try:
            service = VideoService(db)

            if source_type == 'documents':
                video, error = service.create_video_from_documents(
                    tenant_id=g.tenant_id,
                    title=title,
                    document_ids=source_ids,
                    description=data.get('description'),
                    project_id=data.get('project_id')
                )
            else:
                video, error = service.create_video_from_gaps(
                    tenant_id=g.tenant_id,
                    title=title,
                    gap_ids=source_ids,
                    include_answers=data.get('include_answers', True),
                    description=data.get('description')
                )

            if error:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            return jsonify({
                "success": True,
                "video": video.to_dict()
            }), 201

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# LIST VIDEOS
# ============================================================================

@video_bp.route('', methods=['GET'])
@require_auth
def list_videos():
    """
    List videos with filtering.

    Query params:
        project_id: filter by project
        status: queued, processing, completed, failed
        limit: page size (default 50)
        offset: page offset

    Response:
    {
        "success": true,
        "videos": [...],
        "pagination": {...}
    }
    """
    try:
        project_id = request.args.get('project_id')
        status_str = request.args.get('status')
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))

        status = None
        if status_str:
            status_map = {
                'queued': VideoStatus.QUEUED,
                'processing': VideoStatus.PROCESSING,
                'completed': VideoStatus.COMPLETED,
                'failed': VideoStatus.FAILED
            }
            status = status_map.get(status_str.lower())

        db = get_db()
        try:
            service = VideoService(db)
            videos, total = service.list_videos(
                tenant_id=g.tenant_id,
                project_id=project_id,
                status=status,
                limit=limit,
                offset=offset
            )

            return jsonify({
                "success": True,
                "videos": [v.to_dict() for v in videos],
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GET VIDEO
# ============================================================================

@video_bp.route('/<video_id>', methods=['GET'])
@require_auth
def get_video(video_id: str):
    """
    Get video details.

    Response:
    {
        "success": true,
        "video": { ... }
    }
    """
    try:
        db = get_db()
        try:
            service = VideoService(db)
            video = service.get_video(video_id, g.tenant_id)

            if not video:
                return jsonify({
                    "success": False,
                    "error": "Video not found"
                }), 404

            return jsonify({
                "success": True,
                "video": video.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# VIDEO STATUS/PROGRESS
# ============================================================================

@video_bp.route('/<video_id>/status', methods=['GET'])
@require_auth
def get_video_status(video_id: str):
    """
    Get video generation status and progress.

    Response:
    {
        "success": true,
        "status": "processing",
        "progress_percent": 45,
        "error_message": null
    }
    """
    try:
        db = get_db()
        try:
            video = db.query(Video).filter(
                Video.id == video_id,
                Video.tenant_id == g.tenant_id
            ).first()

            if not video:
                return jsonify({
                    "success": False,
                    "error": "Video not found"
                }), 404

            return jsonify({
                "success": True,
                "status": video.status.value,
                "progress_percent": video.progress_percent,
                "current_step": video.current_step,
                "error_message": video.error_message,
                "started_at": video.started_at.isoformat() if video.started_at else None,
                "completed_at": video.completed_at.isoformat() if video.completed_at else None
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# DOWNLOAD VIDEO
# ============================================================================

@video_bp.route('/<video_id>/download', methods=['GET'])
@require_auth
def download_video(video_id: str):
    """
    Download the video file.

    Response:
        Video file (mp4)
    """
    try:
        db = get_db()
        try:
            video = db.query(Video).filter(
                Video.id == video_id,
                Video.tenant_id == g.tenant_id
            ).first()

            if not video:
                return jsonify({
                    "success": False,
                    "error": "Video not found"
                }), 404

            if video.status != VideoStatus.COMPLETED:
                return jsonify({
                    "success": False,
                    "error": "Video not ready"
                }), 400

            if not video.file_path:
                return jsonify({
                    "success": False,
                    "error": "Video file not found"
                }), 404

            # Check if file is in S3 (URL starts with http)
            if video.file_path.startswith('http'):
                # Redirect to S3 URL
                return redirect(video.file_path)
            elif Path(video.file_path).exists():
                # Serve local file
                return send_file(
                    video.file_path,
                    mimetype='video/mp4',
                    as_attachment=True,
                    download_name=f"{video.title}.mp4"
                )
            else:
                return jsonify({
                    "success": False,
                    "error": "Video file not found"
                }), 404

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# THUMBNAIL
# ============================================================================

@video_bp.route('/<video_id>/thumbnail', methods=['GET'])
@require_auth
def get_thumbnail(video_id: str):
    """
    Get video thumbnail.

    Response:
        JPEG image
    """
    try:
        db = get_db()
        try:
            video = db.query(Video).filter(
                Video.id == video_id,
                Video.tenant_id == g.tenant_id
            ).first()

            if not video:
                return jsonify({
                    "success": False,
                    "error": "Video not found"
                }), 404

            if not video.thumbnail_path:
                return jsonify({
                    "success": False,
                    "error": "Thumbnail not found"
                }), 404

            # Check if file is in S3 (URL starts with http)
            if video.thumbnail_path.startswith('http'):
                # Redirect to S3 URL
                return redirect(video.thumbnail_path)
            elif Path(video.thumbnail_path).exists():
                # Serve local file
                return send_file(
                    video.thumbnail_path,
                    mimetype='image/jpeg'
                )
            else:
                return jsonify({
                    "success": False,
                    "error": "Thumbnail not found"
                }), 404

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# DELETE VIDEO
# ============================================================================

@video_bp.route('/<video_id>', methods=['DELETE'])
@require_auth
def delete_video(video_id: str):
    """
    Delete a video and its files.

    Response:
    {
        "success": true
    }
    """
    try:
        db = get_db()
        try:
            service = VideoService(db)
            success, error = service.delete_video(video_id, g.tenant_id)

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
# REGENERATE VIDEO
# ============================================================================

@video_bp.route('/<video_id>/regenerate', methods=['POST'])
@require_auth
def regenerate_video(video_id: str):
    """
    Regenerate a failed or completed video.

    Response:
    {
        "success": true,
        "video": { ... }
    }
    """
    try:
        db = get_db()
        try:
            video = db.query(Video).filter(
                Video.id == video_id,
                Video.tenant_id == g.tenant_id
            ).first()

            if not video:
                return jsonify({
                    "success": False,
                    "error": "Video not found"
                }), 404

            # Reset video status
            video.status = VideoStatus.QUEUED
            video.progress_percent = 0
            video.error_message = None
            video.started_at = None
            video.completed_at = None
            db.commit()

            # Start regeneration
            service = VideoService(db)

            import threading

            def regenerate():
                service._process_video(video.id, g.tenant_id)

            thread = threading.Thread(target=regenerate)
            thread.start()

            return jsonify({
                "success": True,
                "video": video.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
