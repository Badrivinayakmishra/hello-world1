# 2nd Brain - Quick Start & Development Guide

## Project Overview

**2nd Brain** is an AI-powered knowledge transfer system that:
- Captures knowledge from emails, Slack, and GitHub
- Identifies knowledge gaps through interactive Q&A
- Provides intelligent search with RAG (Retrieval-Augmented Generation)
- Generates training materials and exit interview content

**Stack**: Next.js 14 (Frontend) + Flask (Backend) + Azure OpenAI + BERTopic

---

## Quick Start (5 minutes)

### 1. Start Backend
```bash
cd /Users/rishitjain/Downloads/2nd-brain/backend
pip install -r requirements.txt
python app_universal.py
# Opens on: http://localhost:5003
```

### 2. Start Frontend
```bash
cd /Users/rishitjain/Downloads/2nd-brain/frontend
npm install  # First time only
npm run dev
# Opens on: http://localhost:3000
```

### 3. Access Application
- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:5003/api/stats

---

## File Structure at a Glance

```
2nd-brain/
├── frontend/                          # Next.js 14 app
│   ├── app/                          # Pages (routing)
│   │   ├── page.tsx                  # Home → Chat
│   │   ├── documents/page.tsx        # Document management
│   │   ├── projects/page.tsx         # Project view
│   │   ├── knowledge-gaps/page.tsx   # Gap collection
│   │   └── ...
│   ├── components/                   # React components
│   │   ├── chat/ChatInterface.tsx    # Main chat UI
│   │   ├── knowledge-gaps/KnowledgeGaps.tsx  # Gap form
│   │   └── ...
│   └── package.json
│
└── backend/                           # Flask API
    ├── app_universal.py              # Main app (43 endpoints)
    ├── rag/                          # RAG implementations
    │   └── enhanced_rag_v2.py        # PRODUCTION RAG
    ├── gap_analysis/                 # Gap detection
    ├── club_data/                    # BEAT data storage
    ├── config/config.py              # Configuration
    └── requirements.txt
```

---

## Architecture in 1 Minute

### Data Flow: User Query → Answer

```
1. User types query in ChatInterface
2. Frontend: POST /api/search with query
3. Backend RAG pipeline:
   - Classify query type
   - Retrieve documents (BM25 + semantic)
   - Re-rank by relevance
   - Remove duplicates (MMR)
   - Generate answer with LLM
   - Detect hallucinations
4. Return answer + source citations
5. Frontend displays with clickable source links
```

### Data Storage

```
BEAT Club Data:
  /club_data/classified/
    ├── work/              # Confirmed work docs
    ├── personal/          # Removed from RAG
    ├── spam/              # Filtered
    └── uncertain/         # Needs review
  
  /club_data/search_index.pkl  (1.4GB TF-IDF vectors)
```

### RAG Pipeline Stages

```
Query → Classify → Retrieve → Rerank → Deduplicate → Generate Answer
         (type)   (BM25+sem) (cross)   (MMR)         (LLM+verify)
```

---

## Key Components Deep Dive

### 1. ChatInterface.tsx (Frontend)
- **Purpose**: Main conversation interface
- **Calls**: `POST /api/search` 
- **Features**:
  - Message history
  - Source citations
  - Feedback (thumbs up/down)
  - Quick action cards
- **Location**: `/frontend/components/chat/ChatInterface.tsx` (430 lines)

### 2. enhanced_rag_v2.py (Backend)
- **Purpose**: State-of-the-art RAG implementation
- **Key Classes**:
  - `QueryClassifier` - Determines retrieval strategy
  - `CrossEncoderReranker` - Scores relevance
  - `HallucinationDetector` - Verifies answers
  - `MMRSelector` - Removes duplicates
- **Features**: 
  - 6 query types with different params
  - Temporal weighting (boost recent docs)
  - Adaptive retrieval (more sources for complex queries)
  - Result caching
- **Location**: `/backend/rag/enhanced_rag_v2.py` (1200+ lines)

