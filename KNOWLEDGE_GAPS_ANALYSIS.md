# Knowledge Gaps System - Complete Analysis

## Overview
The Knowledge Gaps feature analyzes documents to identify missing information and prompts users to fill those gaps through text or voice answers.

---

## System Architecture

### 1. **Data Flow**

```
Documents (synced from Gmail/Slack/Box/GitHub)
         ↓
Document Extraction (structured summaries)
         ↓
Gap Analysis (5 different modes available)
         ↓
Knowledge Gaps created (with questions)
         ↓
User answers questions (text or voice)
         ↓
Answers auto-embedded to Pinecone (for RAG search)
         ↓
Complete Process (finalize into knowledge base)
```

### 2. **Backend Components**

**API Routes** (`backend/api/knowledge_routes.py`):
- `/api/knowledge/analyze` - Trigger gap analysis (POST)
- `/api/knowledge/gaps` - List gaps with filters (GET)
- `/api/knowledge/gaps/<id>` - Get single gap with answers (GET)
- `/api/knowledge/gaps/<id>/answers` - Submit text answer (POST)
- `/api/knowledge/gaps/<id>/voice-answer` - Submit voice answer (POST)
- `/api/knowledge/transcribe` - Transcribe audio (POST)
- `/api/knowledge/complete-process` - Finalize to RAG (POST)
- `/api/knowledge/rebuild-index` - Rebuild embeddings (POST)
- `/api/knowledge/gaps/<id>/feedback` - Rate gap usefulness (POST)

**Service Layer** (`backend/services/knowledge_service.py`):
- `KnowledgeService` - Main service class
- `analyze_gaps()` - Simple mode (single GPT pass)
- `analyze_gaps_multistage()` - 5-stage LLM reasoning
- `analyze_gaps_goalfirst()` - Backward reasoning from goals
- `analyze_gaps_intelligent()` - NLP-based detection
- `submit_answer()` - Save text/voice answers
- `transcribe_audio()` - Whisper transcription
- `transcribe_and_answer()` - Voice → text → answer

**Database Models** (`backend/database/models.py`):
```python
class KnowledgeGap:
    id: str
    tenant_id: str
    project_id: str (optional)
    title: str
    description: str
    category: GapCategory (enum: decision, technical, process, etc.)
    priority: int (1-5)
    status: GapStatus (enum: open, in_progress, answered, verified, closed)
    questions: JSON (list of question objects)
    context: JSON (metadata, evidence, related topics)
    feedback_useful: int
    feedback_not_useful: int
    feedback_comments: JSON

class GapAnswer:
    id: str
    knowledge_gap_id: str
    tenant_id: str
    user_id: str
    question_index: int
    question_text: str
    answer_text: str
    is_voice_transcription: bool
    audio_file_path: str (optional)
    transcription_confidence: float
    transcription_model: str ("whisper")
```

### 3. **Frontend Components**

**Main Component** (`frontend/components/knowledge-gaps/KnowledgeGaps.tsx`):
- Lists all knowledge gaps
- Filters by status/category
- Shows stats
- Manages gap selection

**Answer Panel** (`frontend/components/knowledge-gaps/GapAnswerPanel.tsx`):
- Displays gap details (description, evidence, context)
- Shows suggested source documents
- Text input for typing answers
- Voice recorder for speaking answers
- Submit button
- Feedback buttons (useful/not useful)

**Voice Recorder** (`frontend/components/knowledge-gaps/VoiceRecorder.tsx`):
- Uses browser MediaRecorder API
- Real-time audio level visualization
- Sends audio to `/api/knowledge/transcribe` endpoint
- Shows transcription preview
- Allows editing before using

---

## How Gap Analysis Works

### Gap Detection Sources

The system analyzes **work documents** to find gaps:

1. **Document Selection** (from `analyze_gaps()` method):
   ```python
   # Includes: CONFIRMED + CLASSIFIED + PENDING documents
   # Filters: classification == WORK or status == PENDING
   # Limits: 200 documents max (then token budgeting)
   ```

2. **Content Preparation**:
   - **Prefers structured summaries** (from extraction service)
   - **Falls back to raw content** (truncated to 4000 chars)
   - **Token budgeting**: Max 400,000 chars (~100K tokens)
   - **Prioritizes recent** documents if over budget

3. **Information Extracted**:
   From `_prepare_document_for_analysis()`:
   ```
   - Title, Type, Date, Sender
   - Summary (2-3 sentences)
   - Key Topics
   - Entities (people, systems, organizations)
   - Decisions made
   - Processes mentioned
   - Key dates/deadlines
   - Action items
   - Technical details
   ```

