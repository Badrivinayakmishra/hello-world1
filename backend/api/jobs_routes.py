"""
Background Jobs API Routes
Endpoints for checking status and managing background jobs.
"""

from flask import Blueprint, request, jsonify, g
from services.auth_service import require_auth
from celery_app import get_task_info, revoke_task

jobs_bp = Blueprint('jobs', __name__)


@jobs_bp.route('/jobs/<task_id>', methods=['GET'])
@require_auth
def get_job_status(task_id):
    """
    Get status of a background job.

    GET /api/jobs/<task_id>

    Returns:
        JSON with task state, progress, and result
    """
    try:
        task_info = get_task_info(task_id)

        return jsonify({
            'success': True,
            'job': task_info
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@jobs_bp.route('/jobs/<task_id>/cancel', methods=['POST'])
@require_auth
def cancel_job(task_id):
    """
    Cancel a running background job.

    POST /api/jobs/<task_id>/cancel
    Body: { "terminate": false }

    Args:
        terminate: If true, forcefully kill the task

    Returns:
        JSON with success status
    """
    try:
        data = request.get_json() or {}
        terminate = data.get('terminate', False)

        revoke_task(task_id, terminate=terminate)

        return jsonify({
            'success': True,
            'message': 'Job cancelled' if not terminate else 'Job terminated'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@jobs_bp.route('/jobs', methods=['GET'])
@require_auth
def list_jobs():
    """
    List recent jobs (placeholder - would need Redis storage for full implementation).

    GET /api/jobs?tenant_id=xxx

    Returns:
        JSON with list of recent jobs
    """
    try:
        # This would require storing job metadata in Redis
        # For now, return a simple message
        return jsonify({
            'success': True,
            'message': 'Job history not yet implemented. Use specific task_id to check status.',
            'jobs': []
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
