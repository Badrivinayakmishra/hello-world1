# 2nd Brain RAG/Chatbot Architecture Analysis

**Date:** January 5, 2026
**Project:** Knowledge Vault Backend
**Scope:** Vector Store, Embedding Flow, RAG Implementation, Tenant Isolation

---

## Executive Summary

The 2nd Brain backend implements a **production-grade multi-tenant RAG (Retrieval Augmented Generation) system** with:
- **Pinecone** as the vector database
- **Azure OpenAI** (text-embedding-3-large) for embeddings
- **Tenant namespace isolation** for data security
- **Advanced search features** (query expansion, cross-encoder reranking, MMR diversity, hallucination detection)
- **Knowledge gap answer integration** into the RAG index
- **Document deletion tracking** to prevent re-sync from connectors

---

## 1. VECTOR STORE: Pinecone Configuration

### Location
- **Main Implementation:** `/backend/vector_stores/pinecone_store.py`
- **Configuration:** Environment variables

### Setup Details
```python
# Pinecone Configuration
- API Key: PINECONE_API_KEY (from environment)
- Index Name: "knowledgevault" (customizable via PINECONE_INDEX env var)
- Dimension: 1536 (Azure text-embedding-3-large native dimension)
- Metric: Cosine similarity
- Spec: Serverless (AWS us-east-1 region)
```

### Key Classes
1. **`PineconeVectorStore`** - Core vector store with:
   - Multi-tenant isolation via namespaces + metadata filtering
   - Batch upsert operations (BATCH_SIZE = 100)
   - Retry logic (MAX_RETRIES = 3, RETRY_DELAY = 1 second)
   - Automatic deduplication via vector ID hashing

2. **`HybridPineconeStore`** - Extends PineconeVectorStore with:
   - Dense (semantic) + sparse (keyword) search combination
   - Configurable weights (sparse: 0.3, dense: 0.7)

### Deduplication Strategy
```
Vector ID = MD5(document_id + chunk_index)
- Same document always produces same vector IDs
- Pinecone upsert (not insert) handles updates automatically
- Re-embedding the same document overwrites existing vectors
```

---

## 2. EMBEDDING FLOW: Document → Vector

### Overview
Documents flow through this sequence:

```
Document Created/Synced
    ↓
[Classification Service] (classify as work/personal)
    ↓
[Structured Extraction] (via Document Parser)
    ↓
[Embedding Service] (when embedded_at is NULL)
    ↓
[Pinecone Vector Store] (chunked & embedded)
    ↓
Available for RAG Search
```

### Chunking Configuration
**File:** `/backend/services/embedding_service.py` (lines 24-26)

```python
CHUNK_SIZE = 2000          # Characters per chunk
CHUNK_OVERLAP = 400        # Character overlap between chunks
```

**Chunking Algorithm:** (`pinecone_store.py`, lines 175-255)
- Sentence-aware splitting with multiple boundary types
- Sentence endings (in order of preference):
  1. `\n\n` (paragraph break - highest priority)
  2. `.\n`, `!\n`, `?\n` (sentence + newline)
  3. `. `, `! `, `? ` (sentence + space)
  4. `.\t` (sentence + tab)
  5. `\n` (single newline)
  6. `; ` (semicolon - fallback)

**Smart Boundary Detection:**
- Finds best sentence boundary in latter half of chunk
- Ensures continuity between chunks via overlap
- Prevents truncating in middle of sentences

### When Embedding Happens

**Timing:** During document synchronization and on-demand

**File:** `/backend/services/embedding_service.py` (lines 60-163)

```python
def embed_documents(
    documents: List[Document],
    tenant_id: str,
    db: Session,
    force_reembed: bool = False,
    progress_callback: Optional[callable] = None
) -> Dict
```

**Deduplication Logic:**
- Skips documents where `embedded_at` is NOT NULL
- Only embeds documents with content
- Can force re-embed with `force_reembed=True`
- Updates `embedded_at` timestamp after successful embedding

**Update Tracking:**
- Sets `Document.embedded_at = now()` after embedding
- Sets `Document.embedding_generated = True`
- Records `Document.embedding_model = "text-embedding-3-large"`

