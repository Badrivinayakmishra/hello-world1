# Sync Fix Implementation Guide

**Date:** 2026-01-31
**Status:** IN PROGRESS

---

## Overview

This guide documents the comprehensive fix for sync issues across all integrations (Gmail, Slack, Box, GitHub), including:

1. **Timeouts** - Prevent indefinite hanging
2. **Real-time progress** - Live status updates via Server-Sent Events (SSE)
3. **Email notifications** - Notify users when sync completes
4. **Better UX** - Progress modal showing what's happening

---

## ✅ Completed Components

### 1. Progress Tracking Service (`services/sync_progress_service.py`)

**Features:**
- Track sync state (connecting, syncing, parsing, embedding, complete, error)
- Real-time progress updates (items found, processed, failed)
- SSE event emission to subscribers
- Automatic cleanup of old syncs

**Usage:**
```python
from services.sync_progress_service import get_sync_progress_service

service = get_sync_progress_service()

# Start sync
sync_id = service.start_sync(tenant_id, user_id, 'gmail')

# Update progress
service.update_progress(sync_id,
    status='syncing',
    stage='Fetching emails...',
    total_items=100
)

# Increment count
service.increment_processed(sync_id, current_item='Email from John')

# Complete
service.complete_sync(sync_id)
```

### 2. SSE Endpoint (`api/sync_progress_routes.py`)

**Endpoints:**
- `GET /api/sync-progress/<sync_id>/stream` - SSE stream for real-time updates
- `GET /api/sync-progress/<sync_id>` - Get current progress state

**Events emitted:**
- `started` - Sync has begun
- `progress` - Progress updated (emitted at 10%, 25%, 50%, 75%, 90% milestones)
- `complete` - Sync finished successfully
- `error` - Sync failed

**Frontend usage:**
```typescript
const eventSource = new EventSource(`/api/sync-progress/${syncId}/stream`);

eventSource.addEventListener('progress', (event) => {
    const data = JSON.parse(event.data);
    console.log(`${data.percent_complete}%: ${data.stage}`);
});

eventSource.addEventListener('complete', (event) => {
    console.log('Sync complete!');
    eventSource.close();
});
```

### 3. Email Notification Service (`services/email_notification_service.py`)

**Features:**
- HTML email templates
- Sync completion summaries
- Error notifications
- SMTP with TLS

**Configuration (`.env`):**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Generate at https://myaccount.google.com/apppasswords
SMTP_FROM_EMAIL=noreply@2ndbrain.ai
SMTP_FROM_NAME="2nd Brain"
```

**Usage:**
```python
from services.email_notification_service import get_email_service

email_service = get_email_service()

email_service.send_sync_complete_notification(
    user_email='user@example.com',
    connector_type='gmail',
    total_items=100,
    processed_items=98,
    failed_items=2,
    duration_seconds=45.3
)
```

---

## 🚧 In Progress

### 4. Connector Manager Updates

**File:** `connectors/connector_manager.py`

**Changes needed:**
1. Import progress service and email service
2. Start progress tracking when sync begins
3. Pass sync_id to connectors
4. Update progress during sync
5. Send email notification when complete
6. Add timeout wrappers

**Code additions:**

```python
# At top of file
from services.sync_progress_service import get_sync_progress_service
from services.email_notification_service import get_email_service
from database.models import User  # To get user email

