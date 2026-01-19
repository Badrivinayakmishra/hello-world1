# Connector/Integration Isolation Security Analysis

## Executive Summary
This codebase implements **multi-tenant connector isolation with critical security vulnerabilities** in credential storage and state management. OAuth tokens are stored in plaintext in the database without encryption, and OAuth state is stored in an in-memory dictionary vulnerable to race conditions and replay attacks.

---

## 1. CREDENTIALS STORAGE & ENCRYPTION

### Critical Finding: Plaintext Token Storage

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py` (Lines 326-330)

```python
# OAuth credentials (encrypted in production)
access_token = Column(Text)  # Should be encrypted
refresh_token = Column(Text)  # Should be encrypted
token_expires_at = Column(DateTime(timezone=True))
token_scopes = Column(JSON, default=list)
```

**Security Issue:** 
- OAuth tokens stored as plaintext in database
- Comment indicates "should be encrypted" but NOT implemented
- Violates OWASP Top 10 - A02:2021 Cryptographic Failures
- No encryption-at-rest implementation

**Risk Level:** CRITICAL

**Affected Connectors:**
- Gmail (lines 250, 264, 837)
- Slack (lines 522, 654, 836)
- Box (lines 779, 792, 837)

**Example from Gmail OAuth Callback:**
```python
# File: integration_routes.py, lines 249-255
connector.access_token = tokens["access_token"]
connector.refresh_token = tokens["refresh_token"]
connector.status = ConnectorStatus.CONNECTED
# ... no encryption before DB insertion
```

### Recommended Fix:
Implement field-level encryption using cryptography library:
```python
from cryptography.fernet import Fernet

class Connector(Base):
    _encrypted_access_token = Column(Text)
    _encrypted_refresh_token = Column(Text)
    
    @property
    def access_token(self):
        if self._encrypted_access_token:
            cipher = Fernet(ENCRYPTION_KEY)
            return cipher.decrypt(self._encrypted_access_token).decode()
        return None
    
    @access_token.setter
    def access_token(self, value):
        if value:
            cipher = Fernet(ENCRYPTION_KEY)
            self._encrypted_access_token = cipher.encrypt(value.encode())
```

---

## 2. OAUTH TOKEN ISOLATION BY TENANT

### Positive Finding: Tenant-Based Token Storage

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py` (Lines 314-316)

```python
id = Column(String(36), primary_key=True, default=generate_uuid)
tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
user_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # Null = org-wide
```

**Implementation Details:**
- Each Connector record has `tenant_id` foreign key (REQUIRED, not nullable)
- Index on `tenant_id` for efficient filtering: `Index('ix_connector_tenant_type', 'tenant_id', 'connector_type')`

**Verification in Routes:**
File: `integration_routes.py` shows proper tenant isolation checks:

```python
# Line 65-68: List integrations only for current tenant
connectors = db.query(Connector).filter(
    Connector.tenant_id == g.tenant_id,  # ✓ Tenant filter
    Connector.is_active == True
).all()

# Line 243-245: Gmail callback - uses state_data["tenant_id"]
connector = db.query(Connector).filter(
    Connector.tenant_id == state_data["tenant_id"],  # ✓ Tenant from OAuth state
    Connector.connector_type == ConnectorType.GMAIL
).first()
```

**Token Isolation Status:** ✓ CORRECTLY IMPLEMENTED FOR TENANTS

Each tenant's connectors are isolated at the database level with foreign key constraints.

---

## 3. CROSS-TENANT ACCESS VULNERABILITIES

### Critical Finding: OAuth State Dictionary Vulnerability

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py` (Line 26)

```python
# ============================================================================
# OAuth state storage (use Redis in production)
# ============================================================================
oauth_states = {}  # CRITICAL: In-memory, unencrypted, server process scope
```

**Vulnerabilities:**

#### A. In-Memory State Storage (Race Conditions)
- Stored in server process memory
- No persistence across multiple workers/processes
- Race condition: State could be popped by wrong user in concurrent requests

Example scenario:
```
User A initiates Gmail OAuth → state "abc123" stored
User B initiates Gmail OAuth → state "def456" stored
User A completes callback first → pops state "abc123"
User B completes callback → gets "def456"
Both complete successfully if timing aligns
```

#### B. State Reuse Vulnerability (CSRF)
**File:** `integration_routes.py`, Lines 226-228 (Gmail callback)

```python
state_data = oauth_states.pop(state, None)
if not state_data or state_data["type"] != "gmail":
    return redirect("/integrations?error=invalid_state")
