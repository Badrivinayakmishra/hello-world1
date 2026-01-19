# Database Scaling Issues - Quick Fix Guide

## Priority 1: Critical N+1 Issues (Fix First)

### Fix 1.1: Bulk Classify Documents (doc_routes.py:255-293)

**BEFORE** (150+ queries):
```python
for doc_id in document_ids:
    document = db.query(Document).filter(
        Document.id == doc_id,
        Document.tenant_id == g.tenant_id
    ).first()
    if document:
        # process one document
        classification_result = service.classify_document(document)
        # ... update
```

**AFTER** (1 query):
```python
# Fetch all documents at once
documents = db.query(Document).filter(
    Document.id.in_(document_ids),
    Document.tenant_id == g.tenant_id
).all()

doc_map = {doc.id: doc for doc in documents}

for doc_id in document_ids:
    document = doc_map.get(doc_id)
    if document:
        classification_result = service.classify_document(document)
        # ... update

db.commit()  # Single commit for all
```

**Estimated improvement**: 100 queries → 1 query (100x faster)

---

### Fix 1.2: Bulk Delete Documents (doc_routes.py:884-955)

**BEFORE** (150 queries):
```python
# Loop 1: Validation (N queries)
for doc_id in document_ids:
    document = db.query(Document).filter(...).first()
    if document:
        valid_doc_ids.append(doc_id)

# Loop 2: Deletion (N queries)
for doc_id in document_ids:
    document = db.query(Document).filter(...).first()  # Redundant!
    # ...check deleted documents (N more queries)
    existing = db.query(DeletedDocument).filter(...).first()
```

**AFTER** (2-3 queries total):
```python
# Single fetch
documents = db.query(Document).filter(
    Document.id.in_(document_ids),
    Document.tenant_id == g.tenant_id
).all()

doc_map = {doc.id: doc for doc in documents}

# Single deleted docs fetch
deleted_docs = db.query(DeletedDocument).filter(
    DeletedDocument.connector_id == connector_id,
    DeletedDocument.external_id.in_([
        doc.external_id for doc in documents 
        if doc.external_id
    ])
).all()

deleted_ids = {d.external_id for d in deleted_docs}

# Single loop for processing
for doc_id in document_ids:
    document = doc_map.get(doc_id)
    if document:
        if hard_delete and document.external_id not in deleted_ids:
            # Track deletion
            pass
        # Delete
```

**Estimated improvement**: 150 queries → 2-3 queries (50x faster)

---

### Fix 1.3: Bulk Confirm Classifications (classification_service.py:404-411)

**BEFORE**:
```python
def bulk_confirm(self, document_ids, tenant_id):
    for doc_id in document_ids:
        success, error = self.confirm_classification(doc_id, tenant_id)
        # Each call = 1 query
```

**AFTER**:
```python
def bulk_confirm(self, document_ids, tenant_id):
    # Batch fetch
    documents = self.db.query(Document).filter(
        Document.id.in_(document_ids),
        Document.tenant_id == tenant_id
    ).all()
    
    # Batch update
    for doc in documents:
        doc.user_confirmed = True
        doc.user_confirmed_at = utc_now()
        doc.status = DocumentStatus.CONFIRMED
    
    self.db.commit()  # Single commit
    
    return {
        "confirmed": len(documents),
        "not_found": len(document_ids) - len(documents),
        "errors": []
    }
```

**Estimated improvement**: N queries → 1 query

---

## Priority 2: Missing Indexes (Add These)

### Add Indexes to Document Model