### Analysis Modes

**1. Simple Mode (default in code, but v3 is actual default)**:
- Single GPT-4 pass
- Prompt asks for: title, description, category, priority, questions
- Focus areas: decisions, technical details, processes, context, relationships, timelines, outcomes, rationale

**2. Multi-Stage Mode** (5 stages):
1. Corpus Understanding - Build mental model
2. Expert Mind Simulation - What would expert know?
3. New Hire Simulation - What would onboarder ask?
4. Failure Mode Analysis - What could go wrong?
5. Question Synthesis - Generate intelligent questions

**3. Goal-First Mode** (4 stages):
1. Goal Extraction - Define project goals
2. Decision Extraction - Find strategic/scope/timeline/financial decisions
3. Alternative Inference - What alternatives existed?
4. Question Generation - "Why X over Y?"

**4. Intelligent Mode** (6 layers of NLP):
1. Frame-Based Extraction (DECISION, PROCESS, DEFINITION frames)
2. Semantic Role Labeling (missing agents, causes)
3. Discourse Analysis (unsupported claims)
4. Knowledge Graph (missing entity relations, bus factor)
5. Cross-Document Verification (contradictions)
6. Grounded Question Generation

**5. V3 Mode (RECOMMENDED - default)**:
- 6-stage GPT-4 analysis
- Deep semantic understanding
- Enhanced prioritization
- Feedback loop for learning

### Gap Categories

```python
class GapCategory(str, Enum):
    DECISION = "decision"        # Why was X chosen?
    TECHNICAL = "technical"      # How does X work?
    PROCESS = "process"          # How do we do X?
    CONTEXT = "context"          # What's the background?
    RELATIONSHIP = "relationship" # Who works with whom?
    TIMELINE = "timeline"        # When did X happen?
    OUTCOME = "outcome"          # What was the result?
    RATIONALE = "rationale"      # Why did we do X?
```

---

## How Users Answer Questions

### Text Answering Flow

1. **User Interface**:
   - Gap panel shows question(s)
   - Textarea for typing answer
   - "Save Answer" button (enabled when text entered)

2. **Submit Flow** (from `GapAnswerPanel.tsx` → `/api/knowledge/gaps/<id>/answers`):
   ```
   User types answer
        ↓
   Frontend: POST /api/knowledge/gaps/<gap_id>/answers
   {
       "question_index": 0,
       "answer_text": "The answer is..."
   }
        ↓
   Backend: KnowledgeService.submit_answer()
        ↓
   Create GapAnswer record
        ↓
   Mark question as answered in gap.questions JSON
        ↓
   Auto-embed answer to Pinecone (immediate RAG availability)
        ↓
   Return success + embedding status
   ```

3. **Backend Processing** (`submit_answer()` method):
   ```python
   # 1. Validate gap exists
   # 2. Get question text from gap.questions[index]
   # 3. Create GapAnswer record
   # 4. Update gap.questions[index].answered = true
   # 5. If all questions answered, set gap.status = ANSWERED
   # 6. Auto-embed to Pinecone via embed_gap_answer()
   ```

4. **Auto-Embedding** (`embed_gap_answer()` function):
   ```python
   # Formats as: "Q: <question>\nA: <answer>"
   # Creates Pinecone document with ID "gap_answer_<id>"
   # Metadata: source_type=gap_answer, gap_id, question_index, user_id
   # Makes answer searchable by chatbot immediately
   ```

### Voice Answering Flow

1. **User Interface** (`VoiceRecorder.tsx`):
   - "Start Voice Answer" button
   - Records using browser MediaRecorder API
   - Shows real-time audio level bars
   - Timer shows recording duration
   - "Stop Recording" button

2. **Recording Flow**:
   ```
   User clicks "Start Voice Answer"
        ↓
   Browser requests microphone permission
        ↓
   MediaRecorder starts capturing
        ↓
   Audio level visualization (WebAudio API)
        ↓
   User speaks answer
        ↓
   User clicks "Stop Recording"
        ↓
   Audio saved as Blob (webm format)
        ↓
   Sent to /api/knowledge/transcribe
   ```

3. **Transcription Flow**:
   ```
   Frontend: POST /api/knowledge/transcribe
   FormData: { audio: Blob }
        ↓
   Backend: KnowledgeService.transcribe_audio()
        ↓
   Save to temp file
        ↓
   Call Azure Whisper API
   {
       model: "whisper",
       file: audio_file,
       response_format: "verbose_json",
       timestamp_granularities: ["segment"]
   }
        ↓
   Return TranscriptionResult
   {
       text: "transcribed text",
       confidence: 1.0,
       language: "en",
       duration_seconds: 12.5,
       segments: [...]
   }
        ↓
   Frontend: Show transcription preview
   ```

