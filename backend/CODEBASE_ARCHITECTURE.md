# 2nd Brain - Complete Architecture & Data Flow Summary

**Generated: December 3, 2025**
**Codebase Locations:**
- Frontend: `/Users/rishitjain/Downloads/2nd-brain/frontend`
- Backend: `/Users/rishitjain/Downloads/2nd-brain/backend`

---

## 1. FRONTEND STRUCTURE (Next.js 14 + React 18)

### Architecture Overview
- **Framework**: Next.js 14.0.0 with App Router
- **Styling**: Tailwind CSS 3.3.5
- **HTTP Client**: Axios 1.6.0
- **TypeScript**: 5.2.2
- **Deployment Port**: 3000 (dev)

### Page Structure & Routing

```
/app (Next.js App Router)
├── page.tsx                      # Home page -> ChatInterface component
├── layout.tsx                    # Root layout (basic HTML setup)
├── login/page.tsx               # Login page
├── documents/page.tsx           # Documents listing page
├── projects/page.tsx            # Projects overview page
├── knowledge-gaps/page.tsx       # Knowledge gap identification page
├── training-guides/page.tsx      # Training materials page
├── integrations/page.tsx         # API connectors (Gmail, Slack, GitHub)
└── settings/page.tsx            # User settings

/components (Reusable UI Components)
├── chat/ChatInterface.tsx        # Main chatbot interface (430 lines)
│   ├── Message rendering with sources
│   ├── RAG query handling (POST to /api/search)
│   ├── Feedback system (thumbs up/down, copy)
│   ├── Source citation links
│   └── Welcome cards with quick actions
│
├── knowledge-gaps/KnowledgeGaps.tsx  # Gap analysis UI (888 lines)
│   ├── Voice input (OpenAI Whisper transcription)
│   ├── Project-based gap organization
│   ├── Gap severity badges (high/medium/low)
│   ├── Question type badges
│   ├── Answer submission with progress tracking
│   └── Project expansion/collapse
│
├── documents/Documents.tsx       # Document browser (623 lines)
│   ├── Filter by category/status
│   ├── Upload new documents
│   ├── Document classification review
│   └── Document detail view
│
├── projects/Projects.tsx         # Project management (401 lines)
│   ├── Project clustering display
│   ├── Project statistics
│   ├── Document count per project
│   └── Project-specific RAG search
│
├── training-guides/TrainingGuides.tsx  # Training materials (293 lines)
│   ├── Generated presentations
│   ├── Training videos
│   └── Download options
│
├── integrations/Integrations.tsx # Data connectors (521 lines)
│   ├── Gmail OAuth authentication
│   ├── Slack connection
│   ├── GitHub integration
│   └── Sync status monitoring
│
├── settings/Settings.tsx         # User preferences (80 lines)
│   ├── Account settings
│   └── System configuration
│
├── auth/Login.tsx                # Authentication UI (228 lines)
│   ├── Login form
│   └── User validation
│
└── shared/Sidebar.tsx            # Navigation sidebar (243 lines)
    ├── Main menu items
    ├── User profile
    ├── Settings access
    └── Active item highlighting
```

### API Communication

**Base URL**: `http://localhost:5003/api`

#### Key Frontend Endpoints Used:

1. **ChatInterface.tsx** calls:
   - `POST /api/search` - RAG query with answer generation
   - `POST /api/feedback` - User feedback on answers
   - `GET /api/document/{doc_id}/view` - View document details

2. **KnowledgeGaps.tsx** calls:
   - `POST /api/transcribe` - Voice-to-text (Whisper)
   - `GET /api/questions` - Fetch knowledge gaps
   - `POST /api/questions/answer` - Submit gap answers
   - `POST /api/projects/{project_id}/gaps` - Project-specific gaps
   - `GET /api/projects` - List projects

3. **Documents.tsx** calls:
   - `POST /api/documents/upload` - Upload documents
   - `GET /api/documents/review` - Review pending docs
   - `POST /api/documents/{doc_id}/decision` - Accept/reject docs
   - `GET /api/documents/categories` - Document categories