**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`

Find the `Document` class `__table_args__` (around line 453) and replace:

```python
__table_args__ = (
    Index('ix_document_tenant_status', 'tenant_id', 'status'),
    Index('ix_document_tenant_classification', 'tenant_id', 'classification'),
    Index('ix_document_external', 'tenant_id', 'connector_id', 'external_id'),
    # ADD THESE THREE:
    Index('ix_document_connector_external', 'connector_id', 'external_id'),
    Index('ix_document_external_id', 'external_id'),
    Index('ix_document_title', 'title'),
)
```

### Add Indexes to KnowledgeGap Model

Find `KnowledgeGap` class around line 596 and add after `status` column:

```python
__table_args__ = (
    # NEW: Composite index for common queries
    Index('ix_gap_tenant_status', 'tenant_id', 'status'),
    Index('ix_gap_tenant_category', 'tenant_id', 'category'),
)
```

### Add Index to GapAnswer Model

Find `GapAnswer` class around line 702 and update:

```python
__table_args__ = (
    Index('ix_gap_answer_tenant', 'tenant_id'),
    Index('ix_gap_answer_gap_id', 'knowledge_gap_id'),  # NEW
)
```

### Add Index to DeletedDocument Model

Find `DeletedDocument` class around line 884 and update:

```python
__table_args__ = (
    Index('ix_deleted_doc_lookup', 'tenant_id', 'connector_id', 'external_id'),
    Index('ix_deleted_doc_connector', 'connector_id', 'external_id'),  # NEW
    UniqueConstraint('tenant_id', 'connector_id', 'external_id', name='uq_deleted_doc'),
)
```

---

## Priority 3: Connection Pool Configuration

**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`

Find the `engine = create_engine()` call (around line 838) and update:

```python
engine = create_engine(
    get_database_url(),
    echo=False,
    pool_pre_ping=True,      # Keep: validates connections
    pool_recycle=3600,       # Keep: recycles after 1 hour
    # ADD THESE:
    pool_size=10,            # Number of persistent connections
    max_overflow=5,          # Max temporary connections
    pool_timeout=30,         # Timeout waiting for connection
    connect_args={
        'timeout': 10,
        'connect_timeout': 10,
        'server_settings': {
            'jit': 'off',   # Disable JIT for predictable perf
            'statement_timeout': '30s'
        }
    }
)
```

---

## Priority 4: Aggregation Query Fixes

### Fix Knowledge Gap Statistics (knowledge_routes.py:1019-1051)

**BEFORE** (8+ COUNT queries):
```python
total = db.query(func.count(KnowledgeGap.id)).filter(
    KnowledgeGap.tenant_id == g.tenant_id
).scalar()

open_count = db.query(func.count(KnowledgeGap.id)).filter(
    KnowledgeGap.tenant_id == g.tenant_id,
    KnowledgeGap.status == GapStatus.OPEN
).scalar()

# ... 6 more similar queries
```

**AFTER** (1 aggregation query):
```python
from sqlalchemy import case

stats = db.query(
    func.count(KnowledgeGap.id).label('total'),
    func.sum(case((KnowledgeGap.status == GapStatus.OPEN, 1), else_=0)).label('open'),
    func.sum(case((GapStatus.CLOSED, 1), else_=0)).label('closed'),
    func.sum(case((KnowledgeGap.category == GapCategory.DECISION, 1), else_=0)).label('decision'),
    func.sum(case((KnowledgeGap.category == GapCategory.TECHNICAL, 1), else_=0)).label('technical'),
    func.sum(case((KnowledgeGap.category == GapCategory.PROCESS, 1), else_=0)).label('process'),
    func.sum(case((KnowledgeGap.category == GapCategory.CONTEXT, 1), else_=0)).label('context'),
    func.sum(case((KnowledgeGap.category == GapCategory.RELATIONSHIP, 1), else_=0)).label('relationship'),
    func.sum(case((KnowledgeGap.category == GapCategory.TIMELINE, 1), else_=0)).label('timeline'),
).filter(
    KnowledgeGap.tenant_id == g.tenant_id
).first()

return jsonify({
    "success": True,
    "stats": {
        "total_gaps": stats.total or 0,
        "open_gaps": stats.open or 0,
        "closed_gaps": stats.closed or 0,
        "by_category": {
            "decision": stats.decision or 0,
            "technical": stats.technical or 0,
            # ... rest of categories
        }
    }
})
```

**Estimated improvement**: 8 queries → 1 query (8x faster)

---

## Priority 5: Batch Delete with Pagination

### Fix Delete All Documents (doc_routes.py:994-1028)