# Update sync_connector method
async def sync_connector(
    self,
    user_id: str,
    connector_type: str,
    since: Optional[datetime] = None,
    tenant_id: Optional[str] = None
) -> Dict:
    """Sync a specific connector with progress tracking"""

    # Get user email for notifications
    from database.models import SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        user_email = user.email if user else None
    finally:
        db.close()

    # Start progress tracking
    progress_service = get_sync_progress_service()
    sync_id = progress_service.start_sync(tenant_id or user_id, user_id, connector_type)

    connector_id = self.get_connector_id(user_id, connector_type)

    if connector_id not in self.connectors:
        progress_service.complete_sync(sync_id, error_message=f"{connector_type} not configured")
        return {"success": False, "error": f"{connector_type} not configured"}

    connector = self.connectors[connector_id]

    try:
        start_time = datetime.now()

        # Connect with timeout
        progress_service.update_progress(sync_id, status='connecting', stage=f'Connecting to {connector_type}...')

        try:
            connected = await asyncio.wait_for(
                connector.connect(),
                timeout=self.CONNECTION_TIMEOUT
            )
            if not connected:
                error_msg = connector.last_error or "Failed to connect"
                progress_service.complete_sync(sync_id, error_message=error_msg)
                return {"success": False, "error": error_msg}
        except asyncio.TimeoutError:
            error_msg = f"Connection timeout after {self.CONNECTION_TIMEOUT} seconds"
            progress_service.complete_sync(sync_id, error_message=error_msg)
            return {"success": False, "error": error_msg}

        # Sync with progress tracking
        progress_service.update_progress(sync_id, status='syncing', stage='Fetching data...')

        # Pass sync_id to connector for progress updates
        connector._sync_id = sync_id
        connector._progress_service = progress_service

        try:
            documents = await asyncio.wait_for(
                connector.sync(since),
                timeout=self.SYNC_TIMEOUT
            )
        except asyncio.TimeoutError:
            error_msg = f"Sync timeout after {self.SYNC_TIMEOUT} seconds"
            progress_service.complete_sync(sync_id, error_message=error_msg)
            return {"success": False, "error": error_msg}

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Complete progress tracking
        progress_service.complete_sync(sync_id)

        # Send email notification
        if user_email:
            email_service = get_email_service()
            email_service.send_sync_complete_notification(
                user_email=user_email,
                connector_type=connector_type,
                total_items=len(documents),
                processed_items=len(documents),
                failed_items=0,
                duration_seconds=duration
            )

        # Update connector
        connector.config.last_sync = datetime.now()
        self._save_config(connector_id, connector.config)

        # Record sync history
        self.sync_history.append({
            "connector_id": connector_id,
            "user_id": user_id,
            "connector_type": connector_type,
            "timestamp": datetime.now().isoformat(),
            "documents_synced": len(documents),
            "duration_seconds": duration,
            "success": True,
            "sync_id": sync_id
        })

        return {
            "success": True,
            "documents": [doc.to_dict() for doc in documents],
            "count": len(documents),
            "sync_time": datetime.now().isoformat(),
            "sync_id": sync_id,
            "duration_seconds": duration
        }

    except Exception as e:
        # Complete with error
        progress_service.complete_sync(sync_id, error_message=str(e))

        # Send error email
        if user_email:
            email_service = get_email_service()
            email_service.send_sync_complete_notification(
                user_email=user_email,
                connector_type=connector_type,
                total_items=0,
                processed_items=0,
                failed_items=0,
                duration_seconds=0,
                error_message=str(e)
            )

        self.sync_history.append({
            "connector_id": connector_id,
            "user_id": user_id,
            "connector_type": connector_type,
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "success": False,
            "sync_id": sync_id
        })

        return {"success": False, "error": str(e), "sync_id": sync_id}
```

---

## 📋 TODO

### 5. Add Timeouts to Connectors

#### Gmail Connector (`connectors/gmail_connector.py`)

**Add at top:**
```python
# Timeout configuration
REQUEST_TIMEOUT = 30  # seconds
MAX_PAGINATION_ITERATIONS = 100
```

**Add timeout to API calls:**
- Line 107: `execute()` → `execute(num_retries=3, timeout=REQUEST_TIMEOUT)`
- Line 129: `execute()` → `execute(num_retries=3, timeout=REQUEST_TIMEOUT)`
- Line 256: `execute()` → `execute(num_retries=3, timeout=REQUEST_TIMEOUT)`
- Line 265-269: `execute()` → `execute(num_retries=3, timeout=REQUEST_TIMEOUT)`

**Add pagination limit:**
```python
# In sync() method around line 242
page_count = 0
while True:
    page_count += 1
    if page_count > MAX_PAGINATION_ITERATIONS:
        print(f"[Gmail] Hit pagination limit of {MAX_PAGINATION_ITERATIONS} pages")
        break

    # ... existing pagination code
```

**Add progress tracking:**
```python
# In sync() method
if hasattr(self, '_progress_service') and hasattr(self, '_sync_id'):
    self._progress_service.update_progress(
        self._sync_id,
        total_items=len(messages)
    )