4. **Preview & Edit**:
   - Transcription shown in editable textarea
   - User can edit if Whisper made mistakes
   - "Use This Answer" button → fills main answer textarea
   - "Re-record" button → start over

5. **Alternative: Direct Voice Submit**:
   - `POST /api/knowledge/gaps/<id>/voice-answer`
   - Combines transcription + answer submission
   - Saves audio file to `tenant_data/<tenant>/audio/<uuid>.webm`
   - Creates GapAnswer with `is_voice_transcription=true`

---

## Bugs & Issues Found

### 🔴 CRITICAL BUGS

1. **Gap Analysis Runs in Background BUT No UI Feedback**
   - **Location**: `knowledge_routes.py` line 166
   - **Issue**: Analysis starts Celery task but frontend has no way to poll status
   - **Impact**: User clicks "Find Gaps" → nothing happens for 5-15 minutes
   - **Code**:
     ```python
     task = analyze_gaps_task.delay(...)
     return jsonify({"job_id": task.id})  # Frontend doesn't use this!
     ```
   - **Fix Needed**: Add polling endpoint + UI loading state

2. **Voice Answer Route Exists BUT Not Used**
   - **Location**: `knowledge_routes.py` line 533, `GapAnswerPanel.tsx` line 130
   - **Issue**: VoiceRecorder only transcribes, doesn't submit directly
   - **Impact**: Voice workflow is: record → transcribe → edit → paste → submit (inefficient)
   - **Better Flow**: Record → transcribe → submit in one step
   - **Fix**: Use `/voice-answer` endpoint directly from VoiceRecorder

3. **Missing Question Navigation**
   - **Location**: Frontend `GapAnswerPanel.tsx`
   - **Issue**: Gaps have multiple questions, but UI shows only description (not individual questions)
   - **Impact**: User doesn't know what specific questions to answer
   - **Code Problem**:
     ```tsx
     // Shows: gap.description (the title)
     // Missing: gap.questions[0].text, gap.questions[1].text, etc.
     ```
   - **Fix**: Add question list with individual answer fields

### 🟡 MAJOR ISSUES

4. **No Duplicate Gap Detection**
   - **Location**: All `analyze_gaps*()` methods
   - **Issue**: Running analysis multiple times creates duplicate gaps
   - **Impact**: 100 gaps → run again → 200 gaps (same questions)
   - **Missing**: Fingerprint-based deduplication (exists in intelligent mode only)
   - **Fix**: Check `fingerprint` field before creating gap

5. **Token Budget Silently Skips Documents**
   - **Location**: `_prepare_documents_for_analysis()` line 260
   - **Issue**: If 200 docs fetched but budget allows only 50, silently skips 150
   - **Impact**: Incomplete analysis, user doesn't know
   - **Code**:
     ```python
     if total_chars >= max_total_chars:
         stats["documents_skipped"] = len(documents) - stats["documents_included"]
         logger.warning(...)  # Only logs, doesn't tell user!
         break
     ```
   - **Fix**: Return skipped count in response

6. **Answer Editing Not Wired Up**
   - **Location**: Frontend has no edit UI
   - **Issue**: Backend has `PUT /api/knowledge/gaps/<id>/answers/<answer_id>` but no frontend button
   - **Impact**: Can't fix typos in submitted answers
   - **Fix**: Add "Edit" button to answered questions

7. **Complete Process Doesn't Show Progress**
   - **Location**: `/api/knowledge/complete-process` endpoint
   - **Issue**: Processes all answers + rebuilds index synchronously (could take minutes)
   - **Impact**: HTTP timeout on large datasets
   - **Fix**: Make async with status endpoint

### 🟢 MINOR ISSUES

8. **Whisper Confidence Always 1.0**
   - **Location**: `transcribe_audio()` line 1536
   - **Issue**: Hardcoded `confidence=1.0` because Whisper API doesn't return it
   - **Impact**: Can't warn users about low-quality transcriptions
   - **Note**: Not fixable (Azure Whisper limitation)

9. **Audio Files Not Cleaned Up**
   - **Location**: `transcribe_and_answer()` saves to disk
   - **Issue**: No cleanup job, audio files accumulate
   - **Impact**: Disk space grows unbounded
   - **Fix**: Add cleanup task or expiration

10. **No Answer Validation**
    - **Location**: `submit_answer()` method
    - **Issue**: Accepts empty strings if trimmed
    - **Impact**: Users can submit blank answers
    - **Code**: `if not answer_text:` check happens BEFORE trim
    - **Fix**: Validate `answer_text.strip()`