### 3. KnowledgeGaps.tsx (Frontend)
- **Purpose**: Collect tacit knowledge from users
- **Features**:
  - Voice input (Whisper transcription)
  - Text input for answers
  - Progress tracking per project
  - Severity badges (high/medium/low)
- **Calls**: 
  - `GET /api/questions` - Fetch gaps
  - `POST /api/questions/answer` - Submit answers
  - `POST /api/transcribe` - Whisper API
- **Location**: `/frontend/components/knowledge-gaps/KnowledgeGaps.tsx` (888 lines)

### 4. gap_analyzer.py (Backend)
- **Purpose**: Identify missing information
- **Process**:
  1. Summarize project documents
  2. Use LLM to find gaps
  3. Categorize into 8 types
  4. Assign severity levels
- **Gap Types**:
  - `project_goal` - Objectives missing
  - `success_criteria` - Metrics missing
  - `lesson_learned` - Insights missing
  - Plus 5 more...
- **Location**: `/backend/gap_analysis/gap_analyzer.py`

---

## Common Development Tasks

### Task: Add a New API Endpoint

1. **Define endpoint in `app_universal.py`**:
```python
@app.route('/api/my-feature', methods=['POST'])
def my_feature():
    data = request.get_json()
    result = process_data(data)
    return jsonify(result)
```

2. **Call from frontend**:
```typescript
const response = await axios.post(`${API_BASE}/my-feature`, {
  param: value
})
```

### Task: Modify RAG Parameters

**File**: `/backend/config/config.py`

```python
# Change these values:
Config.TOP_K_RETRIEVAL = 10        # How many docs to retrieve
Config.RERANK_TOP_K = 5            # Keep top N after re-ranking
Config.MAX_CONTEXT_LENGTH = 8000   # Max context for LLM
```

Or dynamically in `enhanced_rag_v2.py`:
```python
rag = EnhancedRAGv2(
    use_reranker=True,     # Use cross-encoder
    use_mmr=True,          # Deduplicate results
    cache_results=True     # Cache queries
)
```

### Task: Add New Gap Type

1. **Add to question types in `KnowledgeGaps.tsx`**:
```typescript
const typeLabels: Record<string, string> = {
  // ... existing types
  'new_gap_type': 'My New Type'
}
```

2. **Update gap analyzer in `gap_analyzer.py`**:
```python
def _categorize_gaps(self, gaps):
    categories = {
        'new_gap_type': 'Description of new gap type',
        # ... rest
    }
```

### Task: Debug RAG Results

**Enable logging in `enhanced_rag_v2.py`**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug(f"Query type: {query_type}")
logger.debug(f"Retrieved {len(results)} documents")
logger.debug(f"Top source: {results[0]['metadata']}")
```

Or check `/tmp/rag_debug.log` if it exists.

---

## Data Structures Reference

### Document/Message Format
```json
{
  "metadata": {
    "doc_id": "space_msg_12345",
    "source": "gmail",
    "sender": "user@example.com",
    "timestamp": "2025-01-15T10:30:00Z",
    "project": "Project Name",
    "category": "work"
  },
  "content": "Full text of message..."
}
```

### RAG Response Format
```json
{
  "answer": "The answer is...",
  "sources": [
    {
      "doc_id": "...",
      "content": "...",
      "score": 0.92,
      "metadata": {...}
    }
  ],
  "confidence": 0.85,
  "citation_coverage": 85.5
}
```

### Knowledge Gap Format
```json
{
  "project_name": "Project X",
  "gaps": [
    {
      "type": "project_goal",
      "description": "...",
      "severity": "high",
      "is_standard": true
    }
  ],
  "questions": [
    {
      "question": "What were the objectives?",
      "gap_type": "project_goal",
      "severity": "high"
    }
  ]
}
```

---

## API Endpoints Cheat Sheet

### Search & RAG
```
POST /api/search
  Input: {query: string}
  Output: {answer, sources, confidence}

GET /api/document/<doc_id>/view
  Output: {content, metadata}
```

### Knowledge Gaps
```
GET /api/questions
  Output: [gap objects for all projects]

POST /api/questions/answer
  Input: {gap_id, answer, project}
  Output: {success}