# Inside message processing loop
if hasattr(self, '_progress_service') and hasattr(self, '_sync_id'):
    self._progress_service.increment_processed(
        self._sync_id,
        current_item=f"Email: {subject}"
    )
```

#### Slack Connector (`connectors/slack_connector.py`)

**Add at top:**
```python
# Timeout configuration
REQUEST_TIMEOUT = 30
MAX_CHANNELS = 200
MAX_MESSAGES_PER_CHANNEL = 10000
```

**Add timeout to Slack SDK calls:**
The Slack SDK doesn't have direct timeout support, but we can wrap calls:
```python
import asyncio

async def _call_with_timeout(self, func, *args, **kwargs):
    """Call Slack API method with timeout"""
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, func, *args),
            timeout=REQUEST_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise SlackApiError("API call timed out", response={'error': 'timeout'})
```

**Add progress tracking:**
```python
# In sync() method
if hasattr(self, '_progress_service') and hasattr(self, '_sync_id'):
    self._progress_service.update_progress(
        self._sync_id,
        stage=f'Syncing {len(channels)} channels...',
        total_items=len(channels)
    )

# Inside channel loop
if hasattr(self, '_progress_service') and hasattr(self, '_sync_id'):
    self._progress_service.increment_processed(
        self._sync_id,
        current_item=f"Channel: {channel['name']}"
    )
```

#### Box Connector (`connectors/box_connector.py`)

**Add at top:**
```python
# Timeout configuration (for API calls without built-in timeout)
REQUEST_TIMEOUT = 30
MAX_FOLDERS_PER_SYNC = 1000
```

**Add progress tracking:**
```python
# In _sync_folder method
if hasattr(self, '_progress_service') and hasattr(self, '_sync_id'):
    self._progress_service.increment_processed(
        self._sync_id,
        current_item=f"File: {item.name}"
    )
```

### 6. Register SSE Blueprint (`app_v2.py`)

**Add import:**
```python
from api.sync_progress_routes import sync_progress_bp
```

**Register blueprint (after line 78):**
```python
app.register_blueprint(sync_progress_bp)
```

### 7. Frontend Sync Progress Modal

**Create:** `frontend/components/integrations/SyncProgressModal.tsx`

```typescript
'use client'

import React, { useState, useEffect } from 'react'
import { X, CheckCircle, XCircle, Loader2 } from 'lucide-react'

interface SyncProgressModalProps {
  syncId: string
  connectorType: string
  onClose: () => void
}

interface ProgressData {
  sync_id: string
  connector_type: string
  status: 'connecting' | 'syncing' | 'parsing' | 'embedding' | 'complete' | 'error'
  stage: string
  total_items: number
  processed_items: number
  failed_items: number
  current_item?: string
  error_message?: string
  percent_complete: number
}

