# TENANT ISOLATION SECURITY ANALYSIS REPORT
## 2nd Brain Application - Multi-Tenant Data Security Assessment

**Date:** January 6, 2026  
**Scope:** Authentication, Database Models, API Endpoints, Data Access Patterns  
**Severity Assessment:** CRITICAL & HIGH PRIORITY ISSUES FOUND

---

## EXECUTIVE SUMMARY

The 2nd Brain application implements a multi-tenant architecture with tenant-aware database models and API endpoints. The implementation demonstrates **GOOD general security practices** but contains **ONE CRITICAL VULNERABILITY** and several **HIGH-PRIORITY CONCERNS** that could allow unauthorized cross-tenant data access.

**Critical Finding:** Unfiltered document query at integration_routes.py:1160 allows bypassing tenant isolation when fetching documents for embedding.

---

## 1. AUTHENTICATION & TENANT IDENTIFICATION

### 1.1 Authentication Mechanism

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/services/auth_service.py`

**How it works:**
- Users authenticate via email/password at login endpoint
- JWT access token is generated containing:
  - `sub` (user_id)
  - `tenant_id` (organization ID)
  - `email`
  - `role`
  - `jti` (JWT ID for token revocation)
  - `exp` (expiration)

**Token Generation (Lines 145-178):**
```python
@classmethod
def create_access_token(
    cls,
    user_id: str,
    tenant_id: str,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, datetime, str]:
    jti = generate_uuid()
    now = utc_now()
    if expires_delta:
        expires_at = now + expires_delta
    else:
        expires_at = now + timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRES)

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,  # KEY: tenant_id embedded in JWT
        "email": email,
        "role": role,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
        "type": "access"
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
```

**Assessment:** GOOD - Tenant ID is embedded in JWT token and properly encoded.

### 1.2 Tenant ID Derivation

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/services/auth_service.py` (Lines 841-865)

**Decorator: `@require_auth`**
```python
def require_auth(f):
    """Decorator for requiring authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_header(request.headers.get("Authorization", ""))
        if not token:
            return jsonify({"error": "Missing authorization token"}), 401

        payload, error = JWTUtils.decode_access_token(token)
        if error:
            return jsonify({"error": error}), 401

        # Store user info in Flask g object
        g.user_id = payload.get("sub")
        g.tenant_id = payload.get("tenant_id")  # Extracted from token
        g.email = payload.get("email")
        g.role = payload.get("role")

        return f(*args, **kwargs)

    return decorated
```

**Key Points:**
- `tenant_id` is extracted from JWT token payload (trusted source)
- Stored in Flask's `g` object for request scope
- Cannot be spoofed or modified by client (signed JWT)
- Tied to user login via user record

**Assessment:** EXCELLENT - Tenant ID is derived from signed JWT token and cannot be tampered with by client.

### 1.3 User-Tenant Relationship

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py` (Lines 190-265)

```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    
    # ... other fields ...
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'email', name='uq_user_tenant_email'),
        Index('ix_user_email_active', 'email', 'is_active'),
    )
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
```

**Assessment:** EXCELLENT - Each user is tightly bound to a single tenant via foreign key constraint. Email is unique per tenant, not globally.

---

## 2. DATABASE MODELS & TENANT FILTERING

### 2.1 Models with Tenant ID

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`

The following models properly include `tenant_id` field:

| Model | Tenant ID | Type | Status |
|-------|-----------|------|--------|
| **Tenant** | N/A (is tenant) | Parent | OK |
| **User** | Line 198 | FK to Tenant | OK |
| **Connector** | Line 315 | FK to Tenant | OK |
| **Document** | Line 393 | FK to Tenant | OK |
| **Project** | Line 542 | FK to Tenant | OK |
| **KnowledgeGap** | Line 597 | FK to Tenant | OK |
| **Video** | Line 728 | FK to Tenant | OK |
| **AuditLog** | Line 796 | FK to Tenant (optional) | OK |
| **DeletedDocument** | Line 862 | FK to Tenant | OK |

