# Scaling Issues - Implementation Fix Guide

## Quick Reference: Top 10 Critical Locations

| Priority | Issue | File | Lines | Fix | Effort |
|----------|-------|------|-------|-----|--------|
| P0 | OAuth state dict | api/integration_routes.py | 80 | Redis + JWT | 4h |
| P0 | Sync progress dict | api/integration_routes.py | 83 | Redis backend | 3h |
| P1 | Tenant RAG globals | app_universal.py | 71-99 | Request-scoped cache | 8h |
| P1 | Parser singleton | services/document_parser.py | 422-436 | Config factory | 3h |
| P1 | Embedding cache | services/enhanced_search_service.py | 507, 512-532 | Redis cache | 5h |
| P2 | Entity normalizer cache | services/intelligent_gap_detector.py | 463-464 | Redis + TTL | 4h |
| P2 | Knowledge graph | services/intelligent_gap_detector.py | 1163-1164 | Database store | 10h |
| P2 | Claims verifier | services/intelligent_gap_detector.py | 1403 | Request-scoped | 2h |
| P3 | Frame extraction memoization | services/intelligent_gap_detector.py | 658-682 | @lru_cache | 2h |
| P3 | Embedding eviction | services/enhanced_search_service.py | 526-530 | ThreadSafeDict | 2h |

**Total Effort**: ~43 hours = 1 person-week

---

## P0: CRITICAL - OAuth State Management

### Problem
Global `oauth_states` dict breaks with multiple instances. Instance 1 creates state, Instance 2 receives callback.

### Current Code
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`

```python
# LINE 80
oauth_states = {}  # CRITICAL FLAW

# LINE 233 - Gmail
oauth_states[state] = {
    "type": "gmail",
    "tenant_id": g.tenant_id,
    "user_id": g.user_id,
    # ...
}

# LINE 280 - Gmail callback
state_data = oauth_states.pop(state, None)  # Fails if wrong instance
```

### Fix Strategy
Use Redis for distributed state with JWT fallback:

```python
import redis
from datetime import timedelta
import jwt
import os

# Initialize Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

# Option 1: JWT-based (stateless, preferred)
def create_oauth_state_jwt(tenant_id: str, user_id: str, connector_type: str) -> str:
    """Create signed OAuth state token"""
    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "connector_type": connector_type,
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.utcnow() + timedelta(minutes=10)
    }
    token = jwt.encode(
        payload,
        os.getenv("JWT_SECRET_KEY"),
        algorithm="HS256"
    )
    return token

def verify_oauth_state_jwt(state: str) -> tuple:
    """Verify JWT state"""
    try:
        payload = jwt.decode(
            state,
            os.getenv("JWT_SECRET_KEY"),
            algorithms=["HS256"]
        )
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "OAuth state expired"
    except jwt.InvalidTokenError:
        return None, "Invalid OAuth state"

# Option 2: Redis fallback (if JWT not available)
def create_oauth_state_redis(tenant_id: str, user_id: str, connector_type: str) -> str:
    """Create OAuth state with Redis backend"""
    state = secrets.token_urlsafe(32)
    redis_key = f"oauth:state:{state}"
    
    redis_client.setex(
        redis_key,
        timedelta(minutes=10),
        json.dumps({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "connector_type": connector_type,
        })
    )
    return state

def verify_oauth_state_redis(state: str) -> tuple:
    """Verify OAuth state from Redis"""
    redis_key = f"oauth:state:{state}"
    data = redis_client.get(redis_key)
    
    if not data:
        return None, "Invalid or expired OAuth state"
    
    redis_client.delete(redis_key)  # One-time use
    return json.loads(data), None
```

### Implementation Steps
1. **Add Redis dependency**: `pip install redis`
2. **Update integrations blueprint**:
   - Remove `oauth_states = {}` (line 80)
   - Replace `oauth_states[state] = {...}` with JWT creation
   - Replace `oauth_states.pop(state, None)` with JWT verification
3. **Test**:
   ```bash
   # Test multi-instance scenario
   # Start 2 instances on different ports
   # Auth on instance 1, verify callback on instance 2
   ```

### Files to Modify
- **Primary**: `api/integration_routes.py` (lines 80, 233, 280, 350, 645, 813, 1315)
- **Support**: Create `services/oauth_service.py` with JWT/Redis helpers

---

## P0: CRITICAL - Sync Progress Tracking

### Problem
`sync_progress` dict only visible on instance that's running sync.

### Current Code
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`