### Embedding Service Workflow

1. **Filter documents to embed:**
   - Check `doc.embedded_at` (skip if already embedded)
   - Check `doc.content` exists (skip if empty)

2. **Convert to Pinecone format:**
   ```python
   {
       'id': document.id,
       'content': document.content,
       'title': document.title,
       'metadata': {
           'source_type': document.source_type,
           'external_id': document.external_id,
           'sender': document.sender,
           'classification': document.classification,
           'created_at': document.source_created_at.isoformat()
       }
   }
   ```

3. **Call PineconeVectorStore.embed_and_upsert_documents():**
   - Chunks text with sentence-aware splitting
   - Gets embeddings via Azure OpenAI API
   - Generates deterministic vector IDs
   - Upserts to Pinecone with tenant_id namespace

4. **Update database:**
   - Marks documents as `embedded_at = now()`
   - Commits changes

### Azure OpenAI Configuration
**File:** `/backend/vector_stores/pinecone_store.py` (lines 28-38)

```python
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2023-05-15"
AZURE_EMBEDDING_DEPLOYMENT = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 1536
```

**Embedding Limits:**
- Max embedding characters: 30,000 (text-embedding-3-large supports 8191 tokens ≈ 32K chars)
- With 2000 char chunks, limit should not trigger
- Truncation warning logged if exceeded

---

## 3. CHATBOT/SEARCH IMPLEMENTATION

### Core RAG Pipeline

**File:** `/backend/services/enhanced_search_service.py` (lines 482-871)

The `EnhancedSearchService` orchestrates the complete RAG flow:

```
User Query
    ↓
[Query Expansion] - Expand acronyms, add synonyms
    ↓
[Pinecone Search] - Retrieve vectors (retrieve_k = top_k * 3 for reranking)
    ↓
[Freshness Scoring] - Boost recent documents
    ↓
[Cross-Encoder Reranking] - Re-score using BERT model (ms-marco-MiniLM-L-12-v2)
    ↓
[MMR Diversity Selection] - Select diverse results
    ↓
[LLM Answer Generation] - Generate response with citations
    ↓
[Hallucination Detection] - Verify claims against sources
    ↓
Response with Sources + Metadata
```

### Query Expansion
**File:** `/backend/services/enhanced_search_service.py` (lines 51-196)

**Features:**
- 100+ acronym expansions (healthcare, finance, consulting, tech)
- Synonym detection and expansion
- Example: "ROI" → "ROI (Return on Investment)"

**Supported Acronyms (sample):**
- Healthcare: NICU, ICU, L&D, OR, FDU, EMR, EHR, HIPAA
- Finance: NPV, IRR, EBITDA, P&L, COGS, OPEX, CAPEX, DCF, WACC
- Consulting: SOW, RFP, NDA, SLA, KPI, OKR, SWOT
- Tech: API, AWS, GCP, ML, AI, NLP, RAG, LLM

### Search Methods

#### 1. Standard Pinecone Search
```python
vector_store.search(
    query: str,
    tenant_id: str,           # REQUIRED for isolation
    namespace: Optional[str],  # Defaults to tenant_id
    top_k: int = 10,
    filter: Optional[Dict],    # Additional metadata filters
    include_metadata: bool
) -> List[Dict]
```

**Key Implementation Details:**
- Gets query embedding via Azure OpenAI
- Builds combined filter: `{'tenant_id': {'$eq': tenant_id}}`
- Applies additional filters if provided
- Returns results with scores, doc_id, chunk_idx, title, content preview

#### 2. Hybrid Search (Semantic + Keyword)
```python
vector_store.hybrid_search(
    query: str,
    tenant_id: str,
    namespace: Optional[str],
    top_k: int = 10,
    filter: Optional[Dict],
    sparse_weight: float = 0.3,
    dense_weight: float = 0.7
) -> List[Dict]
```

**Algorithm:**
- Fetches semantic results (top_k * 2 for reranking)
- Boosts results containing query keywords:
  - Content matches: +0.05 boost per match
  - Title matches: +0.15 boost per match (weighted higher)
  - Max keyword boost: 0.3