### 2.2 Models Missing Tenant ID

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`

The following models are **MISSING** explicit `tenant_id` field:

| Model | Issue | Impact | Status |
|-------|-------|--------|--------|
| **DocumentChunk** | No tenant_id | **MEDIUM** - Relies on parent Document | ⚠️ CONCERN |
| **UserSession** | No tenant_id | **LOW** - Looks up via User relation | OK |
| **GapAnswer** | No tenant_id | **MEDIUM** - Relies on KnowledgeGap | ⚠️ CONCERN |

**Assessment:**
- DocumentChunk (Line 493-528): No direct tenant_id. Requires join through Document to verify tenant ownership.
- GapAnswer (Line 662-713): No direct tenant_id. Requires join through KnowledgeGap to verify tenant ownership.
- These are acceptable if code always validates parent object's tenant_id (see findings below).

### 2.3 Relationship Structures

All primary models have proper cascade relationships:

```python
# Example from Tenant model (Line 133-169)
class Tenant(Base):
    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
    connectors = relationship("Connector", back_populates="tenant", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="tenant", cascade="all, delete-orphan")
    knowledge_gaps = relationship("KnowledgeGap", back_populates="tenant", cascade="all, delete-orphan")
    videos = relationship("Video", back_populates="tenant", cascade="all, delete-orphan")
```

**Assessment:** EXCELLENT - All relationships use cascade delete to ensure orphaned data cleanup.

---

## 3. API ENDPOINTS SECURITY

### 3.1 Endpoints with Proper Tenant Filtering

**✅ GOOD (Consistent tenant filtering):**

| Endpoint | File | Line | Filtering |
|----------|------|------|-----------|
| GET /api/documents | document_routes.py | 76-77 | `Document.tenant_id == g.tenant_id` |
| GET /api/documents/<id> | document_routes.py | 175-177 | `Document.tenant_id == g.tenant_id` |
| POST /api/documents/classify | document_routes.py | 256-258 | `Document.tenant_id == g.tenant_id` |
| GET /api/integrations | integration_routes.py | 65-66 | `Connector.tenant_id == g.tenant_id` |
| GET /api/knowledge-gaps | knowledge_routes.py | 341 | `KnowledgeGap.tenant_id == g.tenant_id` |
| GET /api/videos | video_routes.py | 261-263 | `Video.tenant_id == g.tenant_id` |

All major endpoints consistently apply `g.tenant_id` filter.

### 3.2 ⚠️ CRITICAL VULNERABILITY FOUND

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`  
**Lines:** 1160-1162  
**Severity:** CRITICAL

**Vulnerable Code:**
```python
# Line 1152-1162
doc_ids = [db_doc.id for db_doc in db.query(Document).filter(
    Document.tenant_id == tenant_id,      # Line 1153 - properly filtered
    Document.connector_id == connector.id,  # Line 1154
    Document.embedded_at == None           # Line 1155
).all()]

if doc_ids:
    # Get fresh document objects
    docs_to_embed = db.query(Document).filter(
        Document.id.in_(doc_ids)  # ⚠️ LINE 1161 - MISSING TENANT FILTER!
    ).all()
```

**Issue:**
- First query properly filters by `tenant_id`
- Extracts document IDs
- **Second query uses only `.in_(doc_ids)` without tenant_id check**
- If attacker somehow modifies doc_ids or SQLi, they could fetch documents from ANY tenant

**Attack Scenario:**
1. Attacker intercepts the sync process or API call
2. Modifies doc_ids list to include documents from other tenants
3. Second query retrieves those documents without tenant verification
4. Documents are embedded, and metadata is exposed

**Impact:**
- **Data Confidentiality Breach:** Unauthorized access to other tenants' documents
- **Information Disclosure:** Document content can be exposed through embeddings
- **Cross-Tenant Data Leakage:** Metadata, summaries, or embeddings may be processed/stored

**Recommendation:**
```python
# CORRECT: Add tenant filter to second query
docs_to_embed = db.query(Document).filter(
    Document.id.in_(doc_ids),
    Document.tenant_id == tenant_id  # ADD THIS LINE
).all()
```