```python
# LINE 83
sync_progress = {}  # CRITICAL

# LINE 1054 - During sync
sync_progress[progress_key] = {
    "status": "syncing",
    "progress": 5,
    # ...
}

# LINE 1315 - Status polling
if progress_key not in sync_progress:
    # No progress tracking if queried on different instance
```

### Fix Strategy
Move to Redis with compound keys:

```python
def get_sync_progress(tenant_id: str, connector_type: str) -> dict:
    """Get sync progress from Redis"""
    key = f"sync:progress:{tenant_id}:{connector_type}"
    data = redis_client.get(key)
    
    if not data:
        return {
            "status": "idle",
            "progress": 0,
            "documents_found": 0,
        }
    
    return json.loads(data)

def update_sync_progress(tenant_id: str, connector_type: str, progress: dict):
    """Update sync progress in Redis"""
    key = f"sync:progress:{tenant_id}:{connector_type}"
    
    # Set with 24-hour TTL (clear old progress after a day)
    redis_client.setex(
        key,
        timedelta(hours=24),
        json.dumps(progress)
    )

def start_sync_job(tenant_id: str, connector_type: str, connector_id: str):
    """Create Redis-backed sync job"""
    job_key = f"sync:job:{tenant_id}:{connector_type}"
    
    redis_client.setex(
        job_key,
        timedelta(hours=24),
        json.dumps({
            "connector_id": connector_id,
            "started_at": datetime.utcnow().isoformat(),
            "status": "PENDING"
        })
    )
```

### Implementation Steps
1. **Update `_run_connector_sync()`** (line 1041):
   - Replace `sync_progress[progress_key] = {...}` with `update_sync_progress()`
   - Wrap operations in try/except with Redis failure fallback
   
2. **Update `get_sync_status()`** (line 1295):
   - Replace dict lookup with `get_sync_progress()`

3. **Add job queue**: Use Redis LIST for queuing:
   ```python
   def queue_sync_job(tenant_id: str, connector_type: str):
       redis_client.rpush(f"sync:queue", json.dumps({
           "tenant_id": tenant_id,
           "connector_type": connector_type,
           "queued_at": datetime.utcnow().isoformat()
       }))
   ```

### Files to Modify
- **Primary**: `api/integration_routes.py` (lines 83, 1041-1063, 1295-1315)
- **Support**: `services/sync_service.py` (new file with helpers)

---

## P1: HIGH - Tenant RAG Instance Caching

### Problem
Global variables load entire tenant RAG into memory. 10 tenants = 4GB per instance.

### Current Code
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/app_universal.py`

```python
# LINES 70-99
tenant_rag_instances = {}      # Unbounded growth
tenant_data_loaded = {}        # Tracking dict

search_index = None            # Single-tenant globals
embedding_index = None
knowledge_gaps = None
user_spaces = None
kb_metadata = None
enhanced_rag = None
stakeholder_graph = None
connector_manager = None
document_manager = None
```

### Fix Strategy
Convert to request-scoped loading with database-backed caching:

```python
from functools import lru_cache
from flask import g
import pickle
import hashlib

class TenantRAGCache:
    """Database-backed tenant RAG cache with LRU fallback"""
    
    def __init__(self, db_path: str = "tenant_cache.db"):
        self.db_path = db_path
        self._in_memory_cache = {}  # LRU for hot tenants
        self._max_in_memory = 3  # Only 3 tenants in memory
    
    def get(self, tenant_id: str, component: str):
        """Get component (e.g., 'search_index') for tenant"""
        
        # Check in-memory first
        key = (tenant_id, component)
        if key in self._in_memory_cache:
            return self._in_memory_cache[key]
        
        # Try database
        db_key = f"{tenant_id}:{component}"
        cached_data = self._load_from_db(db_key)
        
        if cached_data:
            # Restore to memory (with LRU eviction)
            if len(self._in_memory_cache) >= self._max_in_memory:
                # Evict oldest
                oldest_key = next(iter(self._in_memory_cache))
                del self._in_memory_cache[oldest_key]
            
            self._in_memory_cache[key] = cached_data
            return cached_data
        
        return None
    
    def set(self, tenant_id: str, component: str, data):
        """Cache component for tenant"""
        key = (tenant_id, component)
        self._in_memory_cache[key] = data
        
        # Also persist to DB
        db_key = f"{tenant_id}:{component}"
        self._save_to_db(db_key, data)
    
    def clear_tenant(self, tenant_id: str):
        """Clear all components for tenant"""
        keys_to_remove = [k for k in self._in_memory_cache if k[0] == tenant_id]
        for k in keys_to_remove:
            del self._in_memory_cache[k]
        
        # Clear from DB
        # ... database cleanup ...