4. **Projects.tsx** calls:
   - `GET /api/projects` - All projects
   - `GET /api/projects/{project_id}` - Project details
   - `GET /api/projects/{project_id}/documents` - Project documents

5. **Integrations.tsx** calls:
   - `GET /api/connectors` - List connected sources
   - `POST /api/connectors/add` - Add new connector
   - `GET /api/connectors/gmail/auth` - Gmail OAuth flow
   - `POST /api/connectors/gmail/sync` - Sync Gmail

---

## 2. BACKEND STRUCTURE (Flask + Python ML/NLP)

### Architecture Overview
- **Framework**: Flask + Flask-CORS
- **Python Version**: 3.8+
- **Main Application**: `app_universal.py` (port 5003)
- **LLM**: Azure OpenAI (GPT-5-chat, text-embedding-3-large)
- **Database**: Pickle-based indexes, JSON metadata

### Directory Structure

```
backend/
├── app.py                           # Original Flask app (deprecated)
├── app_universal.py                 # Main production app (2454 lines)
├── app_complete.py                  # Alternative implementation
├── app_project_classification.py     # Project classification only
│
├── config/
│   └── config.py                    # Centralized configuration
│       ├── BASE_DIR, DATA_DIR, OUTPUT_DIR
│       ├── Model paths (embeddings, LLM)
│       ├── Clustering parameters (MIN_CLUSTER_SIZE=5, UMAP settings)
│       ├── Classification thresholds
│       ├── RAG settings (TOP_K_RETRIEVAL=10, RERANK_TOP_K=5)
│       └── Gap analysis configuration
│
├── rag/                              # Retrieval-Augmented Generation
│   ├── enhanced_rag.py              # RAG v1 (basic version)
│   ├── enhanced_rag_v2.py           # RAG v2.1 (PRODUCTION)
│   │   ├── QueryClassifier - Determines query type & retrieval params
│   │   ├── HallucinationDetector - Prevents false claims
│   │   ├── CrossEncoderReranker - Re-ranks by relevance
│   │   ├── MMRSelector - Maximal Marginal Relevance selection
│   │   ├── TemporalAwareness - Boosts recent documents
│   │   ├── AdaptiveRetrieval - More sources for complex queries
│   │   └── Cache for repeated queries
│   │
│   ├── hierarchical_rag.py          # Graph + Vector retrieval
│   ├── semantic_chunker.py          # Document chunking strategies
│   ├── stakeholder_graph.py          # Relationship graph building
│   └── multimodal.py                # Image/text processing
│
├── gap_analysis/                     # Knowledge gap detection
│   ├── gap_analyzer.py              # GapAnalyzer class
│   │   ├── analyze_project_gaps() - Find missing info
│   │   ├── _create_project_summary() - Summarize docs
│   │   ├── _identify_gaps_with_llm() - LLM-based analysis
│   │   └── _categorize_gaps() - Gap types
│   │
│   └── question_generator.py         # QuestionGenerator class
│       ├── generate_followup_questions() - Create prompts
│       └── _generate_additional_questions() - LLM generation
│
├── knowledge_capture/                # Exit interview system
│   └── exit_interview.py             # Structured interview generation
│
├── club_data/                         # BEAT Club data storage
│   ├── classified/                   # Classified messages
│   │   ├── work/                     # Confirmed work messages
│   │   ├── personal/                 # Personal messages
│   │   ├── spam/                     # Spam messages
│   │   ├── uncertain/                # Uncertain classification
│   │   ├── rishi2205/                # User-specific data
│   │   └── [other-users]/
│   │
│   ├── connectors/                   # OAuth tokens, connection state
│   │   ├── gmail/
│   │   ├── slack/
│   │   └── github/
│   │
│   └── search_index.pkl              # TF-IDF search vectors (1.4GB)
│       └── Contains:
│           ├── doc_ids: Document ID list
│           ├── doc_vectors: TF-IDF vectors
│           ├── doc_index: Document metadata & content
│           └── vectorizer: sklearn TfidfVectorizer
│
├── data/                              # Original Enron dataset
│   ├── employee_clusters/            # Clustered by employee (152 dirs)
│   ├── project_clusters/             # Clustered by project (153 dirs)
│   ├── unclustered/                  # Flattened documents
│   ├── processed/                    # Intermediate results
│   ├── search_index.pkl              # Enron search index
│   └── stakeholder_graph.pkl         # Relationship graph
│
├── src/                               # Modular source code
│   ├── clustering/
│   │   ├── employee_clustering.py    # Group by sender/recipient
│   │   ├── project_clustering.py     # BERTopic semantic clusters
│   │   ├── intelligent_project_clustering.py
│   │   └── llm_first_clusterer.py
│   │
│   ├── classification/
│   │   ├── work_personal_classifier.py  # GPT-based filtering
│   │   ├── project_classifier.py
│   │   └── global_project_classifier.py
│   │
│   ├── gap_analysis/
│   │   ├── gap_analyzer.py
│   │   └── question_generator.py
│   │
│   ├── knowledge_graph/
│   │   ├── knowledge_graph.py         # Neo4j graph builder
│   │   └── vector_database.py         # ChromaDB indexing
│   │
│   └── content_generation/
│       ├── powerpoint_generator.py    # PPTX creation
│       ├── video_generator.py          # MP4 generation
│       └── gamma_presentation.py       # Specialized format
│
└── templates/                          # HTML templates (deprecated)
    └── index.html, etc.
```

