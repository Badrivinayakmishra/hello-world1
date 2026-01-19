# Database Scaling Issues Analysis - 2nd Brain Backend

## Executive Summary
Identified **7 critical database scaling issues** affecting performance:
- **N+1 Query Problems**: Multiple places querying in loops
- **Missing Indexes**: Columns used in WHERE/JOIN clauses without proper indexing
- **Inefficient Bulk Operations**: Sequential processing instead of batch operations
- **Unoptimized Counts**: Multiple count queries instead of aggregation
- **Large Table Scans**: Loading all records without pagination/filtering
- **Suboptimal Connection Management**: Multiple get_db() calls and session handling

---

## 1. N+1 QUERY PROBLEMS

### Issue 1.1: Bulk Classify Loop - Sequential Document Queries
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/document_routes.py`
**Lines**: 255-293

**Problem**: For each document ID in the request, a separate database query is executed in a loop.

```python
for doc_id in document_ids:
    document = db.query(Document).filter(
        Document.id == doc_id,
        Document.tenant_id == g.tenant_id
    ).first()  # ← ONE QUERY PER DOC_ID
    
    if document:
        classification_result = service.classify_document(document)
        # ... update and save
```

**Impact**: With 100 document IDs, this becomes 100 separate database queries.

**Fix**: Fetch all documents at once using `.in_()` operator:
```python
documents = db.query(Document).filter(
    Document.id.in_(document_ids),
    Document.tenant_id == g.tenant_id
).all()
```

---

### Issue 1.2: Bulk Delete Loop - Multiple Nested Queries
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/document_routes.py`
**Lines**: 884-890 (validation) + 912-955 (deletion)

**Problem**: Triple nested query pattern:
1. Lines 884-890: Query each document to validate (1 query per ID)
2. Lines 912-917: Query same documents again (1 query per ID)
3. Lines 924-928: Query DeletedDocument for each document (1 query per ID)

```python
# First loop - validation
for doc_id in document_ids:
    document = db.query(Document).filter(...).first()  # Query 1
    if document:
        valid_doc_ids.append(doc_id)

# Second loop - deletion
for doc_id in document_ids:
    document = db.query(Document).filter(...).first()  # Query 2 (redundant!)
    if document:
        existing = db.query(DeletedDocument).filter(...).first()  # Query 3
```

**Impact**: With 50 document IDs, this is 50 + 50 + 50 = 150 queries.

**Fix**: Fetch once, use in-memory lookups:
```python
doc_map = {doc.id: doc for doc in db.query(Document).filter(
    Document.id.in_(document_ids),
    Document.tenant_id == g.tenant_id
).all()}

deleted_ids = set(d.external_id for d in db.query(DeletedDocument.external_id).filter(...).all())

for doc_id in document_ids:
    document = doc_map.get(doc_id)
    if document and document.external_id not in deleted_ids:
        # process
```

---

### Issue 1.3: Bulk Classification Loop - Sequential Single-Document Queries
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/classification_service.py`
**Lines**: 404-411

**Problem**: Calls `confirm_classification()` in a loop, which queries database individually:

```python
def bulk_confirm(self, document_ids, tenant_id):
    for doc_id in document_ids:
        success, error = self.confirm_classification(doc_id, tenant_id)  # 1 query per ID
        # ...
```

Inside `confirm_classification()` (lines 314-317):
```python
document = self.db.query(Document).filter(
    Document.id == document_id,
    Document.tenant_id == tenant_id
).first()  # ← Individual query
```

**Impact**: N queries for N documents.

**Fix**: Batch fetch then update:
```python
def bulk_confirm(self, document_ids, tenant_id):
    documents = self.db.query(Document).filter(
        Document.id.in_(document_ids),
        Document.tenant_id == tenant_id
    ).all()
    
    for doc in documents:
        doc.user_confirmed = True
        # ...
    self.db.commit()
```

---

### Issue 1.4: Sync Operation - Double Query for Deduplication
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`
**Lines**: 1128-1142

**Problem**: Two separate full-table scans to build deduplication sets:

```python
# Query 1: Get all deleted external_ids
deleted_external_ids = set(
    d.external_id for d in db.query(DeletedDocument.external_id).filter(
        DeletedDocument.tenant_id == tenant_id,
        DeletedDocument.connector_id == connector.id
    ).all()  # ← Full table scan (values only)
)

# Query 2: Get all existing external_ids
existing_external_ids = set(
    d.external_id for d in db.query(Document.external_id).filter(
        Document.tenant_id == tenant_id,
        Document.connector_id == connector.id,
        Document.external_id != None
    ).all()  # ← Another full table scan (values only)
)
```

**Impact**: 
- For large Document/DeletedDocument tables, these queries are expensive
- No indexes on `external_id` column pairs
- Loads entire result set into memory