export default function SyncProgressModal({
  syncId,
  connectorType,
  onClose
}: SyncProgressModalProps) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [eventSource, setEventSource] = useState<EventSource | null>(null)

  useEffect(() => {
    // Connect to SSE stream
    const es = new EventSource(
      `http://localhost:5003/api/sync-progress/${syncId}/stream`,
      { withCredentials: true }
    )

    es.addEventListener('started', (event) => {
      const data = JSON.parse(event.data)
      setProgress(data)
    })

    es.addEventListener('progress', (event) => {
      const data = JSON.parse(event.data)
      setProgress(data)
    })

    es.addEventListener('complete', (event) => {
      const data = JSON.parse(event.data)
      setProgress(data)
      // Auto-close after 3 seconds
      setTimeout(() => {
        es.close()
        onClose()
      }, 3000)
    })

    es.addEventListener('error', (event) => {
      const data = JSON.parse(event.data)
      setProgress(data)
    })

    es.onerror = () => {
      console.error('SSE connection error')
    }

    setEventSource(es)

    return () => {
      es.close()
    }
  }, [syncId, onClose])

  if (!progress) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 max-w-md w-full">
          <div className="flex items-center justify-center">
            <Loader2 className="animate-spin h-8 w-8 text-blue-500" />
          </div>
        </div>
      </div>
    )
  }

  const getStatusIcon = () => {
    if (progress.status === 'complete') {
      return <CheckCircle className="h-12 w-12 text-green-500" />
    } else if (progress.status === 'error') {
      return <XCircle className="h-12 w-12 text-red-500" />
    } else {
      return <Loader2 className="animate-spin h-12 w-12 text-blue-500" />
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">
            Syncing {connectorType.charAt(0).toUpperCase() + connectorType.slice(1)}
          </h2>
          {progress.status === 'complete' || progress.status === 'error' ? (
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="h-5 w-5" />
            </button>
          ) : null}
        </div>

        {/* Status Icon */}
        <div className="flex justify-center mb-4">
          {getStatusIcon()}
        </div>

        {/* Stage */}
        <div className="text-center mb-4">
          <p className="text-lg font-medium text-gray-900">{progress.stage}</p>
          {progress.current_item && (
            <p className="text-sm text-gray-500 mt-1">{progress.current_item}</p>
          )}
        </div>

        {/* Progress Bar */}
        {progress.total_items > 0 && (
          <div className="mb-4">
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${progress.percent_complete}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-sm text-gray-600 mt-2">
              <span>{progress.processed_items} / {progress.total_items}</span>
              <span>{Math.round(progress.percent_complete)}%</span>
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">{progress.total_items}</div>
            <div className="text-xs text-gray-500">Found</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{progress.processed_items}</div>
            <div className="text-xs text-gray-500">Processed</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">{progress.failed_items}</div>
            <div className="text-xs text-gray-500">Failed</div>
          </div>
        </div>

        {/* Error Message */}
        {progress.error_message && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-800">{progress.error_message}</p>
          </div>
        )}

        {/* Success Message */}
        {progress.status === 'complete' && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-sm text-green-800">
              Sync completed successfully! {progress.processed_items} items processed.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
```

**Update Integrations Page to use modal:**
```typescript
import SyncProgressModal from './SyncProgressModal'

// In component state
const [syncId, setSyncId] = useState<string | null>(null)
const [syncingConnector, setSyncingConnector] = useState<string | null>(null)

// In handleSync function
const handleSync = async (connectorType: string) => {
  try {
    const response = await axios.post(
      `${API_BASE}/integrations/${connectorType}/sync`,
      {},
      { headers: authHeaders }
    )

    if (response.data.success && response.data.sync_id) {
      setSyncId(response.data.sync_id)
      setSyncingConnector(connectorType)
    }
  } catch (error) {
    console.error('Sync failed:', error)
  }
}

// In JSX
{syncId && syncingConnector && (
  <SyncProgressModal
    syncId={syncId}
    connectorType={syncingConnector}
    onClose={() => {
      setSyncId(null)
      setSyncingConnector(null)
      // Reload integrations
      loadIntegrations()
    }}
  />
)}
```

---

## 🧪 Testing

### Test Progress Tracking
```bash
# Terminal 1: Start backend
cd backend
python app_v2.py

# Terminal 2: Trigger sync and watch SSE stream
curl -N http://localhost:5003/api/sync-progress/<sync_id>/stream
```

### Test Email Notifications

1. Set up Gmail App Password:
   - Go to https://myaccount.google.com/apppasswords
   - Generate new app password
   - Add to `.env`:
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

2. Trigger sync and check email

### Test Frontend Modal

1. Go to integrations page
2. Click "Sync" on any connector
3. Should see real-time progress modal
4. Should auto-close when complete
5. Should receive email notification

---

## 📊 Benefits

### Before:
- ❌ Sync hangs at 0% forever
- ❌ No idea what's happening
- ❌ No feedback on completion
- ❌ Have to refresh page to see results

### After:
- ✅ Live progress updates
- ✅ See exactly what's being processed
- ✅ Email notification when done
- ✅ Auto-refresh results
- ✅ Graceful timeout handling

---

## 🎯 Next Steps

1. ✅ Create progress tracking service
2. ✅ Create SSE endpoint
3. ✅ Create email service
4. ⚠️ Update connector_manager (IN PROGRESS)
5. ⏳ Add timeouts to all connectors
6. ⏳ Register SSE blueprint
7. ⏳ Create frontend modal
8. ⏳ Test end-to-end

---

**Last Updated:** 2026-01-31