---

## 3. DATA ORGANIZATION & STORAGE

### Data Hierarchy

```
BEAT Club Data (Primary)
├── Gmail messages + Slack + GitHub
├── Classified by: work/personal/spam/uncertain
├── Stored in: /club_data/classified/{category}/{username}/
├── Format: JSON lines with metadata
└── Search Index: club_data/search_index.pkl (1.4GB)

Enron Dataset (Secondary - Historical)
├── Original emails from Enron scandal
├── Stored in: /data/
├── Clustered by:
│   ├── Employee (152 clusters)
│   └── Project (153 clusters)
└── Search Index: data/search_index.pkl
```

### Data Structures

#### Document/Message Format (JSON)
```json
{
  "metadata": {
    "doc_id": "space_msg_12345",
    "file_name": "message_from_user.txt",
    "source": "gmail",
    "sender": "rishi2205@gmail.com",
    "timestamp": "2025-01-15T10:30:00Z",
    "project": "BEAT Project Alpha",
    "category": "work",
    "classification": {"type": "work", "confidence": 0.94}
  },
  "content": "Full message content...",
  "chunk_id": "doc_001_chunk_1",
  "chunk_seq": 1
}
```

#### Search Index Structure (Pickle)
```python
{
    'doc_ids': [list of 1000s of IDs],
    'doc_vectors': numpy array (n_docs, n_features),
    'doc_index': {
        'doc_id': {
            'metadata': {...},
            'content': "...",
            'cluster_label': 'project_name'
        }
    },
    'vectorizer': TfidfVectorizer instance
}
```

#### Embedding Index (for RAG)
```python
{
    'chunks': [list of text chunks],
    'chunk_ids': [list of chunk IDs],
    'embeddings': numpy array (n_chunks, 3072),  # text-embedding-3-large
    'metadata': [metadata for each chunk]
}
```

#### Knowledge Gaps Format (JSON)
```json
{
  "project_name": "BEAT Project Alpha",
  "gaps": [
    {
      "type": "project_goal",
      "description": "Missing project objectives",
      "severity": "high",
      "is_standard": true
    }
  ],
  "questions": [
    {
      "question": "What were the main goals?",
      "gap_type": "project_goal",
      "severity": "high"
    }
  ],
  "missing_elements": ["budget", "timeline", "success_metrics"]
}
```

### BEAT Data Storage Details

```
club_data/classified/
├── work/                           # Confirmed work messages
│   ├── rishi2205/
│   │   ├── messages_001.jsonl
│   │   ├── metadata.json
│   │   └── summary.json
│   ├── syedislam/
│   └── [other-users]/
│
├── personal/                       # Removed from RAG
├── spam/                           # Filtered out
├── uncertain/                      # Flagged for review
└── search_index.pkl               # TF-IDF vectors for all work docs
```