```

**Issue:** 
- State only validated to exist and match type
- No tenant_id validation in callback function itself
- State stored WITHOUT timestamp
- No rate limiting on callback attempts

Attack scenario:
```
1. Attacker initiates OAuth as Tenant A
2. Obtains authorization code from OAuth provider
3. Submits code to Tenant B's callback
4. If state checking is weak, code might be accepted for Tenant B
```

#### C. No State Expiration
**File:** `integration_routes.py`, Line 179-185 (Gmail auth)

```python
oauth_states[state] = {
    "type": "gmail",
    "tenant_id": g.tenant_id,
    "user_id": g.user_id,
    "redirect_uri": redirect_uri,
    "created_at": utc_now().isoformat()  # Timestamp stored but NOT CHECKED
}
```

The `created_at` timestamp is stored but never validated on callback. No cleanup of old states.

### Recommended Fixes:

1. **Use Redis instead of in-memory dict:**
```python
import redis
oauth_redis = redis.Redis(host='localhost', port=6379, db=1)

def gmail_auth():
    state = secrets.token_urlsafe(32)
    state_data = {
        "type": "gmail",
        "tenant_id": g.tenant_id,
        "user_id": g.user_id,
        "created_at": utc_now().isoformat()
    }
    # Expires in 10 minutes
    oauth_redis.setex(f"oauth_state:{state}", 600, json.dumps(state_data))
```

2. **Validate state on callback:**
```python
def gmail_callback():
    state = request.args.get('state')
    state_json = oauth_redis.get(f"oauth_state:{state}")
    if not state_json:
        return redirect("/integrations?error=invalid_state")
    
    state_data = json.loads(state_json)
    
    # Critical: Verify tenant_id matches current request
    if state_data["tenant_id"] != g.tenant_id:
        return redirect("/integrations?error=invalid_state")  # CSRF attempt
    
    oauth_redis.delete(f"oauth_state:{state}")  # One-time use
```

---

## 4. SYNCED DOCUMENT TENANT ATTRIBUTION

### Positive Finding: Documents Properly Attributed

**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/database/models.py` (Lines 392-394)

```python
id = Column(String(36), primary_key=True, default=generate_uuid)
tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
connector_id = Column(String(36), ForeignKey("connectors.id"), nullable=True)
```

**Implementation in Sync Process:**
File: `integration_routes.py`, Lines 1120-1133

```python
for i, doc in enumerate(documents):
    db_doc = Document(
        tenant_id=tenant_id,        # ✓ From request context (g.tenant_id)
        connector_id=connector.id,  # ✓ Verified connector belongs to tenant
        external_id=doc.doc_id,
        source_type=doc.source,
        title=doc.title,
        content=doc.content,
        metadata=doc.metadata,
        sender=doc.author,
        source_created_at=doc.timestamp,
        source_updated_at=doc.timestamp,
        status=DocumentStatus.PENDING,
        classification=DocumentClassification.UNKNOWN
    )
    db.add(db_doc)
```

**Verification Flow:**
1. Sync triggered with `@require_auth` decorator → ensures `g.tenant_id` is set
2. Connector queried with `Connector.tenant_id == g.tenant_id` filter (line 933-936)
3. All synced documents created with same `tenant_id` (line 1121)

**Document Isolation Status:** ✓ CORRECTLY IMPLEMENTED

---

## 5. CONNECTOR QUERIES - TENANT ISOLATION VERIFICATION

### Checked: All Integration Routes Properly Filter by Tenant

| Route | File:Lines | Tenant Check | Status |
|-------|-----------|--------------|--------|
| List integrations | `integration_routes.py:65` | `Connector.tenant_id == g.tenant_id` | ✓ |
| Gmail auth | `integration_routes.py:181` | Stored in state_data | ✓ |
| Gmail callback | `integration_routes.py:244` | Uses state_data["tenant_id"] | ✓ |
| Slack auth | `integration_routes.py:298` | Stored in state_data | ✓ |
| Slack callback | `integration_routes.py:628` | Uses state_data["tenant_id"] | ✓ |
| Slack channels | `integration_routes.py:363` | `Connector.tenant_id == g.tenant_id` | ✓ |
| Box auth | `integration_routes.py:704` | Stored in state_data | ✓ |
| Box callback | `integration_routes.py:774` | Uses state_data["tenant_id"] | ✓ |
| Box folders | `integration_routes.py:820` | `Connector.tenant_id == g.tenant_id` | ✓ |
| Connector status | `integration_routes.py:1416` | `Connector.tenant_id == g.tenant_id` | ✓ |
| Disconnect | `integration_routes.py:1353` | `Connector.tenant_id == g.tenant_id` | ✓ |

**All routes use `@require_auth` decorator which sets `g.tenant_id` (auth_service.py:859)**

---

## 6. ADDITIONAL SECURITY FINDINGS

### Finding 1: Token Refresh Logic Vulnerability

**File:** `integration_routes.py`, Lines 777-783 (Box callback example)