- Combines: `score = (0.7 * semantic) + (0.3 * keyword_boost)`
- Re-sorts and returns top_k

#### 3. Enhanced Search with All Features
```python
enhanced_search(
    query: str,
    tenant_id: str,
    vector_store,
    top_k: int = 10,
    use_reranking: bool = True,
    use_mmr: bool = True,
    use_expansion: bool = True,
    use_freshness: bool = True,
    mmr_lambda: float = 0.7
) -> Dict
```

**Pipeline Steps:**

**a) Query Expansion:**
- Expands acronyms in query
- Logs expanded query for debugging

**b) Initial Retrieval:**
- Retrieves `top_k * 3` results (for reranking)
- Uses hybrid search if available, else standard search

**c) Freshness Scoring:**
- Extracts date from document content/metadata
- Applies boost factor:
  - Current year: 1.15x boost
  - 1 year old: 1.1x boost
  - 2 years old: 1.0x (no boost)
  - 5 years old: 0.95x (penalty)
  - Older: 0.9x (penalty)

**d) Cross-Encoder Reranking:**
- Uses sentence-transformers model: `cross-encoder/ms-marco-MiniLM-L-12-v2`
- Scores content segments (beginning, middle, end)
- Reduces results to `top_k * 2`

**e) MMR Diversity Selection:**
- Computes embeddings for all results
- Uses Maximal Marginal Relevance algorithm
- Selects diverse results balancing relevance and diversity
- Lambda = 0.7 (70% relevance, 30% diversity)

### Answer Generation with Citations

**File:** `/backend/services/enhanced_search_service.py` (lines 673-809)

```python
def generate_answer(
    self,
    query: str,
    search_results: Dict,
    validate: bool = True,
    max_context_tokens: int = 12000
) -> Dict
```

**Key Features:**

1. **Context Construction:**
   - Uses up to 15 sources (expanded from default)
   - Max context: 12,000 tokens (~48K characters)
   - Doesn't aggressively truncate (up to 3000 chars per source)
   - Includes source number, relevance score, title

2. **System Prompt (Mandatory Citation Rules):**
   ```
   - EVERY fact, number, date, or claim MUST have [Source N]
   - If cannot cite, do NOT include the statement
   - Never synthesize or infer beyond what sources state
   - Say "I don't have information..." if sources don't cover topic
   ```

3. **LLM Configuration:**
   - Model: `gpt-5-chat` (via Azure OpenAI)
   - Temperature: 0.1 (low for factual consistency)
   - Max tokens: 2000

4. **Hallucination Detection:**
   - Extracts numerical claims with context
   - Extracts citations and verifies source numbers
   - Verifies numbers appear in source documents
   - Returns: verified, unverified, hallucinated claim counts
   - Confidence score = verified / total_claims

5. **Citation Coverage Check:**
   - Counts sentences with citations
   - Flags if citation ratio < 70%
   - Returns: cited_ratio, uncited_sentences, total_checkable

### Complete RAG Pipeline
```python
def search_and_answer(
    self,
    query: str,
    tenant_id: str,
    vector_store,
    top_k: int = 10,
    validate: bool = True
) -> Dict
```

**Returns:**
```python
{
    'query': original_query,
    'expanded_query': expanded_search_query,
    'answer': generated_answer_text,
    'confidence': float (0.0-1.0),
    'sources': list of 10 source documents,
    'num_sources': int,
    'search_time': float (seconds),
    'features_used': {
        'expansion': bool,
        'reranking': bool,
        'mmr': bool,
        'freshness': bool
    },
    'hallucination_check': {
        'verified': int,
        'unverified': int,
        'hallucinated': int,
        'confidence': float
    },
    'citation_check': {
        'cited_ratio': float,
        'uncited_sentences': list,
        'total_checkable': int
    },
    'context_chars': int
}
```

---

## 4. TENANT ISOLATION: Multi-Tenant Security

### 3-Layer Isolation Strategy

**File:** `/backend/vector_stores/pinecone_store.py` (lines 60-72)

