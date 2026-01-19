# API Scaling Issues - Quick Reference Sheet

## Critical Issues (Must Fix)

### 1. No Rate Limiting (CRITICAL)
- **Location:** All API routes
- **Risk:** Brute force attacks, DoS, resource exhaustion
- **Files Affected:** `auth_routes.py`, `integration_routes.py`
- **Exposed Endpoints:** `/api/auth/login`, `/api/auth/signup`, `/api/integrations/*/sync`
- **Fix:** Add `Flask-Limiter` decorator to all public endpoints

### 2. Knowledge Gap Answers - Unbounded List (HIGH)
- **Location:** `knowledge_routes.py`, line 323-366
- **Endpoint:** `GET /api/knowledge/gaps/<gap_id>`
- **Problem:** Returns ALL answers without pagination
- **Example:** 1000 answers with transcriptions = 50MB+ response
- **Fix:** Add `limit` and `offset` query parameters
```python
# Before
answers = service.get_answers(gap_id, g.tenant_id)
answers_dict = [a.to_dict() for a in answers]

# After
limit = min(int(request.args.get('limit', 20)), 100)
offset = int(request.args.get('offset', 0))
answers = service.get_answers(gap_id, g.tenant_id, limit=limit, offset=offset)
```

### 3. Document Content in List View (HIGH)
- **Location:** `document_routes.py`, line 137
- **Endpoint:** `GET /api/documents`
- **Problem:** Serializes full `content` field for every document in list
- **Example:** 50 documents × 100KB = 5MB+ uncompressed response
- **Fix:** Add `fields` parameter or use list-specific serializer
```python
# Before
"documents": [doc.to_dict() for doc in documents]

# After
fields = request.args.get('fields', 'basic').split(',')
"documents": [doc.to_dict(fields=fields) for doc in documents]
# Returns only: id, title, status, created_at (not content)
```

### 4. No Gzip Compression (HIGH)
- **Location:** Flask app initialization (not in routes)
- **Impact:** 5MB responses sent as-is instead of 500KB gzipped
- **Fix:** Install and enable Flask-Compress
```python
# In main app.py
from flask_compress import Compress
Compress(app)
```

---

## High Priority Issues

### 5. Box Folder Recursion - Unbounded Depth (HIGH)
- **Location:** `integration_routes.py`, line 862-933
- **Endpoint:** `GET /api/integrations/box/folders`
- **Problem:** `depth` parameter has no maximum
- **Risk:** Exponential fetch with `depth=10+` could retrieve millions of items
- **Fix:** Cap depth parameter
```python
# Before
depth = int(request.args.get('depth', '2'))

# After
depth = min(int(request.args.get('depth', '2')), 4)  # Max 4 levels
```

### 6. Threading Without Limits (HIGH)
- **Location:** `integration_routes.py`, line 1012-1023 and `video_routes.py`, line 475-481
- **Problem:** Each sync/regenerate creates new thread, no pool
- **Risk:** 100 sync requests = 100 threads = OOM/crash
- **Fix:** Use ThreadPoolExecutor or Celery
```python
# Before
thread = threading.Thread(target=run_sync)
thread.start()

# After
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=5)
executor.submit(run_sync)
```

### 7. Memory-Based Progress Tracking (MEDIUM)
- **Location:** `integration_routes.py`, line 83
- **Problem:** `sync_progress = {}` global dict
- **Risk:** Not persistent, lost on restart, memory leak if sync hangs
- **Fix:** Move to Redis or database
```python
# Recommended: Use Redis
import redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)
redis_client.setex(progress_key, 3600, json.dumps(progress_data))
```

### 8. Slack Channels - Hardcoded Limit (MEDIUM)
- **Location:** `integration_routes.py`, line 404-476
- **Endpoint:** `GET /api/integrations/slack/channels`
- **Problem:** Hardcoded `limit=200`, no pagination cursor
- **Risk:** Workspaces with 200+ channels get incomplete list
- **Fix:** Implement cursor-based pagination
```python
# Before
"limit": 200

# After
cursor = request.args.get('cursor', '')
limit = 100
response = requests.get(..., params={"limit": limit, "cursor": cursor})
```