11. **Gap Feedback Not Shown to User**
    - **Location**: Feedback endpoint exists but no UI
    - **Issue**: Users can't see aggregate feedback (% useful)
    - **Impact**: No transparency on gap quality
    - **Fix**: Show feedback stats in gap card

### 🔵 EDGE CASES

12. **Multi-Tenant Audio File Collision**
    - **Location**: Audio saved to `tenant.data_directory/audio/`
    - **Issue**: UUID filename prevents collision, but directory not verified
    - **Impact**: If data_directory misconfigured, files leak across tenants
    - **Fix**: Add tenant_id verification

13. **Whisper Temp File Race Condition**
    - **Location**: `transcribe_audio()` temp file handling
    - **Issue**: If multiple requests hit simultaneously, temp files could conflict
    - **Impact**: Rare, but possible transcription corruption
    - **Fix**: Add unique suffix to temp files

14. **Answer Auto-Embed Can Fail Silently**
    - **Location**: `embed_gap_answer()` in routes
    - **Issue**: If Pinecone fails, answer still saved but not searchable
    - **Impact**: Answer lost to RAG system
    - **Code**:
     ```python
     embed_result = embed_gap_answer(...)
     # Returns success=false but doesn't fail request
     ```
    - **Fix**: Retry or queue for later

---

## Missing Features

### High Priority

1. **No Status Polling for Background Analysis**
   - Need: `GET /api/knowledge/analyze/status/<job_id>`
   - Returns: progress %, current stage, time remaining

2. **No Bulk Answer Operations**
   - Need: Submit multiple answers at once
   - Use case: User fills out 5 questions, submits all together

3. **No Search/Filter in Gap List**
   - Need: Search by keyword, filter by answered/unanswered
   - Current: Only filter by status/category (basic)

4. **No Gap Priority Sorting**
   - Need: Sort by priority (5 → 1)
   - Current: No sorting in frontend

### Medium Priority

5. **No Voice Playback**
   - Saved audio files exist but no playback button
   - Can't review what was said

6. **No Export Functionality**
   - Can't export gaps + answers to PDF/CSV
   - Useful for knowledge transfer documentation

7. **No Answer History/Versions**
   - If user edits answer, old version lost
   - No audit trail

### Low Priority

8. **No Collaborative Answering**
   - One user per question
   - Can't have multiple people contribute

9. **No Answer Citations**
   - Can't link answer to source documents
   - Useful for verification

10. **No Answer Confidence Scoring**
    - User can't indicate uncertainty
    - All answers treated as equally certain

---

## Recommended Improvements

### Immediate Fixes (Do Now)

1. **Fix Question Display**
   ```tsx
   // In GapAnswerPanel.tsx, replace:
   <h3>{gap.description}</h3>

   // With:
   {gap.questions.map((q, idx) => (
     <div key={idx}>
       <h4>Question {idx + 1}</h4>
       <p>{q.text}</p>
       {/* Answer input here */}
     </div>
   ))}
   ```

2. **Add Analysis Status Polling**
   ```python
   @knowledge_bp.route('/analyze/status/<job_id>', methods=['GET'])
   def get_analysis_status(job_id: str):
       task = AsyncResult(job_id)
       return jsonify({
           "status": task.state,
           "progress": task.info.get('progress', 0) if task.info else 0
       })
   ```

3. **Add Answer Trimming**
   ```python
   # In submit_answer():
   answer_text = answer_text.strip()
   if not answer_text:
       return None, "Answer cannot be empty"
   ```

4. **Use Voice Answer Endpoint Directly**
   ```tsx
   // In VoiceRecorder.tsx:
   const submitVoiceAnswer = async (audioBlob: Blob) => {
       const formData = new FormData()
       formData.append('audio', audioBlob)
       formData.append('question_index', questionIndex)

       await axios.post(
           `/api/knowledge/gaps/${gapId}/voice-answer`,
           formData,
           { headers: authHeaders }
       )
   }
   ```

### Short-Term (Next Sprint)

5. **Add Gap Deduplication**
   ```python
   # Before creating gap:
   fingerprint = hashlib.md5(
       f"{category}:{title}:{evidence}".encode()
   ).hexdigest()

   existing = db.query(KnowledgeGap).filter(
       KnowledgeGap.fingerprint == fingerprint
   ).first()

   if existing:
       # Merge or skip
   ```

6. **Add Progress Indicators**
   - Show "Analyzing... Stage 2 of 5" in UI
   - WebSocket or Server-Sent Events for real-time updates