# Global cache (not the data itself, just the cache manager)
tenant_rag_cache = TenantRAGCache()

# Use in routes:
def get_tenant_search_index():
    """Get search index for current tenant (request-scoped)"""
    tenant_id = g.tenant_id
    
    component = tenant_rag_cache.get(tenant_id, "search_index")
    if component is None:
        # Load from source (database, files, etc.)
        component = _load_search_index_from_source(tenant_id)
        tenant_rag_cache.set(tenant_id, "search_index", component)
    
    return component

def _load_search_index_from_source(tenant_id: str):
    """Load search index from persistent source"""
    # Load from database table: tenant_components
    # OR load from S3 / file system
    # This ensures actual data is never in memory long-term
    pass
```

### Implementation Steps
1. **Create database schema** (if using SQL):
   ```sql
   CREATE TABLE tenant_components (
       id UUID PRIMARY KEY,
       tenant_id VARCHAR(100) NOT NULL,
       component_name VARCHAR(50) NOT NULL,
       component_data BYTEA,  -- Pickled Python object
       cached_at TIMESTAMP,
       expires_at TIMESTAMP,
       UNIQUE(tenant_id, component_name)
   );
   ```

2. **Replace global variable access**:
   - Remove lines 91-99 from `app_universal.py`
   - Create getter functions: `get_tenant_search_index()`, etc.
   - Use `@lru_cache(maxsize=3)` for hot tenants

3. **Update all routes**:
   - Before: `search_index.search(...)`
   - After: `get_tenant_search_index().search(...)`

### Files to Modify
- **Primary**: `app_universal.py` (lines 70-99)
- **New**: `services/tenant_rag_cache.py` (cache manager)
- **Update**: All routes that access global variables

---

## P1: HIGH - Document Parser Singleton

### Problem
Config changes only affect one instance.

### Current Code
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/document_parser.py`

```python
# LINES 421-436
_parser_instance: Optional[DocumentParser] = None

def get_document_parser(force_new: bool = False) -> DocumentParser:
    global _parser_instance
    if _parser_instance is None or force_new:
        _parser_instance = DocumentParser()
    return _parser_instance

def reset_parser():
    global _parser_instance
    _parser_instance = None
```

### Fix Strategy
Use factory pattern with environment-based config:

```python
import threading
from typing import Optional

class DocumentParserFactory:
    """Thread-safe document parser factory"""
    
    _lock = threading.Lock()
    _instance: Optional[DocumentParser] = None
    _version = 0  # Config version tracking
    
    @classmethod
    def get_parser(cls, force_new: bool = False) -> DocumentParser:
        """Get or create document parser"""
        # Check environment version
        env_version = int(os.getenv("PARSER_CONFIG_VERSION", "0"))
        
        with cls._lock:
            # If env version changed, recreate
            if env_version != cls._version or force_new:
                cls._instance = DocumentParser()
                cls._version = env_version
                return cls._instance
            
            # Otherwise return cached
            if cls._instance is None:
                cls._instance = DocumentParser()
            
            return cls._instance
    
    @classmethod
    def invalidate(cls):
        """Signal all instances to reload"""
        # This writes to a config service, not local memory
        config_service.increment_version("PARSER_CONFIG_VERSION")

# Instead of: get_document_parser()
# Use: DocumentParserFactory.get_parser()
```

### Implementation Steps
1. **Create `services/config_service.py`**:
   ```python
   class ConfigService:
       """Centralized config management"""
       
       def __init__(self, redis_client):
           self.redis = redis_client
       
       def get(self, key: str, default=None):
           """Get config from Redis"""
           value = self.redis.get(f"config:{key}")
           return value if value else default
       
       def set(self, key: str, value):
           """Set config in Redis"""
           self.redis.set(f"config:{key}", value)
       
       def increment_version(self, key: str):
           """Increment version to signal reload"""
           self.redis.incr(f"version:{key}")
   ```