---

## 4. RAG IMPLEMENTATION (Enhanced RAG v2.1)

### RAG Pipeline Architecture

```
User Query
    ↓
┌─────────────────────────────────┐
│ 1. Query Classification          │
│ - Detect query type             │
│ - Set retrieval parameters       │
│ - Choose weighting scheme        │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 2. Multi-Stage Retrieval        │
│ ├─ BM25 (keyword matching)      │
│ ├─ Semantic (embeddings)        │
│ ├─ Freshness weighting          │
│ └─ Metadata filtering           │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 3. Re-ranking (Cross-Encoder)   │
│ - Score semantic relevance      │
│ - Keep top-5 sources            │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 4. Duplicate Removal            │
│ - MMR (Maximal Marginal Rel.)   │
│ - Diverse results               │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 5. Context Building             │
│ - Format top sources            │
│ - Include metadata              │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 6. Answer Generation (LLM)      │
│ - GPT-5-chat with context       │
│ - Include citations             │
│ - Temperature: 0.3              │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 7. Hallucination Detection      │
│ - Verify claims against sources │
│ - Flag unsupported statements   │
│ - Calculate citation coverage   │
└────────┬────────────────────────┘
         ↓
   Answer + Sources
```

### Query Classification Types

| Type | Semantic Weight | BM25 Weight | Top K | MMR Lambda | Use Case |
|------|-----------------|-------------|-------|------------|----------|
| **Factual** | 75% | 25% | 12 | 0.8 | "What was the budget?" |
| **Exploratory** | 60% | 40% | 15 | 0.6 | "Tell me about the project" |
| **Comparative** | 65% | 35% | 20 | 0.5 | "Compare two projects" |
| **Procedural** | 70% | 30% | 12 | 0.7 | "How was it done?" |
| **Temporal** | 60% | 40% | 15 | 0.6 | "When did it happen?" |
| **Aggregation** | 55% | 45% | 20 | 0.5 | "List all projects" |

### RAG Components

1. **QueryClassifier** - Determines best retrieval strategy
2. **EmbeddingRetriever** - Semantic search using text-embedding-3-large
3. **BM25Retriever** - Keyword matching
4. **CrossEncoderReranker** - Scores retrieved documents (requires sentence-transformers)
5. **MMRSelector** - Maximal Marginal Relevance for diversity
6. **HallucinationDetector** - Verifies answers against sources
7. **TemporalWeighter** - Boosts recent documents
8. **ConversationContextManager** - Maintains chat history

### Configuration

```python
# app_universal.py
Config.TOP_K_RETRIEVAL = 10        # Initial retrieval
Config.RERANK_TOP_K = 5            # After re-ranking
Config.MAX_CONTEXT_LENGTH = 8000   # Context window
```

---

## 5. BACKEND API ENDPOINTS (43 Total)

### Core RAG & Search
- **`POST /api/search`** - RAG query with answer + sources
- **`GET /api/all-emails`** - Get all indexed documents
- **`GET /api/document/<doc_id>`** - Get document metadata
- **`GET /api/document/<doc_id>/view`** - View document content

### Knowledge Gaps & Questions
- **`GET /api/questions`** - List knowledge gaps
- **`GET /api/questions/generate`** - Generate new gap questions
- **`POST /api/questions/answer`** - Submit answer to gap question
- **`POST /api/questions/analyze-project`** - Analyze project for gaps
- **`GET /api/projects/<project_id>/gaps`** - Project-specific gaps

### Projects & Documents
- **`GET /api/projects`** - List all projects
- **`GET /api/projects/<project_id>`** - Project details
- **`GET /api/projects/<project_id>/documents`** - Project documents
- **`POST /api/projects/reprocess`** - Re-cluster projects
- **`POST /api/documents/upload`** - Upload new document
- **`GET /api/documents/review`** - Documents pending review
- **`POST /api/documents/<doc_id>/decision`** - Accept/reject document
- **`GET /api/documents/ready-for-rag`** - Approved documents
- **`GET /api/documents/stats`** - Document statistics
- **`GET /api/documents/categories`** - Document categories