POST /api/projects/<project_id>/gaps
  Output: {gaps, questions}
```

### Documents
```
GET /api/documents/review
  Output: [pending documents]

POST /api/documents/<doc_id>/decision
  Input: {decision: 'accept'|'reject'}

GET /api/documents/stats
  Output: {total, by_category, classified}
```

### Integrations
```
GET /api/connectors
  Output: [connected services]

POST /api/connectors/gmail/sync
  Output: {synced_count, new_documents}
```

---

## Troubleshooting

### Problem: "Connection refused" on port 5003
**Solution**: Make sure backend is running
```bash
cd /Users/rishitjain/Downloads/2nd-brain/backend
python app_universal.py
```

### Problem: Search index takes 30+ seconds to load
**Solution**: This is normal for 1.4GB index. Subsequent queries are cached.
- Check `/tmp/rag_cache.pkl` is being written
- Set `cache_results=True` in RAG initialization

### Problem: Whisper transcription not working
**Solution**: Check microphone permissions
- Frontend: Allow microphone access in browser
- Backend: Ensure OpenAI API key is set
- Test: Try text input instead of voice

### Problem: Knowledge gaps not appearing
**Solution**: 
1. Check if project has documents: `GET /api/projects/{id}/documents`
2. Check if gap analyzer is running: Look for log messages
3. Manually trigger: `POST /api/projects/{id}/gaps`

### Problem: High hallucination in answers
**Solution**: 
1. Enable hallucination detector: `use_reranker=True`
2. Lower `MAX_CONTEXT_LENGTH` to reduce noise
3. Check source quality: `GET /api/documents/stats`
4. Increase `RERANK_TOP_K` to keep better sources

---

## Performance Tips

### Speed up RAG queries
```python
# In enhanced_rag_v2.py
rag = EnhancedRAGv2(
    cache_results=True,      # Cache repeated queries
    use_mmr=True,            # Remove duplicates (faster)
    use_reranker=False       # Skip if not needed
)
```

### Reduce memory usage
```python
# In config.py
Config.TOP_K_RETRIEVAL = 5        # Retrieve fewer docs
Config.MAX_CONTEXT_LENGTH = 4000  # Shorter context
```

### Improve accuracy
```python
# In config.py
Config.RERANK_TOP_K = 10          # Keep more sources
Config.TOP_K_RETRIEVAL = 20       # Retrieve more candidates
```

---

## Testing Checklist

- [ ] Backend starts without errors: `python app_universal.py`
- [ ] Frontend loads: http://localhost:3000
- [ ] Chat search works: Type a query, get answer
- [ ] Sources are clickable: Click a source, view document
- [ ] Gap identification works: Go to Knowledge Gaps page
- [ ] Voice input works: Click microphone, speak, get transcription
- [ ] Document upload works: Upload a new document, see in review queue
- [ ] Project view works: See documents grouped by project

---

## Next Steps

1. **Understand RAG**: Read `/backend/rag/enhanced_rag_v2.py` (well-commented)
2. **Explore Data**: Check `/backend/club_data/classified/work/` for structure
3. **Test API**: Use Postman/curl to hit endpoints directly
4. **Modify UI**: Edit components in `/frontend/components/`
5. **Add Features**: Create new endpoints following existing patterns

---

## Useful Commands

```bash
# Check API status
curl http://localhost:5003/api/stats

# List all projects
curl http://localhost:5003/api/projects

# Test search
curl -X POST http://localhost:5003/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"What is BEAT?"}'

# Check logs
tail -f /tmp/2nd_brain.log

# Rebuild search index
python /Users/rishitjain/Downloads/2nd-brain/backend/build_embedding_index.py
```

---

## Documentation Files

- **`CODEBASE_ARCHITECTURE.md`** - Complete architecture (this directory)
- **`README.md`** - Project overview
- **`requirements.txt`** - Dependencies
- **`config/config.py`** - All configuration options

---

**Last Updated**: December 3, 2025
**Created for**: Rishit Jain
**Maintained in**: `/Users/rishitjain/Downloads/2nd-brain/`