---

## Medium Priority Issues

### 9. Full Object Serialization in Updates (MEDIUM)
- **Location:** Multiple endpoints
- **Examples:**
  - `knowledge_routes.py:831-899` - `PUT /gaps/<id>/status`
  - `integration_routes.py:1503-1572` - `PUT /integrations/*/settings`
  - `document_routes.py:505-569` - `POST /documents/bulk/confirm`
- **Problem:** Returns entire object when only updating 1 field
- **Fix:** Return only updated fields
```python
# Before
return jsonify({"success": True, "gap": gap.to_dict()})

# After
return jsonify({"success": True, "id": gap.id, "status": gap.status.value})
```

### 10. N+1 Query Problem (MEDIUM)
- **Location:** `document_routes.py`, line 672-732
- **Endpoint:** `GET /api/documents/review`
- **Problem:** Each `doc.to_dict()` may trigger relation queries
- **Risk:** 50 documents = 50+ database queries
- **Fix:** Use eager loading
```python
# Before
documents, total = service.get_documents_for_review(...)
"documents": [doc.to_dict() for doc in documents]

# After (in service)
from sqlalchemy.orm import joinedload
documents = db.query(Document).options(
    joinedload(Document.connector),
    joinedload(Document.classifications)
).filter(...).all()
```

### 11. Unbounded Full-Text Search (MEDIUM)
- **Location:** `document_routes.py`, line 109-117
- **Endpoint:** `GET /api/documents?search=...`
- **Problem:** Searches entire `content` field with LIKE queries
- **Risk:** Full table scan on large content columns
- **Fix:** Use dedicated search engine or indexed search
```python
# Option 1: Add database index
# CREATE INDEX idx_document_content ON documents USING FULLTEXT(content);

# Option 2: Use Elasticsearch
from elasticsearch import Elasticsearch
es = Elasticsearch()
results = es.search(index="documents", body={"query": {"match": {"content": search}}})
```

### 12. Enum Serialization Overhead (LOW)
- **Location:** `integration_routes.py`, line 137, 152, 167, etc.
- **Problem:** Repeated `status.value` conversions in list endpoint
- **Fix:** Cache or batch conversion
```python
# Before
"status": gmail.status.value if gmail else "not_configured"

# After
status_values = {connector.id: connector.status.value for connector in connectors}
"status": status_values.get(gmail.id, "not_configured")
```

---

## Recommended Implementation Order

### Week 1 (Quick Wins)
1. Add Flask-Limiter rate limiting (1 hour)
2. Enable Flask-Compress gzip (30 min)
3. Add max depth to Box folders (15 min)
4. Cap Slack channel limit with cursor pagination (1 hour)
5. Add limits to knowledge gap answers (1 hour)

### Week 2 (Medium Effort)
6. Separate list/detail serialization for documents (2 hours)
7. Replace threading with ThreadPoolExecutor (2 hours)
8. Add database indexes for search (1 hour)
9. Implement eager loading for relations (2 hours)
10. Add field selection parameters (2 hours)

### Week 3+ (Longer Term)
11. Migrate sync progress to Redis (1 hour)
12. Consider Elasticsearch for full-text search (3-4 hours)
13. Plan Celery migration for background jobs (2-3 days)
14. Consider async framework (FastAPI) long-term

---

## Testing Checklist

After implementing fixes, test:

- [ ] Rate limiting blocks >X requests/second
- [ ] Gzip compression reduces response size 80%+
- [ ] Pagination prevents >10MB responses
- [ ] Box folder fetch completes in <5 seconds
- [ ] Thread count stays <20 even with 100 concurrent syncs
- [ ] Database queries for list view = 1-2, not N+1
- [ ] Search queries use indexes (check EXPLAIN plan)
- [ ] Video/sync progress persists across restarts
- [ ] Memory usage stays constant with 1000+ items

---

## Monitoring to Add

```python
# Add metrics for:
1. Response size distribution (p50, p95, p99)
2. Query counts per endpoint
3. Active thread/connection pools
4. Gzip compression ratio
5. Rate limiting hit rate
6. Search query latency
7. Memory usage growth over time
```