### 3.3 ⚠️ HIGH-PRIORITY FINDINGS

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/services/knowledge_service.py`

**Issue 1: GapAnswer retrieval (Lines 1464-1466)**

```python
def get_answers(
    self,
    gap_id: str,
    tenant_id: str
) -> List[GapAnswer]:
    """Get all answers for a knowledge gap."""
    # Verify gap belongs to tenant
    gap = self.db.query(KnowledgeGap).filter(
        KnowledgeGap.id == gap_id,
        KnowledgeGap.tenant_id == tenant_id
    ).first()

    if not gap:
        return []

    return self.db.query(GapAnswer).filter(
        GapAnswer.knowledge_gap_id == gap_id  # ← Indirect tenant verification
    ).order_by(GapAnswer.question_index).all()
```

**Assessment:** ACCEPTABLE - Gap verification ensures tenant isolation through parent record check. However, **better practice** would be:
```python
return self.db.query(GapAnswer).join(KnowledgeGap).filter(
    GapAnswer.knowledge_gap_id == gap_id,
    KnowledgeGap.tenant_id == tenant_id
).order_by(GapAnswer.question_index).all()
```

**Issue 2: Document query patterns (embedding_service.py:195)**

```python
query = db.query(Document).filter(
    Document.tenant_id == tenant_id,
    Document.is_deleted == False,
    Document.content != None,
    Document.content != ''
)
```

**Assessment:** GOOD - Properly filters by tenant_id.

### 3.4 Endpoint Authentication Status

**Checked:** All API endpoints in the following files:
- `auth_routes.py` (15 endpoints)
- `document_routes.py` (12 endpoints)
- `integration_routes.py` (20+ endpoints)
- `knowledge_routes.py` (15+ endpoints)
- `video_routes.py` (8 endpoints)

**Result:** ✅ All endpoints use `@require_auth` decorator except:
- `POST /api/auth/signup` - Intentionally public
- `POST /api/auth/login` - Intentionally public
- `POST /api/auth/refresh` - Uses refresh token (OK)

---

## 4. DATA ACCESS PATTERNS & QUERY ANALYSIS

### 4.1 Systematic Query Review

**Methodology:** Searched all database queries for proper tenant filtering.

**Query Pattern Audit Results:**

| Pattern | Count | Status |
|---------|-------|--------|
| `query(Document).filter(...tenant_id...)` | 15+ | ✅ OK |
| `query(KnowledgeGap).filter(...tenant_id...)` | 12+ | ✅ OK |
| `query(Video).filter(...tenant_id...)` | 8+ | ✅ OK |
| `query(Project).filter(...tenant_id...)` | 5+ | ✅ OK |
| `query(Connector).filter(...tenant_id...)` | 10+ | ✅ OK |
| Queries with potential issues | 1 | ⚠️ CRITICAL |

### 4.2 SQL Injection & Tenant Bypass Risks

**Good News:**
- Application uses SQLAlchemy ORM (parameterized queries)
- No raw SQL strings found
- No `format()` or f-string SQL concatenation
- Input validation present in routes

**Risk Assessment:**
- **SQL Injection Risk:** MINIMAL (ORM protects against this)
- **Tenant Bypass via SQL:** Only through the vulnerability at integration_routes.py:1160

### 4.3 Bulk Operations Audit

**DELETE Operations:**
```python
# document_routes.py:1010-1012
deleted_count = db.query(Document).filter(
    Document.tenant_id == g.tenant_id  # ✅ Properly filtered
).delete()
```

**UPDATE Operations:**
- All updates filter by tenant_id (e.g., classification_service.py:314-317)

---

## 5. DETAILED FINDINGS SUMMARY

### CRITICAL ISSUES (Fix Immediately)

#### Finding #1: Missing Tenant Filter in Document Embedding Query

**Severity:** CRITICAL  
**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`  
**Lines:** 1160-1162  
**CWE:** CWE-284 (Improper Access Control), CWE-639 (Authorization Bypass)

**Vulnerable Code:**
```python
1152    doc_ids = [db_doc.id for db_doc in db.query(Document).filter(
1153        Document.tenant_id == tenant_id,
1154        Document.connector_id == connector.id,
1155        Document.embedded_at == None
1156    ).all()]
1157
1158    if doc_ids:
1159        # Get fresh document objects
1160        docs_to_embed = db.query(Document).filter(
1161            Document.id.in_(doc_ids)  # ⚠️ MISSING TENANT FILTER
1162        ).all()
```

**Risk:** Attacker could potentially access and process documents from other tenants during the embedding phase.

