# In-Memory State and Caching Issues Preventing Scaling

## Executive Summary

The backend contains **critical scaling blockers** through heavy reliance on in-memory state, missing caching, and assumptions about single-instance deployment. Multi-instance horizontal scaling is **not possible** without significant refactoring.

---

## CRITICAL ISSUES FOUND

### 1. GLOBAL DICTIONARIES STORING SESSION STATE (FATAL)

**Issue**: OAuth states and sync progress stored in module-level dictionaries. Breaks in multi-instance.

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`
- **Lines 78-83**: 
```python
# Legacy oauth_states dict - kept for backward compatibility during transition
# TODO: Remove after all OAuth flows are migrated to JWT-based state
oauth_states = {}  # LINE 80 - CRITICAL: Global dict, NOT session-backed

# Sync progress tracking (use Redis in production for multi-instance)
sync_progress = {}  # LINE 83 - CRITICAL: No distributed backing
```

**Impact**:
- Instance 1 stores OAuth state, Instance 2 receives callback → **Fails with "invalid_state"**
- Sync progress only visible on the worker instance, not accessible to front-end on different instance
- Lost on server restart

**Scale**: 
- Gmail auth: Lines 225-239
- Slack auth: Lines 346-355  
- Box auth: Lines 747-762
- Sync status polling: Lines 1053-1063 (writes to `sync_progress` dict)

---

### 2. MULTI-TENANT RAG INSTANCES NOT ISOLATED (MEDIUM)

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/app_universal.py`
- **Lines 70-99**: Global variables that load entire tenant datasets into memory
```python
# Tenant-specific RAG instances
tenant_rag_instances = {}  # LINE 71 - Global cache, unbounded growth
tenant_data_loaded = {}    # LINE 72 - Tracks which tenants loaded

# Global variables
search_index = None        # LINE 91 - Monolithic, single-tenant
embedding_index = None     # LINE 92
knowledge_gaps = None      # LINE 93
user_spaces = None         # LINE 94
kb_metadata = None         # LINE 95
enhanced_rag = None        # LINE 96
stakeholder_graph = None   # LINE 97
connector_manager = None   # LINE 98
document_manager = None    # LINE 99
```

**Problem**:
- Each tenant's entire RAG loads into memory of first instance that accesses it
- No bounds on `tenant_rag_instances` → memory leak with multiple tenants
- Accessing tenant B on instance 2 forces reload (duplicate memory on different instances)
- Stakeholder graphs/connectors for different tenants share instance

**Scale Factor**: 
- If each tenant needs 500MB (reasonable for large dataset), 10 concurrent tenants = 5GB single server
- No distributed cache means each instance maintains separate copies

---

### 3. SINGLETON PATTERN WITH GLOBAL STATE

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/document_parser.py`
- **Lines 421-436**: Classic problematic singleton
```python
# Singleton instance for easy access
_parser_instance: Optional[DocumentParser] = None  # LINE 422

def get_document_parser(force_new: bool = False) -> DocumentParser:
    """Get the singleton document parser instance."""
    global _parser_instance
    if _parser_instance is None or force_new:
        _parser_instance = DocumentParser()
    return _parser_instance

def reset_parser():
    """Reset the parser singleton to reload configuration."""
    global _parser_instance
    _parser_instance = None
```

**Impact**:
- Parser config reloaded only on **one instance** when `reset_parser()` called
- Other instances still use old Azure/LlamaParse credentials
- No thread-safe refcounting on parser instance

---

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/enhanced_search_service.py`
- **Lines 862-871**: Embedding cache singleton
```python
# Singleton instance
_enhanced_search_service: Optional[EnhancedSearchService] = None

def get_enhanced_search_service() -> EnhancedSearchService:
    """Get or create singleton EnhancedSearchService"""
    global _enhanced_search_service
    if _enhanced_search_service is None:
        _enhanced_search_service = EnhancedSearchService()
    return _enhanced_search_service
```

**Problem Inside**:
- Line 507: `self._embedding_cache = {}` - Unbounded local cache
- Lines 512-532: Manual cache eviction (LRU) by deleting random 100 items
- **Not thread-safe**: Two concurrent requests → race condition on cache reads/writes
- Each instance maintains separate embedding cache → cache misses on failover

