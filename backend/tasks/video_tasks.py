"""
Video Generation Tasks
Background tasks for generating training videos.
"""

from celery_app import celery
from database.models import get_db
from services.video_service import VideoService


@celery.task(bind=True, name='tasks.video_tasks.generate_video')
def generate_video_task(self, video_id: str, tenant_id: str):
    """
    Background task for generating training video.

    Args:
        video_id: Video ID from database
        tenant_id: Tenant ID for security

    Returns:
        dict: Video generation results
    """
    db = next(get_db())

    try:
        self.update_progress(0, 100, 'Starting video generation...')

        service = VideoService(db)

        # Progress callback
        def on_progress(current, total, message):
            self.update_progress(current, total, message)

        # Generate video
        result = service.generate_video(
            video_id=video_id,
            tenant_id=tenant_id,
            progress_callback=on_progress
        )

        self.update_progress(100, 100, 'Video generated successfully')

        return {
            'success': True,
            'video_id': video_id,
            'tenant_id': tenant_id,
            'file_path': result.get('file_path'),
            'duration': result.get('duration', 0),
            'size': result.get('size', 0)
        }

    except Exception as e:
        print(f"[VideoTask] Error: {e}", flush=True)

        # Update video status to failed in database
        from database.models import Video
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = 'failed'
            video.error_message = str(e)
            db.commit()

        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )

        raise

    finally:
        db.close()