**Fix**: Use database-level filtering:
```python
# Use NOT EXISTS instead of fetching all IDs
new_docs = [
    doc for doc in documents
    if not db.query(Document).filter(
        Document.external_id == doc.doc_id,
        Document.connector_id == connector.id
    ).exists()
]
```

Or batch insert with ON CONFLICT:
```python
db.bulk_insert_mappings(Document, docs, return_defaults=False)
# Let database handle duplicates via unique constraint
```

---

## 2. MISSING INDEXES

### Issue 2.1: Document.external_id Not Indexed
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`
**Lines**: 385-457

**Problem**: 
- `external_id` is queried in filters (lines 397-398, 456)
- No single column index exists
- Used heavily in sync operations (integration_routes.py:1137, 1148)

**Current Indexes**:
```python
__table_args__ = (
    Index('ix_document_tenant_status', 'tenant_id', 'status'),
    Index('ix_document_tenant_classification', 'tenant_id', 'classification'),
    Index('ix_document_external', 'tenant_id', 'connector_id', 'external_id'),  # Good!
)
```

**Issue**: The composite index `ix_document_external` requires all three columns in the filter. Queries using only `external_id` won't use it efficiently.

**Missing Indexes**:
1. `(external_id)` - For sole lookups
2. `(connector_id, external_id)` - For connector-specific lookups

**Fix**:
```python
__table_args__ = (
    Index('ix_document_tenant_status', 'tenant_id', 'status'),
    Index('ix_document_tenant_classification', 'tenant_id', 'classification'),
    Index('ix_document_external', 'tenant_id', 'connector_id', 'external_id'),
    Index('ix_document_connector_external', 'connector_id', 'external_id'),  # NEW
    Index('ix_document_external_id', 'external_id'),  # NEW
)
```

---

### Issue 2.2: DeletedDocument.external_id Not Properly Indexed
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`
**Lines**: 862-891

**Current Indexes**:
```python
__table_args__ = (
    Index('ix_deleted_doc_lookup', 'tenant_id', 'connector_id', 'external_id'),
    UniqueConstraint('tenant_id', 'connector_id', 'external_id', name='uq_deleted_doc'),
)
```

**Problem**: Query at integration_routes.py:1129 filters by:
```python
DeletedDocument.tenant_id == tenant_id,
DeletedDocument.connector_id == connector.id
```
But then pulls ALL rows into Python to extract `external_id`. This is inefficient for large deleted document lists.

**Missing Indexes**:
1. `(connector_id, external_id)` - For efficient lookups

---

### Issue 2.3: Document.content Not Handled for Full-Text Search
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`
**Line**: 403

**Problem**: Full-text search in document_routes.py:113-115:
```python
query = query.filter(
    db.or_(
        Document.title.ilike(search_pattern),
        Document.content.ilike(search_pattern),  # ← No index!
        Document.sender.ilike(search_pattern)
    )
)
```

- `content` column is `Text` type (very large)
- `ilike()` (case-insensitive LIKE) is slow without indexes
- No GIN or GIST index for full-text search

**Missing Index**:
PostgreSQL GIN index for full-text search:
```python
from sqlalchemy.dialects.postgresql import TSVECTOR, func
content_fts = Column(TSVECTOR, Computed("to_tsvector('english', content)"))
__table_args__ = (
    # ... other indexes
    Index('ix_document_content_fts', content_fts, postgresql_using='gin'),
)
```

---

### Issue 2.4: KnowledgeGap.status Not Indexed
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`
**Line**: 611

**Current**: Only line says `index=True`, but knowledge_routes.py queries heavily by status:

```python
# knowledge_routes.py:1023-1026
open_count = db.query(func.count(KnowledgeGap.id)).filter(
    KnowledgeGap.tenant_id == g.tenant_id,
    KnowledgeGap.status == GapStatus.OPEN  # ← Queries by status
).scalar()
```

**Index exists**: YES, as single column `index=True` on line 611

**Enhancement needed**: Composite index for common queries:
```python
Index('ix_gap_tenant_status', 'tenant_id', 'status'),
```

---

### Issue 2.5: GapAnswer.knowledge_gap_id Not in Composite Index
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`
**Line**: 672

**Current**: Only single column index:
```python
Index('ix_gap_answer_tenant', 'tenant_id'),
```

**Problem**: Knowledge gaps with their answers are fetched together:
```python
# models.py line 635
answers = relationship("GapAnswer", back_populates="knowledge_gap", cascade="all, delete-orphan")
```

When loading a gap and its answers, SQLAlchemy needs to find all `GapAnswer` rows with that `knowledge_gap_id`.

**Missing Index**:
```python
Index('ix_gap_answer_gap_id', 'knowledge_gap_id'),
```

---

### Issue 2.6: User.email Has Index But Lacks Uniqueness Index
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`
**Lines**: 201, 240-243