```
Layer 1: Namespace (Primary)
  - Each tenant gets separate Pinecone namespace
  - Default: namespace = tenant_id
  - Can override with custom namespace
  
Layer 2: Metadata Filtering (Secondary)
  - Every vector includes 'tenant_id' in metadata
  - All searches enforce: {'tenant_id': {'$eq': tenant_id}}
  - Defense in depth (even if namespace breached)
  
Layer 3: Application Layer
  - API routes validate tenant_id from JWT token (g.tenant_id)
  - All database queries filter by tenant_id
  - Document embedding requires explicit tenant_id parameter
```

### Implementation Details

#### 1. Embedding with Tenant Isolation
```python
# From embedding_service.py
result = self.vector_store.embed_and_upsert_documents(
    documents=pinecone_docs,
    tenant_id=tenant_id,      # REQUIRED
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    show_progress=True
)
```

**Metadata Stored per Vector:**
```python
metadata = {
    'doc_id': chunk['doc_id'],
    'chunk_idx': chunk['chunk_idx'],
    'tenant_id': chunk['tenant_id'],  # CRITICAL for isolation
    'title': chunk['title'][:200],
    'content_preview': chunk['content'][:500],
    # Custom metadata (< 500 chars each)
    'source_type': ...,
    'external_id': ...,
    'sender': ...,
    'classification': ...,
    'created_at': ...
}
```

#### 2. Search with Tenant Isolation
```python
# From pinecone_store.py
def search(
    self,
    query: str,
    tenant_id: str,      # REQUIRED
    namespace: Optional[str] = None,
    top_k: int = 10,
    filter: Optional[Dict] = None
) -> List[Dict]:
    ns = namespace or tenant_id
    
    # Build filter with tenant_id (defense in depth)
    combined_filter = {'tenant_id': {'$eq': tenant_id}}
    if filter:
        combined_filter = {'$and': [combined_filter, filter]}
    
    # Query with tenant isolation enforced
    results = self.index.query(
        vector=query_embedding,
        namespace=ns,
        top_k=top_k,
        filter=combined_filter,  # Tenant check enforced here
        include_metadata=include_metadata
    )
```

#### 3. Database-Level Isolation
**File:** `/backend/api/document_routes.py` (lines 74-78)

```python
# All document queries include tenant_id filter
query = db.query(Document).filter(
    Document.tenant_id == g.tenant_id,
    Document.is_deleted == False
)
```

**File:** `/backend/api/knowledge_routes.py` (lines 274-276)

```python
# All gap queries include tenant_id filter
gap = db.query(KnowledgeGap).filter(
    KnowledgeGap.id == gap_id,
    KnowledgeGap.tenant_id == g.tenant_id  # Tenant check
).first()
```

### Storage Statistics
**File:** `/backend/vector_stores/pinecone_store.py` (lines 485-501)

```python
def get_stats(self, tenant_id: Optional[str] = None) -> Dict:
    """Get index statistics, optionally filtered by tenant"""
    stats = self.index.describe_index_stats()
    
    if tenant_id:
        ns_stats = stats.namespaces.get(tenant_id, {})
        return {
            'tenant_id': tenant_id,
            'namespace': tenant_id,
            'vector_count': getattr(ns_stats, 'vector_count', 0)
        }
    
    return {
        'total_vectors': stats.total_vector_count,
        'dimension': stats.dimension,
        'namespaces': {k: v.vector_count for k, v in stats.namespaces.items()}
    }
```

---

## 5. DOCUMENT DELETION & CLEANUP

### Soft Delete vs Hard Delete

**File:** `/backend/api/document_routes.py` (lines 738-788)

#### Soft Delete (Default)
```python
@document_bp.route('/<document_id>', methods=['DELETE'])
def delete_document(document_id: str):
    hard_delete = request.args.get('hard', '').lower() == 'true'
    
    if hard_delete:
        # Hard delete (see below)
        db.delete(document)
    else:
        # Soft delete
        document.is_deleted = True
        document.deleted_at = utc_now()
    
    db.commit()
```

**Soft Delete Behavior:**
- Marks `Document.is_deleted = True`
- Sets `deleted_at` timestamp
- Document remains in database (for audit trail)
- Excluded from queries via `Document.is_deleted == False`
- No impact on Pinecone (vectors remain)