```python
if connector:
    connector.access_token = tokens["access_token"]
    connector.refresh_token = tokens["refresh_token"]
    connector.status = ConnectorStatus.CONNECTED
    connector.is_active = True  # Re-enable connector on reconnect
    connector.error_message = None
```

**Issue:** 
- No token expiry check before using refresh token
- No automatic token refresh during sync
- Tokens can be expired but still marked as CONNECTED

**File:** `connectors/gmail_connector.py`, Lines 93-101

```python
credentials = Credentials(
    token=self.config.credentials.get("access_token"),
    refresh_token=self.config.credentials.get("refresh_token"),
    # ... no auto-refresh configuration
)
```

### Finding 2: Missing Encryption for Sensitive Settings

**File:** `database/models.py`, Line 333

```python
settings = Column(JSON, default=dict)  # E.g., labels, channels, repos
```

Settings may contain:
- Private channel IDs
- Specific folder paths
- Query patterns
- Not encrypted

### Finding 3: Connector to_dict() Exposure Risk

**File:** `database/models.py`, Lines 361-378

```python
def to_dict(self, include_tokens: bool = False) -> Dict[str, Any]:
    data = {
        "id": self.id,
        "tenant_id": self.tenant_id,
        # ... fields
    }
    if include_tokens:
        data["has_access_token"] = bool(self.access_token)
        data["has_refresh_token"] = bool(self.refresh_token)
        # Safe: only returns boolean existence
```

**Status:** ✓ SAFE - Implementation correctly uses boolean instead of actual tokens

However, check all usages:
- `integration_routes.py:1431` - called with `include_tokens=False` ✓

### Finding 4: OAuth Client Credentials in Environment

**File:** `connectors/gmail_connector.py`, Lines 56-66

```python
@classmethod
def _get_client_config(cls) -> Dict:
    import os
    return {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", "YOUR_CLIENT_ID.apps.googleusercontent.com"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "YOUR_CLIENT_SECRET"),
            # ...
        }
    }
```

**Issue:** 
- OAuth client secrets in environment variables (acceptable practice)
- BUT default values shown in source code are template values, not real secrets
- **Status:** ✓ ACCEPTABLE (environment-based, not hardcoded)

---

## 7. DELETED DOCUMENT TRACKING

### Finding: Deleted Documents Properly Attributed

**File:** `database/models.py`, Lines 862-863

```python
tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
connector_id = Column(String(36), ForeignKey("connectors.id"), nullable=True)
```

**Usage in sync:**
File: `integration_routes.py`, Lines 1074-1079

```python
deleted_external_ids = set(
    d.external_id for d in db.query(DeletedDocument.external_id).filter(
        DeletedDocument.tenant_id == tenant_id,  # ✓ Tenant filter
        DeletedDocument.connector_id == connector.id  # ✓ Connector filter
    ).all()
)
```

**Status:** ✓ CORRECTLY IMPLEMENTED

---

## RISK SUMMARY TABLE

| Category | Finding | Severity | Status |
|----------|---------|----------|--------|
| Token Storage | Plaintext in DB | CRITICAL | UNFIXED |
| Token Encryption | No encryption at rest | CRITICAL | UNFIXED |
| OAuth State | In-memory dict | HIGH | UNFIXED |
| State Expiration | No TTL validation | MEDIUM | UNFIXED |
| Cross-Tenant Isolation | Properly filtered queries | ✓ SECURE | IMPLEMENTED |
| Document Attribution | Tenant-scoped | ✓ SECURE | IMPLEMENTED |
| Deleted Docs Tracking | Tenant-scoped | ✓ SECURE | IMPLEMENTED |
| Token Refresh Logic | No expiry check | MEDIUM | UNFIXED |
| Connector Settings | JSON plaintext | LOW | UNFIXED |

---

## RECOMMENDED REMEDIATION ROADMAP

### Immediate (Critical)
1. Implement field-level encryption for access_token and refresh_token
2. Move oauth_states to Redis with 10-minute expiration
3. Add tenant_id validation in all OAuth callbacks

### Short-term (High)
4. Implement automatic token refresh checking before sync
5. Add rate limiting to OAuth callback endpoints
6. Encrypt sensitive connector settings (JSON fields)

### Medium-term (Medium)
7. Implement token rotation (revoke old token on new auth)
8. Add webhook support for token expiration notifications
9. Create audit logging for all token operations

### Long-term (Enhancement)
10. Implement OAuth 2.0 PKCE for public clients
11. Add IP whitelisting for OAuth callbacks
12. Implement hardware security module (HSM) for key storage

---

## COMPLIANCE NOTES

- **OWASP A02:2021:** Cryptographic Failures - Token storage is plaintext
- **GDPR Article 32:** Encryption of personal data not implemented
- **SOC 2:** Encryption at rest requirement not met
- **CWE-312:** Cleartext Storage of Sensitive Information

---