---

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/vector_stores/pinecone_store.py`
- Likely has singleton pattern (confirm by reading more)

---

### 4. ENTITY NORMALIZER WITH UNBOUNDED CACHING

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/intelligent_gap_detector.py`
- **Lines 450-538**: EntityNormalizer holds state
```python
class EntityNormalizer:
    def __init__(self):
        self.canonical_map: Dict[str, str] = {}  # LINE 463 - Cache
        self.entity_clusters: Dict[str, Set[str]] = {}  # LINE 464 - No bounds

    def normalize(self, name: str) -> str:
        """Normalize a name to canonical form"""
        if not name:
            return ""

        # Check cache first
        name_lower = name.lower().strip()
        if name_lower in self.canonical_map:
            return self.canonical_map[name_lower]  # Cache hit
        # ... processing ...
        return cleaned

    def add_alias(self, alias: str, canonical: str):
        """Add an alias mapping"""
        # ... unbounded growth ...
        self.entity_clusters[canonical_clean].add(alias)  # No capacity limits
```

**Scale Issue**:
- Process 1M documents → normalization cache grows unbounded
- No invalidation strategy (what if John Smith is renamed?)
- Shared globally if IntelligentGapDetector is singleton
- Example: 1M unique names × 5 aliases each = 5M cache entries

---

### 5. MISSING CACHING: EXPENSIVE OPERATIONS NOT CACHED

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/intelligent_gap_detector.py`
- **Lines 1837-1954**: IntelligentGapDetector orchestrator
```python
class IntelligentGapDetector:
    def __init__(self):
        self.frame_extractor = FrameExtractor()
        self.srl_analyzer = SemanticRoleAnalyzer()
        self.discourse_analyzer = DiscourseAnalyzer()
        self.kg_builder = KnowledgeGraphBuilder()
        self.verifier = CrossDocumentVerifier()
        self.question_generator = GroundedQuestionGenerator()
        # ...
```

**Missing Cache #1 - spaCy Model (HIGHEST IMPACT)**:
- Line 49: `NLP = spacy.load("en_core_web_sm")` - **Module level**
- **Good**: Shared across all detector instances
- **Bad**: Should be lazy-loaded, and could be Redis-cached for multi-instance
- Cost: 50MB per instance load, 300ms initialization

**Missing Cache #2 - Frame Extraction Results**:
- Lines 658-682: `extract_frames()` processes every document
- No memoization of frame patterns seen before
- Same patterns repeated across documents (DECISION, PROCESS, OWNERSHIP)
- No indexing of triggers for O(1) lookup

Example: Processing 10,000 emails → runs 150+ trigger patterns on EVERY sentence
```python
for frame_type, template in FRAME_TEMPLATES.items():
    for trigger_pattern in template["triggers"]:
        if re.search(trigger_pattern, sentence, re.IGNORECASE):  # LINE 669
```

**Missing Cache #3 - spaCy Doc Processing**:
- Lines 733-851: `FrameExtractor._extract_slots_spacy()` 
- Line 735: `doc = self.nlp(sentence)` - NLP processing on every sentence
- No caching of processed docs
- Repeated processing of duplicate sentences across documents

---

### 6. KNOWLEDGE GRAPH BUILDER WITH UNBOUNDED MEMORY

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/intelligent_gap_detector.py`
- **Lines 1162-1181**: KnowledgeGraphBuilder
```python
class KnowledgeGraphBuilder:
    def __init__(self):
        self.entities: Dict[str, Entity] = {}  # LINE 1163 - Unbounded
        self.relations: List[Relation] = []    # LINE 1164 - Unbounded growth
        self.normalizer = EntityNormalizer()   # Per-instance normalizer
        self.nlp = NLP  # Shared model reference

    def add_document(self, text: str, doc_id: str):
        """Extract entities and relations from document"""
        entities = self._extract_entities(text, doc_id)
        
        for entity in entities:
            if entity.id not in self.entities:
                self.entities[entity.id] = entity  # Unbounded dict
            else:
                self.entities[entity.id].mentions.extend(entity.mentions)
                self.entities[entity.id].documents.update(entity.documents)
                self.entities[entity.id].aliases.update(entity.aliases)

        relations = self._extract_relations(text, doc_id, entities)
        self.relations.extend(relations)  # Unbounded list append
```