#### Hard Delete
```python
# Option 1: Single document hard delete
db.delete(document)

# Option 2: Bulk hard delete (lines 790-909)
@document_bp.route('/bulk/delete', methods=['POST'])
def bulk_delete():
    data = request.get_json()
    document_ids = data['document_ids']
    hard_delete = data.get('hard', False)  # Default: soft delete
```

**Hard Delete Workflow:**
1. **Track external_id (if from connector):**
   ```python
   if document.external_id and document.connector_id:
       deleted_record = DeletedDocument(
           tenant_id=document.tenant_id,
           connector_id=document.connector_id,
           external_id=document.external_id,
           source_type=document.source_type,
           original_title=document.title,
           deleted_by=g.user_id
       )
       db.add(deleted_record)
   ```
   - Prevents document from being re-synced from source
   - Tracks deletion in audit trail

2. **Delete from database:**
   ```python
   db.delete(document)  # Removes document record
   # Cascade: DocumentChunk records also deleted
   ```

3. **Update embedding status (NOT automatic):**
   - **Issue:** Embeddings in Pinecone are NOT automatically deleted
   - **Impact:** Vectors remain in Pinecone even after document deletion
   - **Workaround needed:** Manual embedding deletion via embedding service

### Missing Embedding Cleanup

**CRITICAL GAP:** There is no automatic cleanup of Pinecone vectors when documents are deleted.

**Current Flow:**
```
Document Hard Delete
    ↓
[Remove from Database]
    ↓
[Track external_id to prevent re-sync]
    ✗ [Pinecone vectors NOT deleted]
```

**What Should Happen:**
```
Document Hard Delete
    ↓
[Remove from Database]
    ↓
[Track external_id to prevent re-sync]
    ↓
[Delete vectors from Pinecone] ← MISSING
    ↓
[Clear embedding_generated flag]
```

**Available Method (Not Automatically Called):**
```python
# From embedding_service.py (lines 229-274)
def delete_document_embeddings(
    self,
    document_ids: List[str],
    tenant_id: str,
    db: Session
) -> Dict:
    """Delete embeddings for specific documents."""
    success = self.vector_store.delete_documents(
        doc_ids=document_ids,
        tenant_id=tenant_id
    )
    
    if success:
        # Update database to clear embedded_at
        db.query(Document).filter(
            Document.id.in_(document_ids),
            Document.tenant_id == tenant_id
        ).update({
            'embedded_at': None,
            'embedding_generated': False
        }, synchronize_session=False)
        db.commit()
```

**Recommended Fix:**
- Call `embedding_service.delete_document_embeddings()` after hard delete
- Implement cascade deletion in deletion routes
- Or: Create post-delete hook to clean up Pinecone vectors

---

## 6. KNOWLEDGE GAP ANSWERS: Storage & Searchability

### Knowledge Gap Flow

**File:** `/backend/database/models.py` (lines 589-714)

```
1. Documents Analyzed
    ↓
2. Knowledge Gaps Identified (via LLM analysis)
    ↓
    - KnowledgeGap created with questions
    - Related documents tracked
    ↓
3. Gap Answers Submitted (via /api/knowledge/gaps/<gap_id>/answers)
    ↓
    - GapAnswer records created
    - Can be text or voice transcription
    - Timestamp & user tracked
    ↓
4. [OPTIONAL] Integration into RAG
    ↓
    - rebuild_embedding_index() includes answers
    ↓
5. Gaps marked as VERIFIED
```

### Data Model

#### KnowledgeGap Model
```python
class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"
    
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    
    # Gap content
    title = Column(String(500))
    description = Column(Text)
    category = Column(Enum(GapCategory))  # decision, technical, process, context, etc.
    priority = Column(Integer, default=3)  # 1-5
    
    # Status tracking
    status = Column(Enum(GapStatus), default=GapStatus.OPEN)  # open, in_progress, answered, verified, closed
    
    # Questions to answer
    questions = Column(JSON, default=list)  # List of question objects
    
    # Context for RAG
    context = Column(JSON, default=dict)
    related_document_ids = Column(JSON, default=list)
    
    # Feedback & Quality
    feedback_useful = Column(Integer, default=0)
    feedback_not_useful = Column(Integer, default=0)
    quality_score = Column(Float, default=0.0)
    fingerprint = Column(String(32), index=True)  # For deduplication
    
    # Relationships
    answers = relationship("GapAnswer", back_populates="knowledge_gap")
```