**Current**:
```python
email = Column(String(320), nullable=False, index=True)
__table_args__ = (
    UniqueConstraint('tenant_id', 'email', name='uq_user_tenant_email'),
    Index('ix_user_email_active', 'email', 'is_active'),
)
```

**Missing**: Single email index is redundant with the composite unique constraint. But queries might use just `email` without `tenant_id` for password reset flows.

**Recommendation**: If password reset uses global email lookup:
```python
Index('ix_user_email', 'email'),  # Keep for non-scoped lookups
```

---

## 3. PAGINATION ISSUES

### Issue 3.1: List Operations Without Proper Pagination Enforcement
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/document_routes.py`
**Line**: 70 & 133

**Current**:
```python
limit = min(int(request.args.get('limit', 50)), 200)
# ...
documents = query.offset(offset).limit(limit).all()
```

**Problem**: 
- Default limit of 50 is reasonable
- Max limit of 200 is acceptable
- BUT: If `offset` is not provided or is 0, first request loads 200 records
- No cursor-based pagination for large datasets

**Secondary Issue**: Line 123 counts BEFORE pagination:
```python
total = query.count()  # Counts ALL matching records
# ...then applies limit
```

For large datasets (10K+ documents), this count operation is expensive on every request.

**Recommendation**: Implement cursor-based pagination or cache counts.

---

### Issue 3.2: Knowledge Gap Statistics Without Pagination
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/knowledge_routes.py`
**Lines**: 1019-1051

**Problem**: Multiple unbounded count queries:

```python
# Line 1019
total = db.query(func.count(KnowledgeGap.id)).filter(
    KnowledgeGap.tenant_id == g.tenant_id
).scalar()

# Line 1023
open_count = db.query(func.count(...)).filter(
    KnowledgeGap.tenant_id == g.tenant_id,
    KnowledgeGap.status == GapStatus.OPEN
).scalar()

# ... 5+ more count queries

# Lines 1047-1052
for category in GapCategory:
    count = db.query(func.count(KnowledgeGap.id)).filter(
        KnowledgeGap.tenant_id == g.tenant_id,
        KnowledgeGap.category == category
    ).scalar()
```

**Impact**: 
- 8+ separate COUNT queries executed sequentially
- For 10K knowledge gaps, each COUNT scans entire table
- 8 COUNT = potential 8x slower than single aggregation query

**Fix**:
```python
stats = db.query(
    func.count(KnowledgeGap.id).label('total'),
    func.sum(case((KnowledgeGap.status == GapStatus.OPEN, 1))).label('open'),
    func.sum(case((KnowledgeGap.category == GapCategory.DECISION, 1))).label('decision'),
    # ... all categories
).filter(
    KnowledgeGap.tenant_id == g.tenant_id
).first()
```

---

## 4. LARGE TABLE SCANS

### Issue 4.1: Delete All Documents Without Cursor Pagination
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/document_routes.py`
**Lines**: 994-1028

**Problem**:
```python
@document_bp.route('/all', methods=['DELETE'])
def delete_all_documents():
    deleted_count = db.query(Document).filter(
        Document.tenant_id == g.tenant_id
    ).delete()  # ← Deletes all at once
    db.commit()
```

**Issues**:
1. No pagination/batching of deletes
2. Locks entire Document table during deletion
3. Generates massive rollback log if any error occurs
4. Cascade deletes on DocumentChunk happen one-by-one in loop (N+1)

**Impact**: Deleting 100K documents locks database for 30+ seconds.

**Fix**: Batch delete with chunking:
```python
batch_size = 1000
while True:
    ids = db.query(Document.id).filter(
        Document.tenant_id == g.tenant_id
    ).limit(batch_size).all()
    
    if not ids:
        break
    
    db.query(Document).filter(
        Document.id.in_([id[0] for id in ids])
    ).delete()
    db.commit()
```

---

### Issue 4.2: Loading Full Documents for Sync Without Selective Columns
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`
**Lines**: 1206-1217

**Problem**:
```python
doc_ids = [db_doc.id for db_doc in db.query(Document).filter(
    Document.tenant_id == tenant_id,
    Document.connector_id == connector.id,
    Document.embedded_at == None
).all()]  # ← Loads ENTIRE Document objects

if doc_ids:
    docs_to_embed = db.query(Document).filter(
        Document.id.in_(doc_ids),
        Document.tenant_id == tenant_id
    ).all()  # ← ANOTHER full load with all columns including `content` (LARGE!)
```

**Impact**: 
- Large `content` field loaded even though only `id` needed
- 2 queries instead of 1
- Memory bloat with large documents