**Problem**:
- Processing 10K documents → potentially 100K+ entities, 1M+ relations
- All stored in memory
- If this is a singleton (and likely is), entire knowledge graph persists across requests
- No TTL, no cleanup, no distributed storage

**Memory Estimate**:
```
Entity: ~500 bytes (name, canonical, mentions, documents, aliases, attributes)
Relation: ~200 bytes (source, target, type, confidence, evidence)

100K entities @ 500B = 50MB
1M relations @ 200B = 200MB
Total = 250MB per instance for single tenant
```

---

### 7. CROSS-DOCUMENT VERIFIER WITH UNBOUNDED CLAIMS CACHE

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/intelligent_gap_detector.py`
- **Lines 1402-1410**: CrossDocumentVerifier
```python
class CrossDocumentVerifier:
    def __init__(self):
        self.claims_by_topic: Dict[str, List[Dict]] = defaultdict(list)  # LINE 1403

    def add_document(self, text: str, doc_id: str, doc_title: str = ""):
        """Extract and store claims"""
        claims = self._extract_claims(text, doc_id, doc_title)  # LINE 1407
        for claim in claims:
            topic = claim.get("topic", "general")
            self.claims_by_topic[topic].append(claim)  # Unbounded append
```

**Problem**:
- Every document's claims stay in memory forever
- 10K documents @ 10 claims each = 100K list appends, never cleared
- Memory grows monotonically

---

### 8. QUERY EXPANSION WITH MODULE-LEVEL DICTIONARIES

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/enhanced_search_service.py`
- **Lines 51-182**: QueryExpander
```python
class QueryExpander:
    """Query expansion with acronyms and synonyms"""

    # Comprehensive acronym dictionary (100+ terms)
    ACRONYMS = {  # CLASS VARIABLE (OK - immutable)
        # ... 100+ acronyms ...
    }

    # Synonym mappings
    SYNONYMS = {  # CLASS VARIABLE (OK - immutable)
        # ... synonyms ...
    }
```

**Assessment**: ACCEPTABLE
- Immutable class variables → OK for scaling
- No per-instance state
- Could benefit from constant interning but not critical

---

### 9. COREFERENCE RESOLVER WITH UNBOUNDED MENTION TRACKING

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/intelligent_gap_detector.py`
- **Lines 593-633**: CoreferenceResolver
```python
class CoreferenceResolver:
    def __init__(self):
        self.entity_mentions: List[Dict] = []  # LINE 594 - Unbounded
        self.chains: List[CoreferenceChain] = []  # LINE 595 - Unbounded
```

**Problem**:
- Accumulates mentions across all documents processed by instance
- No bounds or cleanup
- If shared globally, accumulates forever

---

### 10. MISSING CACHING: EMBEDDING OPERATIONS

**Location**: `/Users/rishitjain/Downloads/2nd-brain/backend/services/enhanced_search_service.py`
- **Lines 512-532**: Manual embedding cache in EnhancedSearchService
```python
def _get_embedding(self, text: str) -> np.ndarray:
    """Get embedding with caching"""
    cache_key = hashlib.md5(text.encode()).hexdigest()  # LINE 514
    if cache_key in self._embedding_cache:
        return self._embedding_cache[cache_key]  # Cache hit

    response = self.client.embeddings.create(  # LINE 518 - EXPENSIVE API CALL
        model=AZURE_EMBEDDING_DEPLOYMENT,
        input=text,
        dimensions=1536
    )
    embedding = np.array(response.data[0].embedding, dtype=np.float32)
    
    self._embedding_cache[cache_key] = embedding  # LINE 525
    if len(self._embedding_cache) > 500:  # LINE 526 - Ad-hoc eviction
        # Evict oldest
        keys = list(self._embedding_cache.keys())[:100]
        for k in keys:
            del self._embedding_cache[k]
