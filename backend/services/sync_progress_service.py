"""
Sync Progress Tracking Service
Real-time progress tracking for integration syncs with SSE support.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import uuid

@dataclass
class SyncProgress:
    """Progress state for a sync operation"""
    sync_id: str
    tenant_id: str
    user_id: str
    connector_type: str
    status: str  # 'connecting', 'syncing', 'parsing', 'embedding', 'complete', 'error'
    stage: str  # Current stage description
    total_items: int
    processed_items: int
    failed_items: int
    current_item: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data

    @property
    def percent_complete(self) -> float:
        """Calculate completion percentage"""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100


class SyncProgressService:
    """
    Service for tracking sync progress and emitting real-time updates via SSE.

    Usage:
        # Start sync
        sync_id = service.start_sync(tenant_id, user_id, 'gmail')

        # Update progress
        service.update_progress(sync_id, stage='Fetching emails', total_items=100)
        service.increment_processed(sync_id, current_item='Email from John')

        # Complete sync
        service.complete_sync(sync_id)

        # Subscribe to events (SSE endpoint)
        async for event in service.subscribe(sync_id):
            yield f"data: {json.dumps(event)}\\n\\n"
    """

    def __init__(self):
        # In-memory storage of sync progress
        self._progress: Dict[str, SyncProgress] = {}

        # Event queues for SSE subscribers
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)

        # Cleanup old syncs after this duration (seconds)
        self._cleanup_age = 3600  # 1 hour

    def start_sync(
        self,
        tenant_id: str,
        user_id: str,
        connector_type: str
    ) -> str:
        """
        Start a new sync operation.

        Returns:
            sync_id: Unique identifier for this sync
        """
        sync_id = str(uuid.uuid4())

        self._progress[sync_id] = SyncProgress(
            sync_id=sync_id,
            tenant_id=tenant_id,
            user_id=user_id,
            connector_type=connector_type,
            status='connecting',
            stage='Connecting to service...',
            total_items=0,
            processed_items=0,
            failed_items=0,
            started_at=datetime.now(timezone.utc)
        )

        self._emit_event(sync_id, 'started')

        print(f"[SyncProgress] Started sync: {sync_id} for {connector_type}")
        return sync_id

    def update_progress(
        self,
        sync_id: str,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        total_items: Optional[int] = None,
        current_item: Optional[str] = None
    ):
        """Update sync progress"""
        if sync_id not in self._progress:
            print(f"[SyncProgress] WARNING: sync_id {sync_id} not found")
            return

        progress = self._progress[sync_id]

        if status:
            progress.status = status
        if stage:
            progress.stage = stage
        if total_items is not None:
            progress.total_items = total_items
        if current_item is not None:
            progress.current_item = current_item

        self._emit_event(sync_id, 'progress')

    def increment_processed(
        self,
        sync_id: str,
        current_item: Optional[str] = None,
        failed: bool = False
    ):
        """Increment processed item count"""
        if sync_id not in self._progress:
            return

        progress = self._progress[sync_id]

        if failed:
            progress.failed_items += 1
        else:
            progress.processed_items += 1

        if current_item:
            progress.current_item = current_item

        # Emit event for significant milestones
        should_emit = False

        if progress.total_items > 0:
            percent = progress.percent_complete
            prev_processed = progress.processed_items - 1
            prev_percent = (prev_processed / progress.total_items) * 100 if prev_processed > 0 else 0

            # Check if we crossed any milestone (10%, 25%, 50%, 75%, 90%)
            milestones = [10, 25, 50, 75, 90]
            for milestone in milestones:
                if prev_percent < milestone <= percent:
                    should_emit = True
                    break

            # Also emit every 5 items for responsive feedback
            if not should_emit and progress.processed_items % 5 == 0:
                should_emit = True

            # Always emit on first and last item
            if progress.processed_items == 1 or progress.processed_items == progress.total_items:
                should_emit = True
        else:
            # If total unknown, emit every 3 items for more responsive feedback
            if progress.processed_items % 3 == 0 or progress.processed_items == 1:
                should_emit = True

        if should_emit:
            self._emit_event(sync_id, 'progress')

    def complete_sync(
        self,
        sync_id: str,
        error_message: Optional[str] = None
    ):
        """Mark sync as complete or failed"""
        if sync_id not in self._progress:
            return

        progress = self._progress[sync_id]
        progress.completed_at = datetime.now(timezone.utc)

        if error_message:
            progress.status = 'error'
            progress.stage = 'Sync failed'
            progress.error_message = error_message
            self._emit_event(sync_id, 'error')
        else:
            progress.status = 'complete'
            progress.stage = 'Sync complete'
            self._emit_event(sync_id, 'complete')

        print(f"[SyncProgress] Completed sync: {sync_id} - {progress.status}")

    def get_progress(self, sync_id: str) -> Optional[Dict]:
        """Get current progress for a sync"""
        progress = self._progress.get(sync_id)
        return progress.to_dict() if progress else None

    async def subscribe(self, sync_id: str) -> asyncio.Queue:
        """
        Subscribe to progress events for a sync.

        Returns:
            Queue that will receive progress events
        """
        queue = asyncio.Queue(maxsize=100)
        self._subscribers[sync_id].append(queue)

        # Send current state immediately
        if sync_id in self._progress:
            await queue.put({
                'event': 'current_state',
                'data': self._progress[sync_id].to_dict()
            })

        print(f"[SyncProgress] New subscriber for {sync_id} (total: {len(self._subscribers[sync_id])})")
        return queue

    def unsubscribe(self, sync_id: str, queue: asyncio.Queue):
        """Unsubscribe from progress events"""
        if sync_id in self._subscribers:
            if queue in self._subscribers[sync_id]:
                self._subscribers[sync_id].remove(queue)
                print(f"[SyncProgress] Unsubscribed from {sync_id}")

    def _emit_event(self, sync_id: str, event_type: str):
        """Emit event to all subscribers"""
        if sync_id not in self._progress:
            return

        progress = self._progress[sync_id]
        event = {
            'event': event_type,
            'data': progress.to_dict()
        }

        # Send to all subscribers (non-blocking)
        if sync_id in self._subscribers:
            for queue in self._subscribers[sync_id]:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    print(f"[SyncProgress] Queue full for subscriber, skipping event")

    def cleanup_old_syncs(self, max_age_seconds: int = 3600):
        """Remove syncs older than max_age_seconds"""
        now = datetime.now(timezone.utc)
        to_remove = []

        for sync_id, progress in self._progress.items():
            if progress.completed_at:
                age = (now - progress.completed_at).total_seconds()
                if age > max_age_seconds:
                    to_remove.append(sync_id)

        for sync_id in to_remove:
            del self._progress[sync_id]
            if sync_id in self._subscribers:
                del self._subscribers[sync_id]
            print(f"[SyncProgress] Cleaned up old sync: {sync_id}")


# Global instance
_sync_progress_service = None

def get_sync_progress_service() -> SyncProgressService:
    """Get the global SyncProgressService instance"""
    global _sync_progress_service
    if _sync_progress_service is None:
        _sync_progress_service = SyncProgressService()
    return _sync_progress_service