7. **Add Answer Editing UI**
   ```tsx
   <button onClick={() => setEditMode(true)}>Edit Answer</button>
   ```

### Long-Term (Future)

8. **Add ML-Based Gap Ranking**
   - Learn from feedback (useful/not useful)
   - Prioritize gaps similar to highly-rated ones

9. **Add Answer Suggestions**
   - Use RAG to suggest answer based on existing docs
   - "We found similar info in these documents..."

10. **Add Collaborative Features**
    - Multiple users can contribute to same gap
    - Voting on best answer
    - Comments/discussions

---

## Security Considerations

### ✅ Good Security Practices

1. **Multi-Tenant Isolation**:
   ```python
   # All queries filter by tenant_id
   gap = db.query(KnowledgeGap).filter(
       KnowledgeGap.id == gap_id,
       KnowledgeGap.tenant_id == tenant_id  # ✓ Isolated
   ).first()
   ```

2. **JWT Authentication**: All endpoints use `@require_auth` decorator

3. **Input Validation**: Gap ID, question index validated before use

### ⚠️ Potential Issues

1. **Audio File Storage**:
   - Files saved to tenant directory but no encryption
   - Consider encrypting sensitive voice data

2. **Transcription Privacy**:
   - Audio sent to Azure Whisper (3rd party)
   - Ensure compliance with privacy policies

3. **Answer Visibility**:
   - All tenant users can see all answers
   - No per-user answer privacy

---

## Performance Considerations

### Current Performance

- **Gap Analysis**: 5-15 minutes for 100 documents (depends on mode)
- **Transcription**: 2-5 seconds per minute of audio
- **Answer Submission**: <1 second
- **Auto-Embedding**: 1-2 seconds per answer

### Bottlenecks

1. **Synchronous GPT Calls**: Each stage waits for previous
2. **No Caching**: Re-analyzes same documents if run multiple times
3. **Large Document Sets**: 200 docs × 3000 chars = 600KB of context

### Optimization Opportunities

1. **Cache Analysis Results**: Store per-document insights, reuse across runs
2. **Parallel Stage Execution**: Some stages could run in parallel
3. **Incremental Analysis**: Only analyze new documents since last run
4. **Background Embedding**: Queue instead of sync (already tries Celery, but fallback is sync)

---

## Testing Recommendations

### Unit Tests Needed

1. `test_submit_answer_validation()` - Test empty/invalid answers
2. `test_transcribe_audio_formats()` - Test webm, wav, mp3
3. `test_gap_deduplication()` - Test fingerprint matching
4. `test_multi_tenant_isolation()` - Test tenant_id filtering

### Integration Tests Needed

1. `test_voice_answer_flow()` - Record → transcribe → submit
2. `test_gap_analysis_modes()` - All 5 modes produce valid gaps
3. `test_complete_process()` - Answers embedded to Pinecone correctly

### E2E Tests Needed

1. Full workflow: Sync docs → Analyze → Answer → Search (RAG should find answer)
2. Voice workflow: Record → Transcribe → Edit → Submit → Verify in DB
3. Multi-user workflow: User A creates gap, User B answers

---

## Summary of Current State

### ✅ What Works Well

1. **Multiple Analysis Modes**: Flexibility in gap detection approach
2. **Voice + Text Support**: Users can choose input method
3. **Auto-Embedding**: Answers immediately searchable via RAG
4. **Real-Time Audio Viz**: Nice UX for voice recording
5. **Feedback System**: Learning from user ratings
6. **Multi-Tenant Safe**: Proper isolation

### ❌ What Needs Fixing

1. **Question Display**: Users don't see individual questions
2. **Background Jobs**: No status polling, looks like hang
3. **Voice Workflow**: Inefficient (should use direct endpoint)
4. **Duplicate Gaps**: No prevention
5. **Answer Editing**: Backend ready, no frontend
6. **Error Handling**: Silent failures on embedding

### 🎯 Priority Fixes (In Order)

1. Fix question display (30 min fix, huge UX improvement)
2. Add status polling for analysis (2 hours)
3. Use voice-answer endpoint directly (1 hour)
4. Add answer trimming validation (15 min)
5. Add gap deduplication (2 hours)
6. Add answer editing UI (1 hour)

---

## Code Quality Notes

- **Backend**: Well-structured, good separation of concerns
- **Frontend**: Clean React components, could use more TypeScript types
- **Database**: Proper indexes, good schema design
- **API**: RESTful, consistent error handling
- **Documentation**: Good docstrings, but missing API docs

---

*Analysis Complete - 2026-02-01*