### Connectors & Integrations
- **`GET /api/connectors`** - List connected sources
- **`POST /api/connectors/add`** - Add new connector
- **`GET /api/connectors/gmail/auth`** - Gmail OAuth flow
- **`GET /api/connectors/gmail/callback`** - OAuth callback
- **`GET /api/connectors/gmail/status`** - Connection status
- **`POST /api/connectors/gmail/disconnect`** - Disconnect source
- **`POST /api/connectors/gmail/sync`** - Sync new data

### Message Filtering
- **`GET /api/messages/review`** - Messages for manual review
- **`GET /api/messages/review/count`** - Count pending reviews
- **`POST /api/messages/decide`** - Classify message (work/personal)

### Stakeholder Graph
- **`GET /api/stakeholders`** - All people mentioned
- **`POST /api/stakeholders/query`** - Find person expertise
- **`GET /api/stakeholders/expertise`** - Person's skills
- **`GET /api/stakeholders/projects`** - Person's projects

### Spaces & Organization
- **`GET /api/spaces`** - User spaces/projects

### Analytics & Feedback
- **`GET /api/stats`** - System statistics
- **`POST /api/feedback`** - Record user feedback (thumbs up/down)
- **`GET /api/feedback/stats`** - Feedback analytics
- **`GET /api/training-materials`** - Generated training content

### Content Generation
- **`POST /api/gamma/generate`** - Generate presentation
- **`GET /api/gamma/preview-structure`** - Preview presentation

### Utilities
- **`POST /api/transcribe`** - Speech-to-text (Whisper)

---

## 6. KNOWLEDGE GAPS IDENTIFICATION & STORAGE

### Gap Analysis Process

```python
# gap_analyzer.py
class GapAnalyzer:
    def analyze_project_gaps(project_data):
        """
        1. Create project summary from documents
           - Count documents
           - Extract subjects, keywords, people, dates
           - Identify document types
        
        2. Identify gaps using LLM
           - Query: "What information is missing from these documents?"
           - Look for: goals, success criteria, outcomes, decisions, lessons
           - Flag: budget, timeline, stakeholders, risks
        
        3. Categorize gaps
           - project_goal: Project objectives missing
           - success_criteria: Metrics/KPIs missing
           - project_outcome: Final results missing
           - key_decision: Important decisions not documented
           - lesson_learned: Insights/learnings missing
           - stakeholder: Participant info missing
           - process: How it was done unclear
           - risk: Risk management not documented
        
        4. Assign severity
           - HIGH: Critical gaps affecting understanding
           - MEDIUM: Important but not critical
           - LOW: Nice-to-have information
        
        5. Return structured gaps for frontend
        """
```

### Gap Storage Format

```json
{
  "project_name": "BEAT Initiative",
  "gaps": [
    {
      "type": "project_goal",
      "description": "Project objectives and goals not clearly documented",
      "severity": "high",
      "is_standard": true
    },
    {
      "type": "success_criteria",
      "description": "Success metrics and KPIs not specified",
      "severity": "high",
      "is_standard": true
    }
  ],
  "questions": [
    {
      "question": "What were the primary objectives of this project?",
      "gap_type": "project_goal",
      "severity": "high",
      "answer": null  # Filled when user answers
    }
  ],
  "missing_elements": ["budget", "timeline", "stakeholder_list"]
}
```

### Gap Types (Standard Questions)

1. **project_goal** - "What were the project's main objectives?"
2. **success_criteria** - "How was success measured?"
3. **project_outcome** - "What was the final outcome?"
4. **key_decision** - "What were critical decisions made?"
5. **lesson_learned** - "What lessons were learned?"
6. **stakeholder** - "Who were the key stakeholders?"
7. **process** - "How was the process executed?"
8. **risk** - "What risks were identified and managed?"

### Frontend Gap Collection (KnowledgeGaps.tsx)

1. **Display gaps grouped by project**
2. **Show severity badges** (high/medium/low)
3. **Voice input for answers** (Whisper transcription)
4. **Text input for detailed answers**
5. **Progress tracking** (X of Y questions answered)
6. **Submit answers via** `POST /api/questions/answer`
7. **Store answers for exit interview/knowledge base**

