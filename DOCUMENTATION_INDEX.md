# 2nd Brain - Documentation Index

**Comprehensive Codebase Exploration & Documentation**
**Generated: December 3, 2025**

---

## Quick Navigation

### Start Here
1. **[EXPLORATION_SUMMARY.md](./backend/EXPLORATION_SUMMARY.md)** (16 KB)
   - Executive overview of the entire system
   - Best for: Understanding the big picture in 30 minutes
   - Contains: System capabilities, data flow, tech stack

2. **[QUICK_START_GUIDE.md](./backend/QUICK_START_GUIDE.md)** (11 KB)
   - Development guide with examples and troubleshooting
   - Best for: Getting started quickly, common tasks
   - Contains: Startup instructions, API cheat sheet, debugging tips

### Deep Dives
3. **[CODEBASE_ARCHITECTURE.md](./backend/CODEBASE_ARCHITECTURE.md)** (29 KB)
   - Complete architecture documentation
   - Best for: Understanding implementation details
   - Contains: All 13 sections below

---

## What's Inside the Main Documentation

### CODEBASE_ARCHITECTURE.md Sections

#### 1. Frontend Structure (Next.js 14)
- 8 main pages with routing
- 9 React components (3,707 lines total)
- API communication pattern (Axios to http://localhost:5003/api)

#### 2. Backend Structure (Flask + Python)
- Main app: app_universal.py (2,454 lines)
- 43 API endpoints documented
- Directory structure with key components

#### 3. Data Organization & Storage
- BEAT Club data (primary): /club_data/classified/
- Enron dataset (secondary): /data/
- Search index (1.4GB pickle file)
- Data structures (JSON formats documented)

#### 4. RAG Implementation (Enhanced RAG v2.1)
- 7-stage retrieval pipeline
- 6 query types with different retrieval strategies
- 8 RAG components (classifier, reranker, hallucination detector, etc.)
- Configuration parameters

#### 5. Knowledge Gaps Identification & Storage
- Gap analysis process (5 steps)
- 8 gap types (project_goal, success_criteria, etc.)
- Frontend collection (KnowledgeGaps.tsx)
- Gap storage format (JSON)

#### 6. Backend API Endpoints (43 Total)
- Core RAG & Search (4 endpoints)
- Knowledge Gaps (5 endpoints)
- Projects & Documents (10 endpoints)
- Connectors & Integrations (7 endpoints)
- Message Filtering (3 endpoints)
- Stakeholder Graph (4 endpoints)
- Analytics & Feedback (4 endpoints)
- Content Generation (2 endpoints)
- Utilities (1 endpoint)

#### 7. Data Flow Diagrams
- User query flow (query → answer)
- Document ingestion flow (upload → classification → RAG)
- Gap identification flow (project → gaps → collection)

#### 8. Key Technologies & Dependencies
- Frontend: Next.js, Tailwind, Axios, TypeScript
- Backend: Flask, Azure OpenAI, Sentence-Transformers, BERTopic
- Data: Pickle files, JSON, Neo4j, ChromaDB
- Content: python-pptx, MoviePy, gTTS, Pillow

#### 9. System Status & Capabilities
- Fully implemented features (13 items)
- Partially implemented (4 items)
- In development (4 items)
- Known limitations

#### 10. Configuration & Environment
- Environment variables (.env)
- Configuration parameters (config.py)
- Model settings, clustering, classification, RAG

#### 11. Startup Instructions
- Frontend: npm run dev (port 3000)
- Backend: python app_universal.py (port 5003)
- Data loading process

#### 12. Notable Code Files
- Must-read files (6 critical files)
- Key function signatures

#### 13. Quick Reference
- Data paths
- Important ports
- API base URLs
- File locations

---

## Documentation Files Created

### By This Exploration (December 3, 2025)

```
/backend/
├── CODEBASE_ARCHITECTURE.md          (892 lines, 29 KB)
│   └── Complete architecture documentation
│
├── QUICK_START_GUIDE.md              (400+ lines, 11 KB)
│   └── Development guide with examples
│
└── EXPLORATION_SUMMARY.md            (15 sections, 16 KB)
    └── Executive summary of the entire system
```

### Existing Documentation in Project

```
/backend/
├── README.md                          (Comprehensive project overview)
├── ARCHITECTURE.md                    (Original architecture notes)
├── QUICKSTART.md                      (Original quick start)
├── IMPLEMENTATION_SUMMARY.md          (Implementation details)
├── INTEGRATION_COMPLETE.md            (Integration notes)
├── PROJECT_DETECTION_ARCHITECTURE.md  (Project detection system)
└── [Many others...]

/frontend/
├── README.md                          (Frontend overview)
└── [Component files]
```

---

## How to Use This Documentation

### Scenario 1: "I'm new to the project"
1. Read: EXPLORATION_SUMMARY.md (30 min)
2. Read: QUICK_START_GUIDE.md (15 min)
3. Run: `npm run dev` + `python app_universal.py`
4. Explore: http://localhost:3000

### Scenario 2: "I need to understand the RAG system"
1. Read: CODEBASE_ARCHITECTURE.md section 4
2. Read: `/backend/rag/enhanced_rag_v2.py` (code)
3. Check: Query classification types table in docs

### Scenario 3: "I need to add a new API endpoint"
1. Read: QUICK_START_GUIDE.md → "Common Development Tasks"
2. Read: CODEBASE_ARCHITECTURE.md section 5
3. Follow: Pattern in app_universal.py
4. Test: Using curl/Postman examples

### Scenario 4: "I want to understand the data flow"
1. Read: CODEBASE_ARCHITECTURE.md section 7
2. Read: EXPLORATION_SUMMARY.md section 9
3. Trace: Through app_universal.py routes

### Scenario 5: "I need to fix a bug"
1. Read: QUICK_START_GUIDE.md → "Troubleshooting"
2. Read: CODEBASE_ARCHITECTURE.md → relevant section
3. Check: Config parameters
4. Add: Debug logging using examples

---

## Key Findings Summary

### Architecture Highlights
- **Clean Separation**: Frontend (Next.js) + Backend (Flask) with clear API boundaries
- **Advanced RAG**: 7-stage retrieval pipeline with 6 query types and hallucination detection
- **Knowledge Extraction**: Gap identification system with 8 categorized question types
- **Data Management**: BEAT club data (primary) + Enron dataset (secondary)
- **Modern Stack**: Cutting-edge ML (Azure OpenAI, BERTopic, Cross-encoders)

### System Strengths
- Well-organized codebase with clear separation of concerns
- Comprehensive RAG implementation with multiple optimization techniques
- Flexible document classification workflow
- Voice input support (Whisper integration)
- Good error handling and feedback mechanisms

### Areas for Enhancement
- Search index size (1.4GB) impacts startup time
- Gap questions could be more personalized
- Neo4j integration not fully connected
- Video generation infrastructure ready but not deployed
- Slack/GitHub integrations partially implemented

---

## File Locations Quick Reference

### Frontend Source
```
/Users/rishitjain/Downloads/2nd-brain/frontend/
├── app/                    # Pages (home, documents, projects, etc.)
├── components/             # React components
├── public/                 # Static assets
└── package.json            # Dependencies
```

### Backend Source
```
/Users/rishitjain/Downloads/2nd-brain/backend/
├── app_universal.py        # Main Flask application
├── rag/                    # RAG implementations
├── gap_analysis/           # Gap detection
├── config/                 # Configuration
├── club_data/              # BEAT data storage
└── requirements.txt        # Dependencies
```

### This Documentation
```
/Users/rishitjain/Downloads/2nd-brain/backend/
├── CODEBASE_ARCHITECTURE.md
├── QUICK_START_GUIDE.md
└── EXPLORATION_SUMMARY.md
```

---

## API Quick Reference

### Most Used Endpoints

```bash
# Search with RAG
POST /api/search
Body: {query: "What is BEAT?"}
Response: {answer, sources, confidence}

# Get knowledge gaps
GET /api/questions
Response: [gap objects]

# Submit gap answer
POST /api/questions/answer
Body: {gap_id, answer, project}

# List all projects
GET /api/projects
Response: [project objects]

# Get project details
GET /api/projects/{project_id}
Response: {name, documents, stats}

# Check system status
GET /api/stats
Response: {total_documents, total_projects, etc}
```

---

## Configuration Reference

### Essential Config (config.py)
- `TOP_K_RETRIEVAL = 10` - Initial retrieval count
- `RERANK_TOP_K = 5` - Top documents after re-ranking
- `MAX_CONTEXT_LENGTH = 8000` - LLM context window
- `WORK_CONFIDENCE_THRESHOLD = 0.85` - Classification confidence

### Environment Variables (.env)
```
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=<your-key>
LLAMAPARSE_API_KEY=<your-key>
```

---

## Development Workflow

### 1. Local Setup
```bash
# Backend
cd backend && pip install -r requirements.txt
python app_universal.py

# Frontend (in new terminal)
cd frontend && npm install
npm run dev
```

### 2. Common Tasks
- **Add API endpoint**: Edit `app_universal.py`, follow existing pattern
- **Modify RAG**: Edit `rag/enhanced_rag_v2.py`
- **Change config**: Edit `config/config.py`
- **Update UI**: Edit components in `/components/`

### 3. Testing
- **Unit**: Test individual functions with sample data
- **Integration**: Test API flows with curl/Postman
- **E2E**: Test full user workflows in UI

---

## Support & Maintenance

### If You Get Stuck
1. Check **QUICK_START_GUIDE.md** → Troubleshooting section
2. Search **CODEBASE_ARCHITECTURE.md** for your component
3. Check the specific source file for implementation details
4. Review EXPLORATION_SUMMARY.md for overview context

### To Extend the System
1. Review **Common Development Tasks** in QUICK_START_GUIDE
2. Follow patterns from existing code
3. Refer to **API Endpoints** section for patterns
4. Test thoroughly before deploying

---

## Documentation Statistics

- **Total lines of new documentation**: 1,300+
- **Coverage**: Frontend, Backend, RAG, Data, API, Configuration
- **Code examples**: 50+
- **Diagrams/flowcharts**: 10+
- **Time to read all**: 2-3 hours (detailed)
- **Time to skim**: 30 minutes (quick overview)

---

## Version & Metadata

- **Documentation Generated**: December 3, 2025
- **Codebase Version**: Latest from `/Users/rishitjain/Downloads/2nd-brain/`
- **Technologies Documented**:
  - Frontend: Next.js 14.0.0, React 18.2.0, Tailwind CSS 3.3.5
  - Backend: Flask, Azure OpenAI, BERTopic, SQLAlchemy (conceptual)
- **Total Project Code**: 6,000+ lines (excluding node_modules)

---

## Next Steps

1. **Start with EXPLORATION_SUMMARY.md** (quick overview)
2. **Follow QUICK_START_GUIDE.md** (get running)
3. **Dive into CODEBASE_ARCHITECTURE.md** (understand details)
4. **Explore source code** with documentation as reference
5. **Make changes** following patterns in the docs

---

## Contact & Feedback

This documentation was created to help you understand and work with the 2nd Brain codebase. If you find outdated information or have suggestions for improvement, please update the relevant section.

Key people who should maintain this:
- **Frontend changes**: Update `/frontend/README.md` and CODEBASE_ARCHITECTURE.md section 1
- **Backend changes**: Update `/backend/README.md` and CODEBASE_ARCHITECTURE.md section 2
- **API changes**: Update CODEBASE_ARCHITECTURE.md section 5
- **Config changes**: Update QUICK_START_GUIDE.md and section 10

---

**Last Updated**: December 3, 2025
**Maintained At**: `/Users/rishitjain/Downloads/2nd-brain/`
**Documentation By**: Code exploration & analysis
