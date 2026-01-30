"""
Celery Application Configuration
Background job processing for long-running operations.
"""

import os
from celery import Celery
from kombu import Exchange, Queue

# Get Redis URL from environment or use localhost
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery = Celery(
    'secondbrain',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        'tasks.sync_tasks',
        'tasks.gap_analysis_tasks',
        'tasks.embedding_tasks',
        'tasks.video_tasks'
    ]
)

# Celery Configuration
celery.conf.update(
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Results
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store more metadata

    # Task execution
    task_acks_late=True,  # Ack after task completion (more reliable)
    task_reject_on_worker_lost=True,  # Reject if worker dies
    task_time_limit=1800,  # 30 minute hard limit
    task_soft_time_limit=1600,  # 26 minute soft limit (warning)

    # Worker configuration
    worker_prefetch_multiplier=1,  # Don't prefetch tasks (better distribution)
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)

    # Retry configuration
    task_autoretry_for=(Exception,),  # Auto-retry on any exception
    task_retry_kwargs={'max_retries': 3, 'countdown': 60},  # Retry 3 times with 60s delay

    # Priority queues
    task_default_priority=5,  # Default priority (0-10, 10 is highest)
    task_create_missing_queues=True,

    # Queue configuration
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default', priority=5),
        Queue('high_priority', Exchange('high_priority'), routing_key='high_priority', priority=10),
        Queue('low_priority', Exchange('low_priority'), routing_key='low_priority', priority=1),
    ),

    # Task routes
    task_routes={
        'tasks.sync_tasks.*': {'queue': 'default'},
        'tasks.gap_analysis_tasks.*': {'queue': 'high_priority'},
        'tasks.embedding_tasks.*': {'queue': 'default'},
        'tasks.video_tasks.*': {'queue': 'low_priority'},
    },

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,

    # Beat schedule (for periodic tasks)
    beat_schedule={
        'cleanup-old-results': {
            'task': 'tasks.maintenance.cleanup_old_results',
            'schedule': 3600.0,  # Run every hour
        },
    },
)


# ============================================================================
# TASK BASE CLASS
# ============================================================================

class CallbackTask(celery.Task):
    """
    Base task class with progress tracking support.
    """

    def update_progress(self, current, total, message='Processing...'):
        """
        Update task progress.

        Args:
            current: Current progress value
            total: Total expected value
            message: Status message
        """
        percent = int((current / total) * 100) if total > 0 else 0

        self.update_state(
            state='PROGRESS',
            meta={
                'current': current,
                'total': total,
                'percent': percent,
                'status': message
            }
        )

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds"""
        print(f"[Celery] Task {task_id} succeeded: {retval}", flush=True)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails"""
        print(f"[Celery] Task {task_id} failed: {exc}", flush=True)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried"""
        print(f"[Celery] Task {task_id} retry: {exc}", flush=True)


# Set default task base class
celery.Task = CallbackTask


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_task_info(task_id):
    """
    Get task status and result.

    Returns:
        dict: Task information with state, progress, result
    """
    task = celery.AsyncResult(task_id)

    response = {
        'task_id': task_id,
        'state': task.state,
        'current': 0,
        'total': 100,
        'percent': 0,
        'status': 'Pending...',
        'result': None
    }

    if task.state == 'PENDING':
        # Task is waiting to start
        response['status'] = 'Waiting in queue...'

    elif task.state == 'PROGRESS':
        # Task is running
        info = task.info or {}
        response.update({
            'current': info.get('current', 0),
            'total': info.get('total', 100),
            'percent': info.get('percent', 0),
            'status': info.get('status', 'Processing...')
        })

    elif task.state == 'SUCCESS':
        # Task completed successfully
        response.update({
            'current': 100,
            'total': 100,
            'percent': 100,
            'status': 'Completed',
            'result': task.result
        })

    elif task.state == 'FAILURE':
        # Task failed
        response.update({
            'status': 'Failed',
            'error': str(task.info) if task.info else 'Unknown error'
        })

    elif task.state == 'RETRY':
        # Task is being retried
        response['status'] = 'Retrying after error...'

    elif task.state == 'REVOKED':
        # Task was cancelled
        response['status'] = 'Cancelled'

    return response


def revoke_task(task_id, terminate=False):
    """
    Cancel a running task.

    Args:
        task_id: Task ID to revoke
        terminate: If True, forcefully terminate the task
    """
    celery.control.revoke(task_id, terminate=terminate)


# ============================================================================
# STARTUP CHECK
# ============================================================================

def check_redis_connection():
    """Check if Redis is accessible"""
    try:
        celery.backend.client.ping()
        print("[Celery] ✓ Redis connection successful", flush=True)
        return True
    except Exception as e:
        print(f"[Celery] ✗ Redis connection failed: {e}", flush=True)
        print(f"[Celery] Make sure Redis is running: redis-server", flush=True)
        return False


if __name__ == '__main__':
    """Run Celery worker"""
    check_redis_connection()
    celery.start()