```

**Problems**:
1. **Local only**: Cache lost on instance failover
2. **Thread-unsafe**: Two concurrent requests can race on cache update
3. **Manual eviction**: Deletes 100 items when >500, not LRU
4. **No coordination**: If 2 instances both request same embedding, both hit API
5. **No persistence**: Warm cache not reused across server restarts

---

## SUMMARY TABLE

| Issue | File | Lines | Severity | Impact |
|-------|------|-------|----------|--------|
| OAuth state dict | integration_routes.py | 80 | **CRITICAL** | Multi-instance auth fails |
| Sync progress dict | integration_routes.py | 83 | **CRITICAL** | Progress lost on failover |
| Tenant RAG dict | app_universal.py | 71-99 | **HIGH** | 5GB+ memory for 10 tenants |
| Document parser singleton | document_parser.py | 422 | HIGH | Config not synced across instances |
| Embedding cache singleton | enhanced_search_service.py | 507, 512-532 | HIGH | Cache hits lost on failover, thread-unsafe |
| Entity normalizer cache | intelligent_gap_detector.py | 463-464 | MEDIUM | Unbounded growth, ~5M entries for 1M docs |
| Knowledge graph | intelligent_gap_detector.py | 1163-1164 | HIGH | 250MB per instance, no limits |
| Claims cache | intelligent_gap_detector.py | 1403 | MEDIUM | Unbounded memory for verifier |
| Frame extraction | intelligent_gap_detector.py | 658-682 | MEDIUM | Repeated pattern matching, no memoization |
| Embedding cache eviction | enhanced_search_service.py | 526-530 | MEDIUM | Not thread-safe, manual LRU |

---

## SCALING FAILURES

### Scenario 1: Load Balancer with 3 Instances
```
User logs in on Instance 1:
  - OAuth state stored in Instance 1's oauth_states dict
  
Google OAuth callback routed to Instance 2:
  - Instance 2 checks its oauth_states dict
  - Dict is empty → "invalid_state" error
  - Auth fails
```

### Scenario 2: Sync Operations
```
Instance 1 starts Slack sync:
  - Updates sync_progress["rishi:slack"] = {status: "syncing", progress: 20}
  
Frontend polls from Instance 2 (via load balancer):
  - Instance 2's sync_progress dict is empty
  - Returns status: "idle"
  
User sees incorrect sync status
```

### Scenario 3: Memory Explosion
```
Tenant "Enron" with 600K documents
Each tenant RAG in app_universal.py needs:
  - search_index: 100MB
  - embedding_index: 50MB
  - knowledge_gaps: 100MB
  - RAG instance: 150MB
  Total: ~400MB per instance

With 3 instances: 1.2GB for one tenant
With 10 tenants: 4GB per instance, 12GB total cluster
```

### Scenario 4: Spacy Model Loading
```
Instance starts → loads spacy en_core_web_sm
  Time: ~300ms
  Memory: ~50MB

If not singleton, every gap detector loads it:
  - If 10 concurrent requests
  - 10 * 300ms = 3 seconds latency hit
  - 10 * 50MB = 500MB spike
```

---

## REQUIRED FIXES

### Tier 1: CRITICAL (Blocks multi-instance)
1. **OAuth State** → Redis with 10-minute TTL
2. **Sync Progress** → Redis with TTL or database table
3. **Tenant RAG Instances** → Database caching layer + per-request loading

### Tier 2: HIGH (Memory/Performance)
1. **Embedding Cache** → Redis (distributed)
2. **Entity Normalizer** → Redis or database (shared)
3. **Knowledge Graph** → Database persistent storage
4. **Parser Singleton** → Convert to factory with credentials from config service

### Tier 3: MEDIUM (Optimization)
1. **Frame Extraction** → Memoize pattern matching results
2. **spaCy Processing** → Batch processing + per-sentence cache
3. **Embedding Eviction** → Implement proper LRU with thread locks

---

## RECOMMENDATIONS

### Immediate (Week 1)
- [ ] Add Redis instance for session/auth state
- [ ] Move oauth_states and sync_progress to Redis
- [ ] Add distributed lock for concurrent operations

### Short-term (Week 2-3)
- [ ] Add request-scoped context for RAG instances (not global)
- [ ] Implement embedding cache with Redis backend
- [ ] Add database persistence for entity graphs

### Medium-term (Week 4+)
- [ ] Implement caching layer for expensive operations
- [ ] Add monitoring for memory usage per instance
- [ ] Refactor singletons to use dependency injection

