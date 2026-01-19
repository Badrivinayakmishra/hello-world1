# RAG Architecture Quick Reference

## File Locations

| Component | File |
|-----------|------|
| Vector Store | `/backend/vector_stores/pinecone_store.py` |
| Embedding Service | `/backend/services/embedding_service.py` |
| Enhanced Search | `/backend/services/enhanced_search_service.py` |
| Knowledge Service | `/backend/services/knowledge_service.py` |
| Database Models | `/backend/database/models.py` |
| API Routes (Documents) | `/backend/api/document_routes.py` |
| API Routes (Knowledge) | `/backend/api/knowledge_routes.py` |

## Key Parameters

```python
# Embedding
CHUNK_SIZE = 2000 characters
CHUNK_OVERLAP = 400 characters
EMBEDDING_DIMENSIONS = 1536
EMBEDDING_MODEL = "text-embedding-3-large"

# Pinecone
INDEX_NAME = "knowledgevault"
METRIC = "cosine"
BATCH_SIZE = 100 vectors per upsert
MAX_RETRIES = 3
RETRY_DELAY = 1 second

# Search
QUERY_EXPANSION = Yes (100+ acronyms)
CROSS_ENCODER = "cross-encoder/ms-marco-MiniLM-L-12-v2"
HYBRID_SEARCH = sparse (0.3) + dense (0.7)
FRESHNESS_BOOST = 0.9 to 1.15 based on document age

# Chat
CHAT_MODEL = "gpt-5-chat"
CHAT_TEMPERATURE = 0.1 (low for factual answers)
MAX_CONTEXT_TOKENS = 12000
CITATION_REQUIREMENT = Mandatory
```

## Data Flow

### Document Embedding
```
Document Sync → Classification → Structured Extraction → Embedding Service
                                                             ↓
                                                    PineconeVectorStore
                                                    - Chunk text (2000 chars)
                                                    - Get Azure OpenAI embedding
                                                    - Generate vector ID (MD5)
                                                    - Upsert to Pinecone
                                                    - Update embedded_at timestamp
```

### RAG Query
```
User Query → Query Expansion → Initial Search (Pinecone) → Freshness Scoring
                                                               ↓
                                                    Cross-Encoder Reranking
                                                               ↓
                                                    MMR Diversity Selection
                                                               ↓
                                                    LLM Answer Generation
                                                    (with mandatory citations)
                                                               ↓
                                                    Hallucination Detection
                                                               ↓
                                                    Response + Sources
```

### Knowledge Gap to RAG
```
Gap Analysis → KnowledgeGap Created → Answer Submission → Complete Process
                                         ↓
                                    GapAnswer Stored
                                         ↓
                                    rebuild_embedding_index()
                                    - Collect all answers
                                    - Embed to Pinecone
                                    - Mark gaps VERIFIED
```

## Tenant Isolation

**3-Layer Strategy:**
1. Pinecone Namespace = tenant_id
2. Every vector has metadata: tenant_id (filtered in queries)
3. API routes validate tenant_id from JWT token

**All Critical Methods:**
```python
vector_store.embed_and_upsert_documents(tenant_id=REQUIRED)
vector_store.search(tenant_id=REQUIRED)
vector_store.hybrid_search(tenant_id=REQUIRED)
```

## Critical Issues

| Issue | Severity | Fix |
|-------|----------|-----|
| Document deletion doesn't remove Pinecone vectors | HIGH | Call `embedding_service.delete_document_embeddings()` after hard delete |
| Submitted answers not auto-embedded | MEDIUM | Add post-submit hook to trigger embedding |
| No search/chat API endpoint | MEDIUM | Create `/api/search` or `/api/chat` endpoint |
| Hallucination detection optional | LOW | Make `validate=True` default in chat endpoint |

## Common Operations

### Embed Documents
```python
from services.embedding_service import get_embedding_service

service = get_embedding_service()
result = service.embed_tenant_documents(
    tenant_id="tenant-123",
    db=db,
    force_reembed=False
)
```

### Search
```python
from services.enhanced_search_service import get_enhanced_search_service
from vector_stores.pinecone_store import get_vector_store

search_service = get_enhanced_search_service()
vector_store = get_vector_store()

results = search_service.search_and_answer(
    query="What is ROI?",
    tenant_id="tenant-123",
    vector_store=vector_store,
    top_k=10,
    validate=True
)
```

### Integrate Answers into RAG
```python
from services.knowledge_service import KnowledgeService

service = KnowledgeService(db)
result = service.complete_knowledge_process(
    tenant_id="tenant-123",
    mark_completed=True
)
```

### Delete Document Embeddings
```python
from services.embedding_service import get_embedding_service

service = get_embedding_service()
result = service.delete_document_embeddings(
    document_ids=["doc-1", "doc-2"],
    tenant_id="tenant-123",
    db=db
)
```

## Environment Variables

```bash
# Pinecone
export PINECONE_API_KEY="pk-..."
export PINECONE_INDEX="knowledgevault"

# Azure OpenAI
export AZURE_OPENAI_ENDPOINT="https://..."
export AZURE_OPENAI_API_KEY="..."
export AZURE_API_VERSION="2023-05-15"
export AZURE_EMBEDDING_DEPLOYMENT="text-embedding-3-large"
export AZURE_CHAT_DEPLOYMENT="gpt-5-chat"
export AZURE_WHISPER_DEPLOYMENT="whisper"

# Database
export DATABASE_URL="postgresql://..."
```

## Testing Checklist

- [ ] Create test tenant
- [ ] Sync documents
- [ ] Verify documents embedded (check Pinecone stats)
- [ ] Test search with query expansion
- [ ] Verify tenant isolation (search with different tenant_id)
- [ ] Submit answer to knowledge gap
- [ ] Call complete_knowledge_process()
- [ ] Verify answers searchable via RAG
- [ ] Hard delete document
- [ ] Verify embeddings cleaned up (call delete_document_embeddings)
- [ ] Test hallucination detection
- [ ] Monitor Pinecone vector count

## Performance Notes

- **Embedding:** ~0.5-1s per document (depends on size)
- **Search:** ~100-500ms (includes expansion, reranking, MMR)
- **LLM Generation:** ~1-3s (depends on response length)
- **Pinecone:** Serverless, scales automatically
- **Recommended:** Cache embeddings for frequent queries

## Monitoring

**Key Metrics:**
- Pinecone vector count per tenant
- Embedding success/error rates
- Search latency (expansion, search, rerank, mmr, generation)
- Citation coverage ratio
- Hallucination detection results
- Document embedding backlog (documents with embedded_at == NULL)