**Fix**:
```python
docs_to_embed = db.query(Document).filter(
    Document.tenant_id == tenant_id,
    Document.connector_id == connector.id,
    Document.embedded_at == None
).all()
# Use single query, select only needed columns if possible
```

---

## 5. CONNECTION POOLING & SESSION MANAGEMENT

### Issue 5.1: Multiple get_db() Calls per Request
**File**: Multiple API route files

**Pattern Found**:
```python
# document_routes.py - typical pattern
def list_documents():
    db = get_db()  # Gets from SessionLocal
    try:
        # ... use db
    finally:
        db.close()

def get_document(document_id):
    db = get_db()  # New session created
    try:
        # ... use db
    finally:
        db.close()
```

**Issue**: Each route gets its own database session, but:
1. **Pool efficiency**: SQLAlchemy creates new connections even if one is available
2. **Connection state**: Each session maintains separate connection
3. **Resource leak**: If exception before `db.close()`, connection not returned

**Current Pool Config** (models.py:838-843):
```python
engine = create_engine(
    get_database_url(),
    echo=False,
    pool_pre_ping=True,  # Good - validates before use
    pool_recycle=3600,   # Good - recycles after 1 hour
)
```

**Missing**:
```python
engine = create_engine(
    get_database_url(),
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=20,              # ← MISSING: Connection pool size
    max_overflow=40,           # ← MISSING: Max overflow connections
    pool_timeout=30,           # ← MISSING: Timeout for getting connection
)
```

**Recommendation**:
```python
engine = create_engine(
    get_database_url(),
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,              # Normal connections
    max_overflow=5,            # Emergency overflow
    pool_timeout=30,
    connect_args={'timeout': 10, 'connect_timeout': 10}
)
```

---

### Issue 5.2: Missing Explicit Transaction Management
**File**: Multiple service files

**Pattern**: 
```python
def bulk_confirm(self, document_ids, tenant_id):
    for doc_id in document_ids:
        success, error = self.confirm_classification(doc_id, tenant_id)
        # Each call commits independently
```

**Problem**: 
- Nested transactions can cause issues
- No rollback of entire batch if partial failure occurs
- Each operation commits immediately (AUTOCOMMIT mode)

**Recommendation**: Use explicit transactions:
```python
try:
    for doc in documents:
        # ... updates
    db.commit()  # Single commit
except:
    db.rollback()
    raise
```

---

## 6. SUBOPTIMAL QUERY PATTERNS

### Issue 6.1: Count Then Load Pattern
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/document_routes.py`
**Lines**: 123 & 133

**Pattern**:
```python
total = query.count()  # Query 1
# ... apply sorting ...
documents = query.offset(offset).limit(limit).all()  # Query 2
```

**Problem**: Two separate queries where one would suffice.

**Fix**:
```python
query_for_count = query  # Save before modifications
# Apply sorting/pagination
documents = query.offset(offset).limit(limit).all()
total = query_for_count.count()  # Or cache this value
```

---

### Issue 6.2: In-Memory Filtering Instead of Database Filtering
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`
**Lines**: 1146-1151

**Pattern**:
```python
documents = [
    doc for doc in (documents or [])
    if doc.doc_id not in deleted_external_ids 
    and doc.doc_id not in existing_external_ids
]
```

**Problem**: 
- Filtering happens AFTER data is loaded from connector
- This is acceptable for external data
- But then same external_ids loaded from database (lines 1128-1142)

**Recommendation**: Let database handle filtering:
```python
# Combine both checks in database query
new_documents = [doc for doc in connector_docs if not db.session.query(Document).filter(
    Document.external_id == doc.external_id
).exists()]
```

---

## SUMMARY TABLE

| Issue | Severity | Type | Location | Impact |
|-------|----------|------|----------|--------|
| Bulk classify loop N+1 | Critical | Query | doc_routes.py:255-293 | 100 queries → 1 |
| Bulk delete nested loops | Critical | Query | doc_routes.py:884-955 | 150 queries → 1 |
| Bulk confirm N+1 | Critical | Query | classification_service.py:404-411 | N queries → 1 |
| Sync dedup double query | High | Query | integration_routes.py:1128-1142 | 2 table scans → 1 |
| Missing external_id indexes | High | Index | models.py:385-457 | Slow sync operations |
| Multiple COUNT queries | High | Query | knowledge_routes.py:1019-1051 | 8 queries → 1 |
| Delete all without batching | High | Query | doc_routes.py:994-1028 | Table lock 30+ sec |
| Missing pool config | Medium | Pool | models.py:838-843 | Connection exhaustion |
| Missing text search index | Medium | Index | models.py:403 | Slow search queries |
| Count before paginate | Medium | Query | doc_routes.py:123 | Unnecessary full scan |