#### GapAnswer Model
```python
class GapAnswer(Base):
    __tablename__ = "gap_answers"
    
    id = Column(String(36), primary_key=True)
    knowledge_gap_id = Column(String(36), ForeignKey("knowledge_gaps.id"), index=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    
    # Answer content
    question_index = Column(Integer)  # Which question in gap.questions
    question_text = Column(Text)      # Snapshot of question at time of answer
    answer_text = Column(Text)        # The answer
    
    # Voice transcription metadata
    is_voice_transcription = Column(Boolean, default=False)
    audio_file_path = Column(String(500))
    transcription_confidence = Column(Float)
    transcription_model = Column(String(100))
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verified_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True))
```

### Answer Submission

**File:** `/backend/api/knowledge_routes.py` (lines 308-379)

```python
@knowledge_bp.route('/gaps/<gap_id>/answers', methods=['POST'])
@require_auth
def submit_answer(gap_id: str):
    """Submit an answer to a knowledge gap question."""
    data = request.get_json()
    
    service = KnowledgeService(db)
    answer, error = service.submit_answer(
        gap_id=gap_id,
        question_index=data.get('question_index'),
        answer_text=data['answer_text'],
        user_id=g.user_id,
        tenant_id=g.tenant_id
    )
```

**File:** `/backend/services/knowledge_service.py` (lines 1379-1450)

```python
def submit_answer(
    self,
    gap_id: str,
    question_index: int,
    answer_text: str,
    user_id: str,
    tenant_id: str
) -> Tuple[Optional[GapAnswer], Optional[str]]:
    """Submit an answer to a knowledge gap question."""
    
    # Create GapAnswer record
    answer = GapAnswer(
        knowledge_gap_id=gap_id,
        user_id=user_id,
        question_index=question_index,
        question_text=gap.questions[question_index]['text'],  # Snapshot
        answer_text=answer_text,
        created_at=utc_now()
    )
    
    db.add(answer)
    db.commit()
    return answer, None
```

### Integration into RAG: Complete Knowledge Transfer

**File:** `/backend/services/knowledge_service.py` (lines 1848-1942)

```python
def complete_knowledge_process(
    self,
    tenant_id: str,
    mark_completed: bool = True
) -> Dict:
    """
    Integrate all answered knowledge gaps into RAG embedding index.
    
    Process:
    1. Collect all answered questions
    2. Rebuild embedding index (includes answers)
    3. Mark gaps as VERIFIED
    """
    
    # Get all answered gaps
    answered_gaps = self.db.query(KnowledgeGap).filter(
        KnowledgeGap.tenant_id == tenant_id,
        KnowledgeGap.status.in_([
            GapStatus.ANSWERED,
            GapStatus.IN_PROGRESS,
            GapStatus.OPEN
        ])
    ).all()
    
    # Count answers
    all_answers = self.db.query(GapAnswer).join(
        KnowledgeGap,
        GapAnswer.knowledge_gap_id == KnowledgeGap.id
    ).filter(
        KnowledgeGap.tenant_id == tenant_id
    ).all()
    
    # Rebuild embedding index (includes answers automatically)
    rebuild_result = self.rebuild_embedding_index(
        tenant_id=tenant_id,
        force=True  # Force rebuild to ensure answers included
    )
    
    # Mark gaps with answers as VERIFIED
    for gap in answered_gaps:
        gap_answers = self.db.query(GapAnswer).filter(
            GapAnswer.knowledge_gap_id == gap.id
        ).count()
        
        if gap_answers > 0:
            gap.status = GapStatus.VERIFIED
            gap.updated_at = utc_now()
    
    self.db.commit()
    
    return {
        'success': True,
        'answers_integrated': len(all_answers),
        'documents_indexed': rebuild_result.get('documents_processed', 0),
        'gaps_completed': gaps_completed,
        'message': f'Successfully integrated {len(all_answers)} answers into RAG'
    }
```

