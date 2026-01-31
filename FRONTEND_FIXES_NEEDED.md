# Frontend Fixes Needed

## Issue 1: Progress Bar Jumping (0 → 80 → 0)

**Problem:** The progress bar shows "23 FOUND, 23 PROCESSED, 0 INDEXED" and jumps around.

**Root Cause:** The status polling is reading intermediate states while the backend is processing.

**Fix Location:** `frontend/components/integrations/WebscraperSync.tsx` (or similar)

**Current Code (problematic):**
```typescript
// Polls every 1 second
useEffect(() => {
  const interval = setInterval(() => {
    fetch(`/api/integrations/webscraper/status?tenant_id=${tenantId}`)
      .then(res => res.json())
      .then(data => {
        setProgress(data);  // Raw data causes jumping
      });
  }, 1000);
}, []);
```

**Fixed Code:**
```typescript
// Improved polling with state stabilization
useEffect(() => {
  let lastStableState = { found: 0, processed: 0, indexed: 0 };

  const interval = setInterval(async () => {
    const res = await fetch(`/api/integrations/webscraper/status`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await res.json();

    // Only update if progress is forward (prevent jumping backwards)
    if (data.processed >= lastStableState.processed) {
      setProgress(data);
      lastStableState = data;
    }

    // Stop polling when complete
    if (data.status === 'completed' || data.status === 'failed') {
      clearInterval(interval);
    }
  }, 2000);  // Reduced frequency to 2 seconds

  return () => clearInterval(interval);
}, []);
```

## Issue 2: Infinite Sync Loop

**Problem:** After sync completes, it starts over again automatically.

**Root Cause:** The frontend keeps polling and re-triggering the sync when it sees certain states.

**Fix Location:** `frontend/components/integrations/WebscraperSync.tsx`

**Fixed Code:**
```typescript
// Add completion tracking
const [syncCompleted, setSyncCompleted] = useState(false);

// In status polling
if (data.status === 'completed') {
  setSyncCompleted(true);
  clearInterval(interval);

  // Show success notification
  toast.success(`Sync complete! ${data.processed} documents processed`);

  // DO NOT automatically restart sync
  // Let user manually trigger next sync
}

// In sync trigger button
const handleSync = async () => {
  if (syncCompleted) {
    // Reset state before new sync
    setSyncCompleted(false);
    setProgress({ found: 0, processed: 0, indexed: 0 });
  }

  // Trigger sync...
};
```

## Issue 3: Documents Not Appearing

**Problem:** 80 documents created by webscraper don't show in Documents page.

**Root Cause:** Frontend is filtering by status that excludes CLASSIFIED documents.

**Fix Location:** `frontend/components/documents/Documents.tsx` (or `app/documents/page.tsx`)

**Current Code (problematic):**
```typescript
// Wrong: filters out CLASSIFIED documents
const { data } = useSWR(
  `/api/documents?status=pending&limit=50`,
  fetcher
);
```

**Fixed Code:**
```typescript
// Correct: Don't filter by status, or include all statuses
const [statusFilter, setStatusFilter] = useState('all');  // Default to 'all'

const { data } = useSWR(
  `/api/documents?${statusFilter !== 'all' ? `status=${statusFilter}&` : ''}limit=50`,
  fetcher
);

// Or fetch both pending AND classified
const { data } = useSWR(
  `/api/documents?limit=50`,  // No status filter = all documents
  fetcher
);
```

## Issue 4: Status XHR Spam

**Problem:** Frontend makes 100+ XHR requests per minute polling status.

**Fix:** Use exponential backoff and longer intervals.

**Fixed Code:**
```typescript
// Exponential backoff polling
const [pollInterval, setPollInterval] = useState(2000);  // Start at 2 seconds

useEffect(() => {
  const interval = setInterval(async () => {
    const res = await fetch('/api/integrations/webscraper/status');
    const data = await res.json();

    setProgress(data);

    // If still processing, increase poll interval gradually
    if (data.status === 'processing') {
      setPollInterval(prev => Math.min(prev * 1.2, 10000));  // Max 10 seconds
    }

    // If completed, stop polling
    if (data.status === 'completed') {
      clearInterval(interval);
    }
  }, pollInterval);

  return () => clearInterval(interval);
}, [pollInterval]);
```

## Issue 5: Better Progress Display

**Problem:** Shows "10% complete" but also "23/23 processed" which is confusing.

**Fixed Display:**
```typescript
// Show clear, consistent progress
<div className="progress-section">
  <div className="progress-bar">
    <div
      className="progress-fill"
      style={{ width: `${progress.percent}%` }}
    />
  </div>

  <div className="progress-stats">
    <span>
      {progress.processed} / {progress.found} documents
      {progress.indexed > 0 && ` (${progress.indexed} indexed)`}
    </span>
    <span className="time-estimate">
      {progress.estimatedTimeRemaining &&
        `~${Math.ceil(progress.estimatedTimeRemaining / 60)} min remaining`
      }
    </span>
  </div>

  <div className="progress-status">
    {progress.currentStep || 'Processing...'}
  </div>
</div>
```

## Quick Fixes Summary

1. **Progress jumping**: Add state stabilization (only forward progress)
2. **Infinite loop**: Add completion tracking, don't auto-restart
3. **Documents hidden**: Remove status filter or default to 'all'
4. **XHR spam**: Use exponential backoff (2s → 10s)
5. **Better UX**: Show clear progress with time estimates

Apply these fixes to the frontend and all issues should be resolved!