---

## 7. DATA FLOW DIAGRAMS

### User Query Flow

```
Frontend (ChatInterface)
         ↓
   User enters query
         ↓
POST /api/search with {query: string}
         ↓
Backend (app_universal.py)
         ↓
enhanced_rag.search(query)
         ↓
├─ Load search_index.pkl
├─ Classify query type
├─ BM25 retrieval
├─ Semantic retrieval
├─ Re-ranking
├─ Deduplication (MMR)
└─ LLM answer generation
         ↓
Return {
  answer: string,
  sources: [{doc_id, score, content, metadata}],
  confidence: float,
  citation_coverage: float
}
         ↓
Frontend displays answer with:
├─ Main answer text
├─ Source citations [links]
└─ Source list below answer
```

### Document Ingestion Flow

```
Connector (Gmail/Slack/GitHub)
         ↓
Extract messages/files
         ↓
POST /api/documents/upload
         ↓
Backend:
├─ Store in club_data/pending/
├─ Extract metadata
├─ Run classifier: work/personal/spam?
└─ Store result
         ↓
Frontend (Documents page):
├─ Show pending documents
├─ User reviews classification
├─ Clicks accept/reject
         ↓
POST /api/documents/{doc_id}/decision
         ↓
Approved docs:
├─ Move to club_data/classified/work/
├─ Add to search_index
├─ Re-build indexes
└─ Ready for RAG
```

### Gap Identification Flow

```
Project selected in UI
         ↓
POST /api/projects/{project_id}/gaps
         ↓
Backend:
├─ Load project documents
├─ GapAnalyzer.analyze_project_gaps()
├─ Generate standard questions
└─ LLM-based gap detection
         ↓
Return gaps with questions
         ↓
Frontend (KnowledgeGaps):
├─ Display organized by project
├─ Show severity indicators
├─ Enable voice/text answers
         ↓
User answers questions
         ↓
POST /api/questions/answer with {
  gap_id: string,
  answer: string,
  project: string
}
         ↓
Backend stores answer for:
├─ Knowledge base enrichment
├─ Exit interview document
└─ Future training materials
```

---

## 8. KEY TECHNOLOGIES & DEPENDENCIES

### Core ML/NLP Stack
- **Transformers** (4.30.0) - Language models, embeddings
- **Sentence-Transformers** (2.2.0) - Semantic search, cross-encoders
- **BERTopic** (0.15.0) - Topic modeling/clustering
- **UMAP** (0.5.3) - Dimensionality reduction
- **HDBSCAN** (0.8.29) - Density-based clustering

### LLM & Embeddings
- **Azure OpenAI** - GPT-5-chat (answers), text-embedding-3-large (search)
- **LlamaParse** - PDF/document parsing with OCR

### Databases & Indexes
- **ChromaDB** (0.4.0) - Vector database (optional)
- **Neo4j** (5.12.0) - Knowledge graph (optional)
- **Pickle files** - Search indexes, embeddings (primary)

### Frontend Stack
- **Next.js** 14.0.0 - React framework
- **Tailwind CSS** 3.3.5 - Styling
- **Axios** 1.6.0 - HTTP client

### Backend Stack
- **Flask** - Web framework
- **Flask-CORS** - Cross-origin requests
- **Pandas** - Data processing
- **NumPy** - Numerical computing
- **Scikit-learn** - ML utilities (TF-IDF, similarity)

### Content Generation
- **python-pptx** - PowerPoint creation
- **Pillow** - Image processing
- **MoviePy** - Video generation
- **gTTS** - Text-to-speech

---

## 9. CURRENT SYSTEM STATUS & CAPABILITIES

### Fully Implemented
- ✅ RAG search with answer generation
- ✅ Document classification (work/personal)
- ✅ Knowledge gap identification
- ✅ Chatbot interface with sources
- ✅ Feedback system (thumbs up/down)
- ✅ Gmail OAuth integration
- ✅ Voice input (Whisper)
- ✅ Project clustering
- ✅ Stakeholder relationship mapping