### Searchability of Answers

**Current Status:** Answers are included in RAG BUT with **limitations**:

1. **How Answers Get Searchable:**
   - `rebuild_embedding_index()` collects all GapAnswer records
   - Converts answers to documents for embedding
   - Chunks and embeds them to Pinecone
   - Tenant isolation maintained

2. **Limitations:**
   - Answers are NOT automatically re-embedded when:
     - A new answer is submitted
     - An answer is updated
     - Need manual rebuild_embedding_index() call
   - No automatic trigger after submit_answer()

3. **What Gets Embedded:**
   - Question text (from snapshot in GapAnswer.question_text)
   - Answer text (from GapAnswer.answer_text)
   - Metadata: gap_id, user_id, created_at, is_verified

### API Endpoint for Integration

**File:** `/backend/api/knowledge_routes.py` (endpoint assumed, not shown in provided code)

```
POST /api/knowledge/complete-process
{
    "mark_completed": true  // Mark gaps as verified after integration
}
```

**Returns:**
```json
{
    "success": true,
    "answers_integrated": 42,
    "documents_indexed": 500,
    "chunks_created": 2500,
    "gaps_completed": 35,
    "message": "Successfully integrated 42 answers into RAG knowledge base"
}
```

---

## Summary Table

| Component | Technology | Details |
|-----------|-----------|---------|
| **Vector Store** | Pinecone (Serverless) | Index: knowledgevault, Dim: 1536, Metric: Cosine |
| **Embeddings** | Azure OpenAI | Model: text-embedding-3-large, 1536 dimensions |
| **LLM (Chat)** | Azure OpenAI | Model: gpt-5-chat, Temp: 0.1 for facts |
| **LLM (Analysis)** | Azure OpenAI | Multiple models for gap detection & ranking |
| **Chunking** | Custom (pinecone_store.py) | 2000 chars, 400 overlap, sentence-aware |
| **Search** | Enhanced (enhancements_search_service.py) | Query expansion, reranking, MMR, freshness |
| **Reranking** | sentence-transformers | cross-encoder/ms-marco-MiniLM-L-12-v2 |
| **Tenant Isolation** | Pinecone Namespaces + Metadata | 3-layer: namespace, metadata, application |
| **Database** | PostgreSQL | SQLAlchemy ORM with full audit trail |

---

## Critical Issues & Gaps

### 1. Missing Embedding Cleanup (CRITICAL)
- **Issue:** Document hard delete doesn't remove Pinecone vectors
- **Impact:** Deleted documents remain searchable
- **Fix Needed:** Call `embedding_service.delete_document_embeddings()` after hard delete

### 2. Answer Embedding Not Auto-Triggered
- **Issue:** Submitted answers not automatically embedded
- **Impact:** Need manual `complete_knowledge_process()` call to make answers searchable
- **Fix Needed:** Add post-submit hook or integrate into answer submission flow

### 3. No Search/Chat API Endpoint
- **Issue:** No REST endpoint for chatbot queries
- **Impact:** Enhanced search not accessible via API
- **Fix Needed:** Create `/api/search` or `/api/chat` endpoint using EnhancedSearchService

### 4. Hallucination Detection Optional
- **Issue:** Citation validation not enforced
- **Impact:** LLM may cite sources without verification
- **Risk:** Misinformation if source documents are incorrect

---

## Deployment Checklist

- [ ] Pinecone API key configured (PINECONE_API_KEY)
- [ ] Azure OpenAI endpoint & keys configured
- [ ] Embedding deployment name correct (text-embedding-3-large)
- [ ] Chat deployment name correct (gpt-5-chat)
- [ ] Database tables created (alembic migrations)
- [ ] Create Pinecone index "knowledgevault" or update PINECONE_INDEX env var
- [ ] Test embedding service: `embedding_service.embed_tenant_documents()`
- [ ] Test search: `enhanced_search.search_and_answer()`
- [ ] Verify tenant isolation with multiple tenants
- [ ] Monitor Pinecone vector count and costs
- [ ] Set up deletion cleanup process (cron job recommended)
- [ ] Add search/chat API endpoint if needed