**BEFORE**:
```python
def delete_all_documents():
    deleted_count = db.query(Document).filter(
        Document.tenant_id == g.tenant_id
    ).delete()  # Locks entire table!
    db.commit()
```

**AFTER** (Batch deletion):
```python
def delete_all_documents():
    batch_size = 1000
    total_deleted = 0
    
    while True:
        # Get IDs to delete
        ids_to_delete = db.query(Document.id).filter(
            Document.tenant_id == g.tenant_id
        ).limit(batch_size).all()
        
        if not ids_to_delete:
            break
        
        id_list = [id[0] for id in ids_to_delete]
        
        # Delete embeddings first
        embedding_service = get_embedding_service()
        embedding_service.delete_document_embeddings(
            document_ids=id_list,
            tenant_id=g.tenant_id,
            db=db
        )
        
        # Delete from database
        deleted = db.query(Document).filter(
            Document.id.in_(id_list)
        ).delete()
        
        db.commit()
        total_deleted += deleted
        
        if deleted < batch_size:
            break
    
    return jsonify({
        "success": True,
        "deleted_count": total_deleted
    })
```

**Estimated improvement**: Single lock for 30+ seconds → Multiple small locks (total 2-3 seconds)

---

## Priority 6: Sync Deduplication Optimization

### Fix Sync Deduplication (integration_routes.py:1128-1142)

**BEFORE** (2 full table scans):
```python
deleted_external_ids = set(
    d.external_id for d in db.query(DeletedDocument.external_id).filter(...).all()
)

existing_external_ids = set(
    d.external_id for d in db.query(Document.external_id).filter(...).all()
)

documents = [
    doc for doc in (documents or [])
    if doc.doc_id not in deleted_external_ids 
    and doc.doc_id not in existing_external_ids
]
```

**AFTER** (Single query + EXISTS):
```python
# Filter out deleted and existing in database
new_documents = []
for doc in (documents or []):
    # Check if already exists
    exists = db.query(
        db.literal(True)
    ).filter(
        Document.external_id == doc.doc_id,
        Document.connector_id == connector.id,
        Document.tenant_id == tenant_id
    ).first()
    
    if not exists:
        new_documents.append(doc)

# Or use NOT EXISTS (more efficient):
# See SQLAlchemy docs for: Query.filter(~exists(...))
```

---

## Testing Commands

After applying fixes, verify with:

```bash
# 1. Check indexes were created
psql $DATABASE_URL -c "\di+" | grep document

# 2. Check query performance (enable query logging)
# In models.py, change echo=False to echo=True and run test

# 3. Monitor connection pool
# In logs, look for: "QueuePool timeout" errors (means pool too small)

# 4. Run slow query log
psql $DATABASE_URL -c "ALTER SYSTEM SET log_min_duration_statement = 1000;"
psql $DATABASE_URL -c "SELECT pg_reload_conf();"
```

---

## Rollback Plan

If changes cause issues:

1. **Indexes**: Can be dropped without data loss
   ```sql
   DROP INDEX CONCURRENTLY ix_document_external_id;
   ```

2. **Connection pool**: Restart application to reload config

3. **Query changes**: Revert code changes to previous version

---

## Monitoring After Fixes

Add these metrics:

```python
import time
from functools import wraps

def monitor_query_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        if duration > 1.0:  # Log slow queries
            print(f"SLOW: {func.__name__} took {duration:.2f}s")
        return result
    return wrapper
```

Apply to:
- `bulk_classify()` - should be < 5s for 100 docs
- `bulk_delete()` - should be < 10s for 1000 docs
- `get_gap_stats()` - should be < 1s

---

## Estimated Performance Gains

| Fix | Before | After | Gain |
|-----|--------|-------|------|
| Bulk Classify | 100 queries | 1 query | 100x |
| Bulk Delete | 150 queries | 3 queries | 50x |
| Knowledge Gap Stats | 8 queries | 1 query | 8x |
| Add Indexes | Table scans | Index seeks | 5-10x |
| Connection Pool | Exhaustion risk | Stable | ∞ |

**Total estimated improvement**: 10-50x faster for bulk operations