**Fix:**
```python
docs_to_embed = db.query(Document).filter(
    Document.id.in_(doc_ids),
    Document.tenant_id == tenant_id  # ADD THIS
).all()
```

---

### HIGH-PRIORITY ISSUES (Fix Soon)

#### Finding #2: DocumentChunk and GapAnswer Lack Direct Tenant ID Field

**Severity:** HIGH  
**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py`

**Model: DocumentChunk (Lines 493-528)**
```python
class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    # ⚠️ No tenant_id field - relies on Document relationship
```

**Model: GapAnswer (Lines 662-713)**
```python
class GapAnswer(Base):
    __tablename__ = "gap_answers"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    knowledge_gap_id = Column(String(36), ForeignKey("knowledge_gaps.id"), nullable=False, index=True)
    # ⚠️ No tenant_id field - relies on KnowledgeGap relationship
```

**Impact:**
- Queries must always join parent table to verify tenant
- Risk of accidental cross-tenant access if developer forgets parent check
- Slightly worse query performance (requires join)

**Recommendation:**
Add explicit tenant_id to both models:
```python
# DocumentChunk
tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

# GapAnswer  
tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
# or denormalize via KnowledgeGap join
```

#### Finding #3: No Tenant Verification in UserSession Queries

**Severity:** HIGH  
**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/api/auth_routes.py` (Lines 586-590)

```python
sessions = db.query(UserSession).filter(
    UserSession.user_id == g.user_id,
    UserSession.is_revoked == False,
    UserSession.expires_at > db.func.now()
).order_by(UserSession.last_used_at.desc()).all()
```

**Issue:** While `user_id` is tenant-specific, there's no explicit tenant_id verification.

**Risk:** If `user_id` could be guessed/brute-forced, attacker might access another user's sessions.

**Assessment:** MITIGATED by:
- user_id is UUID (cryptographically random)
- User lookup requires email + password
- But better practice would add tenant check

---

### MEDIUM-PRIORITY ISSUES (Recommended)

#### Finding #4: Inconsistent Tenant Passing in Service Methods

**Severity:** MEDIUM  
**Files:** Multiple service files

**Pattern:**
```python
# Some methods take tenant_id explicitly
def classify_pending_documents(self, tenant_id: str, limit: int = 50) -> Dict:
    
# While others rely on context
def classify_document(self, document: Document) -> ClassificationResult:
    # No tenant_id passed!
```

**Risk:** Human error - easy to forget tenant filtering when document object is passed without verification.

**Recommendation:** Always pass tenant_id explicitly to service methods.

#### Finding #5: Soft-Deleted Documents Not Isolated

**Severity:** MEDIUM  
**File:** database/models.py (Lines 444-445)

```python
class Document(Base):
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))
```

**Pattern:** Deleted documents are soft-deleted but still in database. Most queries filter `is_deleted == False`, but some might not.

**Risk:** Accidental exposure of soft-deleted tenant data.

**Recommendation:** Make soft-deletion filtering mandatory in base query functions.

---

### LOW-PRIORITY ISSUES (Nice-to-Have)

#### Finding #6: Audit Logging

**Severity:** LOW  
**File:** database/models.py (Lines 788-822)

```python
class AuditLog(Base):
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    # ⚠️ tenant_id is nullable!
```

**Impact:** Some audit logs might not have tenant context.

**Recommendation:** Make tenant_id NOT NULL for most audit logs.

#### Finding #7: Rate Limiting by IP, Not Tenant

**Severity:** LOW  
**File:** auth/auth0_handler.py (Lines 337-357)

```python
def rate_limit(self, key_func: Callable = None) -> Callable:
    if key_func:
        key = key_func()
    else:
        key = request.remote_addr  # ⚠️ IP-based, not tenant-based
```

**Impact:** No per-tenant rate limiting.

**Recommendation:** Add tenant-aware rate limiting.

---

## 6. SECURITY POSTURE SUMMARY

### What's Working Well ✅

| Area | Status |
|------|--------|
| JWT Authentication | Excellent |
| Tenant ID in Token | Excellent |
| User-Tenant Binding | Excellent |
| Cascade Deletes | Excellent |
| ORM Usage | Excellent |
| Most API Endpoints | Good |
| Role-Based Access | Good |
| Session Management | Good |