### Partially Implemented
- 🟡 Slack integration (configured, not fully tested)
- 🟡 GitHub integration (configured, not fully tested)
- 🟡 Neo4j graph queries (queries generated, not connected)
- 🟡 Video generation (infrastructure ready, not deployed)

### In Development
- 🔄 Training guide generation
- 🔄 Exit interview system
- 🔄 Cross-project gap analysis
- 🔄 Real-time sync optimization

### Known Limitations
- Search index is large (1.4GB) - slow initial load
- RAG v2.1 requires cross-encoder (optional dependency)
- Whisper transcription needs audio quality handling
- Gap questions are template-based, not fully personalized

---

## 10. CONFIGURATION & ENVIRONMENT

### Required Environment Variables (.env)
```
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com
AZURE_OPENAI_API_KEY=<your-key>

# LlamaParse
LLAMAPARSE_API_KEY=<your-key>

# Neo4j (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>

# Gmail OAuth (optional)
GOOGLE_CLIENT_ID=<your-id>
GOOGLE_CLIENT_SECRET=<your-secret>
```

### Key Config Parameters (config.py)

```python
# Model settings
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
LLM_MODEL = "gpt-4o-mini"

# Clustering
MIN_CLUSTER_SIZE = 5
UMAP_N_COMPONENTS = 5

# Classification confidence
WORK_CONFIDENCE_THRESHOLD = 0.85
PERSONAL_CONFIDENCE_THRESHOLD = 0.85

# RAG retrieval
TOP_K_RETRIEVAL = 10
RERANK_TOP_K = 5
MAX_CONTEXT_LENGTH = 8000

# Gap analysis
MAX_QUESTIONS_PER_PROJECT = 10
```

---

## 11. STARTUP INSTRUCTIONS

### Frontend
```bash
cd /Users/rishitjain/Downloads/2nd-brain/frontend
npm install
npm run dev
# Runs on http://localhost:3000
```

### Backend
```bash
cd /Users/rishitjain/Downloads/2nd-brain/backend
pip install -r requirements.txt
python app_universal.py
# Runs on http://localhost:5003
```

### Data Loading
- Backend automatically loads indices on startup:
  - `club_data/search_index.pkl` (BEAT data)
  - `data/search_index.pkl` (Enron data - optional)
  - `club_data/embedding_index.pkl` (if exists)

---

## 12. NOTABLE CODE FILES TO UNDERSTAND

### Must-Read Files
1. `/backend/app_universal.py` - Main backend, all endpoints
2. `/backend/rag/enhanced_rag_v2.py` - RAG implementation
3. `/frontend/components/chat/ChatInterface.tsx` - Chat UI
4. `/frontend/components/knowledge-gaps/KnowledgeGaps.tsx` - Gap collection
5. `/backend/gap_analysis/gap_analyzer.py` - Gap detection logic
6. `/backend/config/config.py` - All configuration

### Key Function Signatures

```python
# RAG Query
enhanced_rag.search(query: str) -> Dict[str, Any]
# Returns: {answer, sources, confidence, citation_coverage}

# Gap Analysis
gap_analyzer.analyze_project_gaps(project_data: Dict) -> Dict
# Returns: {gaps, questions, missing_elements}

# Document Classification
classifier.classify(content: str) -> Dict
# Returns: {type: 'work'|'personal'|'spam', confidence}
```

---

## 13. QUICK REFERENCE

### Data Paths
- BEAT club data: `/Users/rishitjain/Downloads/2nd-brain/backend/club_data/`
- Search indexes: `/Users/rishitjain/Downloads/2nd-brain/backend/club_data/search_index.pkl`
- Enron data: `/Users/rishitjain/Downloads/2nd-brain/backend/data/`
- Output/reports: `/Users/rishitjain/Downloads/2nd-brain/backend/output/`

### Important Ports
- Frontend: 3000
- Backend: 5003
- Neo4j: 7687 (if running locally)

### API Base URL
- From frontend: `http://localhost:5003/api`
- From backend: `http://localhost:5003/api`

---

**End of Architecture Summary**
**Last Updated: December 3, 2025**