2. **Update parser initialization** to read from ConfigService
3. **Add API endpoint** to invalidate parser:
   ```python
   @app.post("/api/admin/reload-parser")
   def reload_parser():
       DocumentParserFactory.invalidate()
       return {"status": "reload signaled"}
   ```

---

## P1: HIGH - Embedding Cache

### Problem
Cache not shared across instances, thread-unsafe.

### Current Code
**File**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/enhanced_search_service.py`

```python
# LINE 507
self._embedding_cache = {}  # Per-instance, unbounded

# LINES 512-532
def _get_embedding(self, text: str) -> np.ndarray:
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if cache_key in self._embedding_cache:
        return self._embedding_cache[cache_key]
    
    # ... API call ...
    
    self._embedding_cache[cache_key] = embedding
    if len(self._embedding_cache) > 500:
        keys = list(self._embedding_cache.keys())[:100]
        for k in keys:
            del self._embedding_cache[k]
```

### Fix Strategy
Use Redis with fallback to local cache:

```python
import redis
import threading
from typing import Optional

class EmbeddingCache:
    """Redis-backed embedding cache with local fallback"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self._local_cache = {}  # Fallback/local
        self._lock = threading.Lock()
        self._max_local = 500  # Local fallback size
    
    def get(self, text: str) -> Optional[np.ndarray]:
        """Get embedding from cache"""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        
        # Try Redis first
        if self.redis:
            try:
                cached = self.redis.get(f"embedding:{cache_key}")
                if cached:
                    return np.frombuffer(cached, dtype=np.float32)
            except redis.ConnectionError:
                pass  # Fall through to local cache
        
        # Try local cache
        with self._lock:
            if cache_key in self._local_cache:
                return self._local_cache[cache_key]
        
        return None
    
    def set(self, text: str, embedding: np.ndarray):
        """Cache embedding"""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        embedding_bytes = embedding.tobytes()
        
        # Store in Redis (with 24h TTL)
        if self.redis:
            try:
                self.redis.setex(
                    f"embedding:{cache_key}",
                    timedelta(hours=24),
                    embedding_bytes
                )
            except redis.ConnectionError:
                pass  # Fall through
        
        # Also store locally (with LRU eviction)
        with self._lock:
            self._local_cache[cache_key] = embedding
            if len(self._local_cache) > self._max_local:
                # Evict oldest (first inserted)
                oldest = next(iter(self._local_cache))
                del self._local_cache[oldest]

# Update EnhancedSearchService:
class EnhancedSearchService:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        # ... other init ...
        self._embedding_cache = EmbeddingCache(redis_client)
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding with distributed caching"""
        # Try cache
        cached = self._embedding_cache.get(text)
        if cached is not None:
            return cached
        
        # API call
        response = self.client.embeddings.create(...)
        embedding = np.array(response.data[0].embedding, dtype=np.float32)
        
        # Cache
        self._embedding_cache.set(text, embedding)
        
        return embedding
```

### Implementation Steps
1. **Create `services/embedding_cache.py`** with above code
2. **Update `EnhancedSearchService.__init__()`**:
   ```python
   redis_client = redis.Redis(...)  # From env
   self._embedding_cache = EmbeddingCache(redis_client)
   ```
3. **Replace embedding cache calls** in `_get_embedding()`

---

## Summary of Changes

### Files to Create
- `services/oauth_service.py` - OAuth state management
- `services/sync_service.py` - Sync progress tracking
- `services/config_service.py` - Centralized config
- `services/embedding_cache.py` - Distributed embedding cache
- `services/tenant_rag_cache.py` - Tenant data caching

### Files to Modify
- `api/integration_routes.py` - Remove global dicts
- `app_universal.py` - Remove global variables
- `services/document_parser.py` - Use factory
- `services/enhanced_search_service.py` - Use distributed cache

### New Dependencies
```
redis==4.5.0
python-jwt==1.7.1  # For JWT OAuth states
```

### Testing Checklist
- [ ] OAuth callback works with load balancer (3 instances)
- [ ] Sync progress visible across instances
- [ ] Parser config reload synced
- [ ] Embedding cache hits work across instances
- [ ] Memory usage stays <500MB per instance
- [ ] No duplicate data in multi-instance setup