### Critical Gaps ⚠️

| Area | Status | Priority |
|------|--------|----------|
| Document Embedding Query | **CRITICAL** | **IMMEDIATE** |
| DocumentChunk/GapAnswer tenant_id | HIGH | SOON |
| UserSession tenant verification | HIGH | SOON |
| Tenant passing consistency | MEDIUM | SOON |
| Soft-delete filtering | MEDIUM | SOON |

---

## 7. RECOMMENDATIONS

### Immediate Actions (This Week)

1. **Fix integration_routes.py:1160** - Add tenant_id filter to document query
   ```python
   docs_to_embed = db.query(Document).filter(
       Document.id.in_(doc_ids),
       Document.tenant_id == tenant_id
   ).all()
   ```

2. **Add integration tests** for cross-tenant isolation:
   ```python
   def test_user_cannot_access_other_tenant_documents():
       # Create 2 tenants with users
       # Verify user1 cannot fetch user2's documents
   ```

### Short-Term Actions (This Sprint)

3. **Add tenant_id to DocumentChunk model** (Migration required)
   - Add column with default
   - Backfill existing records
   - Add foreign key constraint
   
4. **Add tenant_id to GapAnswer model** (Migration required)
   - Same as above

5. **Implement tenant-aware base query filters:**
   ```python
   class TenantAwareQuery:
       @staticmethod
       def get_documents(db, tenant_id):
           return db.query(Document).filter(Document.tenant_id == tenant_id)
   ```

### Medium-Term Actions (Next Sprint)

6. **Establish query review process:**
   - All queries must explicitly filter by tenant_id
   - Code review checklist for tenant isolation
   - Automated linting/scanning

7. **Add tenant verification middleware:**
   ```python
   @app.before_request
   def verify_request_tenant():
       if not hasattr(g, 'tenant_id'):
           return error, 401
   ```

8. **Implement comprehensive audit logging:**
   - All data access logged with tenant_id
   - Bi-weekly audit log review
   - Alerts for cross-tenant queries

### Testing Requirements

- [ ] Unit tests for each endpoint with multiple tenants
- [ ] Integration tests for data isolation
- [ ] Security regression tests
- [ ] Tenant boundary tests for all services
- [ ] SQL injection testing
- [ ] JWT token manipulation testing

---

## 8. COMPLIANCE & STANDARDS

**Applicable Standards:**
- OWASP Top 10: A01:2021 – Broken Access Control
- CWE-284: Improper Access Control
- CWE-639: Authorization Bypass Through User-Controlled Key
- SOC 2: Access Controls
- GDPR: Data Isolation Requirements

**Current Status:**
- ✅ Most controls implemented
- ⚠️ Critical gaps in document embedding
- ⚠️ Gaps in tenant filtering consistency

---

## CONCLUSION

The 2nd Brain application demonstrates **solid multi-tenant architecture** with proper JWT authentication, tenant-aware database models, and consistent API endpoint filtering. However, **ONE CRITICAL VULNERABILITY** in the document embedding flow (integration_routes.py:1160) must be fixed immediately, along with several **HIGH-PRIORITY architectural improvements** to prevent accidental cross-tenant data access.

**Risk Rating:** 🔴 **HIGH** (due to critical vulnerability)  
**Recommended Action:** Fix critical issue immediately, implement recommendations within 2 sprints.

---

## APPENDIX: Detailed Code References

### Files Analyzed
- `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py` (914 lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/auth/auth0_handler.py` (371 lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/services/auth_service.py` (881 lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/api/auth_routes.py` (665 lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/api/document_routes.py` (1029 lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py` (1500+ lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/api/knowledge_routes.py` (1050+ lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/api/video_routes.py` (480+ lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/services/knowledge_service.py` (2000+ lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/services/classification_service.py` (540 lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/services/embedding_service.py` (350+ lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/services/extraction_service.py` (318 lines)
- `/Users/rishitjain/Downloads/2nd-brain/backend/services/video_service.py` (807 lines)

### Total Code Reviewed: ~10,000+ lines of Python

---

**Report Generated:** 2026-01-06  
**Reviewed By:** Security Analysis Tool  
**Status:** COMPLETE
