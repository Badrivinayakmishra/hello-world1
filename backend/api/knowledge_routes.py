"""
Knowledge Gap API Routes
REST endpoints for knowledge gaps, answers, and voice transcription.
"""

import io
from flask import Blueprint, request, jsonify, g

from database.models import (
    SessionLocal, KnowledgeGap, GapAnswer,
    GapStatus, GapCategory,
    utc_now
)
from services.auth_service import require_auth
from services.knowledge_service import KnowledgeService
from services.embedding_service import get_embedding_service


# Create blueprint
knowledge_bp = Blueprint('knowledge', __name__, url_prefix='/api/knowledge')


def get_db():
    """Get database session"""
    return SessionLocal()


def embed_gap_answer(answer: GapAnswer, tenant_id: str, db):
    """
    Immediately embed a gap answer to Pinecone for RAG access.

    This makes the answer searchable by the chatbot immediately after submission,
    without waiting for the "Complete Process" batch operation.

    Args:
        answer: The GapAnswer object to embed
        tenant_id: Tenant ID for namespace isolation
        db: Database session

    Returns:
        Dict with embedding result
    """
    try:
        embedding_service = get_embedding_service()
        vector_store = embedding_service.vector_store

        # Format answer as document for embedding
        # Use a special ID prefix to distinguish from regular documents
        doc_id = f"gap_answer_{answer.id}"
        content = f"Q: {answer.question_text}\nA: {answer.answer_text}"

        # Prepare document for embedding
        pinecone_docs = [{
            'id': doc_id,
            'content': content,
            'title': f"Knowledge Gap Answer: {answer.question_text[:100]}",
            'metadata': {
                'source_type': 'gap_answer',
                'knowledge_gap_id': answer.knowledge_gap_id,
                'question_index': answer.question_index,
                'user_id': answer.user_id,
                'is_voice': answer.is_voice_transcription,
                'created_at': answer.created_at.isoformat() if answer.created_at else ''
            }
        }]

        # Embed to Pinecone (answers are typically short, so single chunk)
        result = vector_store.embed_and_upsert_documents(
            documents=pinecone_docs,
            tenant_id=tenant_id,
            chunk_size=2000,  # Large enough for most answers
            chunk_overlap=0,  # No overlap for single-chunk answers
            show_progress=False
        )

        print(f"[auto-embed] Gap answer {answer.id} embedded to Pinecone: {result.get('upserted', 0)} chunks")

        return {
            'success': result.get('success', False),
            'chunks': result.get('upserted', 0),
            'doc_id': doc_id
        }

    except Exception as e:
        print(f"[auto-embed] Error embedding gap answer: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# GAP ANALYSIS
# ============================================================================

@knowledge_bp.route('/analyze', methods=['POST'])
@require_auth
def analyze_gaps():
    """
    Trigger knowledge gap analysis on documents.

    Request body (optional):
    {
        "project_id": "...",  // Analyze specific project
        "force": false,  // Force re-analysis
        "include_pending": true,  // Include pending/classified docs (default true)
        "mode": "v3" | "intelligent" | "goalfirst" | "multistage" | "simple",  // Analysis mode
        "max_documents": 100  // Max docs to analyze (for cost control)
    }

    Modes:
    - "v3" (DEFAULT - RECOMMENDED): Enhanced 6-stage GPT-4 analysis
      Stage 1: Deep Document Extraction (GPT-4 semantic understanding)
      Stage 2: Knowledge Graph Assembly (entity resolution)
      Stage 3: Multi-Analyzer Gap Detection (8 specialized analyzers)
      Stage 4: LLM Question Generation (contextual questions)
      Stage 5: Intelligent Prioritization (multi-factor scoring)
      Stage 6: Feedback & Learning Loop

    - "intelligent": 6-layer advanced NLP analysis
      Layer 1: Frame-Based Extraction (DECISION, PROCESS, DEFINITION frames)
      Layer 2: Semantic Role Labeling (missing agents, causes, manners)
      Layer 3: Discourse Analysis (claims without evidence)
      Layer 4: Knowledge Graph (missing entity relations, bus factor)
      Layer 5: Cross-Document Verification (contradictions)
      Layer 6: Grounded Question Generation

    - "goalfirst": 4-stage Goal-First Backward Reasoning
      Stage 1: Goal Extraction - Define project goal
      Stage 2: Decision Extraction - Find strategic, scope, timeline, financial decisions
      Stage 3: Alternative Inference - Infer what alternatives existed
      Stage 4: Question Generation - "Why X over Y?" questions for new employees

    - "multistage": 5-stage LLM reasoning for tacit knowledge
      Stage 1: Corpus Understanding
      Stage 2: Expert Mind Simulation
      Stage 3: New Hire Simulation
      Stage 4: Failure Mode Analysis
      Stage 5: Question Synthesis

    - "simple": Basic single-pass analysis (faster, less intelligent)

    Response:
    {
        "success": true,
        "results": {
            "gaps": [...],
            "total_documents_analyzed": 50,
            "categories_found": {"technical": 5, "process": 3},
            "mode": "intelligent"
        }
    }
    """
    try:
        data = request.get_json() or {}
        project_id = data.get('project_id')
        force = data.get('force', False)
        include_pending = data.get('include_pending', True)
        mode = data.get('mode', 'v3')  # Default to v3 mode (enhanced)
        max_documents = min(data.get('max_documents', 100), 500)  # Cap at 500

        # Use Celery for background processing (gap analysis can take 5-15 minutes)
        from tasks.gap_analysis_tasks import analyze_gaps_task

        # Start background task
        task = analyze_gaps_task.delay(
            tenant_id=g.tenant_id,
            project_id=project_id,
            mode=mode,
            force=force
        )

        return jsonify({
            "success": True,
            "message": f"Gap analysis started in background (mode: {mode})",
            "job_id": task.id  # Task ID for status polling
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# LIST GAPS
# ============================================================================

@knowledge_bp.route('/gaps', methods=['GET'])
@require_auth
def list_gaps():
    """
    List knowledge gaps with filtering.

    Query params:
        project_id: filter by project
        status: open, in_progress, answered, verified, closed
        category: decision, technical, process, context, etc.
        limit: page size (default 50)
        offset: page offset

    Response:
    {
        "success": true,
        "gaps": [...],
        "pagination": {...}
    }
    """
    try:
        project_id = request.args.get('project_id')
        status_str = request.args.get('status')
        category_str = request.args.get('category')
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))

        # Parse status
        status = None
        if status_str:
            status_map = {
                'open': GapStatus.OPEN,
                'in_progress': GapStatus.IN_PROGRESS,
                'answered': GapStatus.ANSWERED,
                'verified': GapStatus.VERIFIED,
                'closed': GapStatus.CLOSED
            }
            status = status_map.get(status_str.lower())

        # Parse category
        category = None
        if category_str:
            category_map = {
                'decision': GapCategory.DECISION,
                'technical': GapCategory.TECHNICAL,
                'process': GapCategory.PROCESS,
                'context': GapCategory.CONTEXT,
                'relationship': GapCategory.RELATIONSHIP,
                'timeline': GapCategory.TIMELINE,
                'outcome': GapCategory.OUTCOME,
                'rationale': GapCategory.RATIONALE
            }
            category = category_map.get(category_str.lower())

        db = get_db()
        try:
            service = KnowledgeService(db)
            gaps, total = service.get_gaps(
                tenant_id=g.tenant_id,
                project_id=project_id,
                status=status,
                category=category,
                limit=limit,
                offset=offset
            )

            return jsonify({
                "success": True,
                "gaps": [gap.to_dict(include_answers=False) for gap in gaps],
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GET SINGLE GAP
# ============================================================================

@knowledge_bp.route('/gaps/<gap_id>', methods=['GET'])
@require_auth
def get_gap(gap_id: str):
    """
    Get a single knowledge gap with answers.

    Response:
    {
        "success": true,
        "gap": { ... },
        "answers": [...]
    }
    """
    try:
        db = get_db()
        try:
            gap = db.query(KnowledgeGap).filter(
                KnowledgeGap.id == gap_id,
                KnowledgeGap.tenant_id == g.tenant_id
            ).first()

            if not gap:
                return jsonify({
                    "success": False,
                    "error": "Knowledge gap not found"
                }), 404

            service = KnowledgeService(db)
            answers = service.get_answers(gap_id, g.tenant_id)

            return jsonify({
                "success": True,
                "gap": gap.to_dict(include_answers=True),
                "answers": [a.to_dict() for a in answers]
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# SUBMIT ANSWER
# ============================================================================

@knowledge_bp.route('/gaps/<gap_id>/answers', methods=['POST'])
@require_auth
def submit_answer(gap_id: str):
    """
    Submit an answer to a knowledge gap question.

    Request body:
    {
        "question_index": 0,
        "answer_text": "The answer is..."
    }

    Response:
    {
        "success": true,
        "answer": { ... }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400

        question_index = data.get('question_index')
        answer_text = data.get('answer_text', '').strip()

        if question_index is None:
            return jsonify({
                "success": False,
                "error": "question_index required"
            }), 400

        if not answer_text:
            return jsonify({
                "success": False,
                "error": "answer_text required"
            }), 400

        db = get_db()
        try:
            service = KnowledgeService(db)
            answer, error = service.submit_answer(
                gap_id=gap_id,
                question_index=question_index,
                answer_text=answer_text,
                user_id=g.user_id,
                tenant_id=g.tenant_id
            )

            if error:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            # Auto-embed the answer to Pinecone immediately
            # This makes it searchable by the chatbot right away
            embed_result = embed_gap_answer(answer, g.tenant_id, db)

            return jsonify({
                "success": True,
                "answer": answer.to_dict(),
                "embedded": embed_result.get('success', False),
                "embedding_chunks": embed_result.get('chunks', 0)
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@knowledge_bp.route('/gaps/<gap_id>/answers/<answer_id>', methods=['PUT'])
@require_auth
def update_answer(gap_id: str, answer_id: str):
    """
    Update an existing answer.

    Request body:
    {
        "answer_text": "Updated answer..."
    }
    """
    try:
        data = request.get_json()

        if not data or not data.get('answer_text'):
            return jsonify({
                "success": False,
                "error": "answer_text required"
            }), 400

        db = get_db()
        try:
            service = KnowledgeService(db)
            success, error = service.update_answer(
                answer_id=answer_id,
                answer_text=data['answer_text'],
                user_id=g.user_id,
                tenant_id=g.tenant_id
            )

            if not success:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            return jsonify({"success": True})

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# VOICE TRANSCRIPTION
# ============================================================================

@knowledge_bp.route('/transcribe', methods=['POST'])
@require_auth
def transcribe_audio():
    """
    Transcribe audio file using Whisper.

    Request:
        multipart/form-data with 'audio' file

    Response:
    {
        "success": true,
        "transcription": {
            "text": "...",
            "confidence": 0.95,
            "language": "en",
            "duration_seconds": 12.5
        }
    }
    """
    try:
        if 'audio' not in request.files:
            return jsonify({
                "success": False,
                "error": "No audio file provided"
            }), 400

        audio_file = request.files['audio']
        audio_data = audio_file.read()
        filename = audio_file.filename or "audio.wav"

        language = request.form.get('language')

        db = get_db()
        try:
            service = KnowledgeService(db)
            result = service.transcribe_audio(
                audio_data=audio_data,
                filename=filename,
                language=language
            )

            if not result.text:
                return jsonify({
                    "success": False,
                    "error": "Transcription failed",
                    "details": result.segments
                }), 500

            return jsonify({
                "success": True,
                "transcription": {
                    "text": result.text,
                    "confidence": result.confidence,
                    "language": result.language,
                    "duration_seconds": result.duration_seconds,
                    "segments": result.segments
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@knowledge_bp.route('/gaps/<gap_id>/voice-answer', methods=['POST'])
@require_auth
def submit_voice_answer(gap_id: str):
    """
    Submit voice answer - transcribe and save.

    Request:
        multipart/form-data with:
        - 'audio': audio file
        - 'question_index': question index

    Response:
    {
        "success": true,
        "answer": { ... },
        "transcription": { ... }
    }
    """
    try:
        if 'audio' not in request.files:
            return jsonify({
                "success": False,
                "error": "No audio file provided"
            }), 400

        question_index = request.form.get('question_index')
        if question_index is None:
            return jsonify({
                "success": False,
                "error": "question_index required"
            }), 400

        question_index = int(question_index)

        audio_file = request.files['audio']
        audio_data = audio_file.read()
        filename = audio_file.filename or "audio.wav"

        db = get_db()
        try:
            service = KnowledgeService(db)
            answer, error = service.transcribe_and_answer(
                gap_id=gap_id,
                question_index=question_index,
                audio_data=audio_data,
                filename=filename,
                user_id=g.user_id,
                tenant_id=g.tenant_id,
                save_audio=True
            )

            if error:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            # Auto-embed the voice answer to Pinecone immediately
            embed_result = embed_gap_answer(answer, g.tenant_id, db)

            return jsonify({
                "success": True,
                "answer": answer.to_dict(),
                "embedded": embed_result.get('success', False),
                "embedding_chunks": embed_result.get('chunks', 0)
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# INDEX MANAGEMENT
# ============================================================================

# ============================================================================
# COMPLETE PROCESS - Finalize knowledge gaps into RAG
# ============================================================================

@knowledge_bp.route('/complete-process', methods=['POST'])
@require_auth
def complete_process():
    """
    Complete the knowledge transfer process.

    Integrates all answered knowledge gap questions into the RAG embedding index,
    making them available for chat queries. Can be called even if not all questions
    are answered - it will integrate whatever answers exist.

    Request body (optional):
    {
        "mark_completed": true  // Whether to mark gaps with answers as completed
    }

    Response:
    {
        "success": true,
        "results": {
            "answers_integrated": 15,
            "documents_indexed": 50,
            "chunks_created": 250,
            "gaps_completed": 5,
            "message": "Successfully integrated 15 answers into RAG knowledge base"
        }
    }
    """
    try:
        data = request.get_json() or {}
        mark_completed = data.get('mark_completed', True)

        db = get_db()
        try:
            service = KnowledgeService(db)
            result = service.complete_knowledge_process(
                tenant_id=g.tenant_id,
                mark_completed=mark_completed
            )

            if not result.get("success"):
                return jsonify({
                    "success": False,
                    "error": result.get("error", "Unknown error")
                }), 500

            return jsonify({
                "success": True,
                "results": {
                    "answers_integrated": result.get("answers_integrated", 0),
                    "documents_indexed": result.get("documents_indexed", 0),
                    "chunks_created": result.get("chunks_created", 0),
                    "gaps_completed": result.get("gaps_completed", 0),
                    "message": result.get("message", "Process completed")
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# INDEX MANAGEMENT
# ============================================================================

@knowledge_bp.route('/rebuild-index', methods=['POST'])
@require_auth
def rebuild_index():
    """
    Rebuild the embedding index for the tenant.

    Request body (optional):
    {
        "force": false
    }

    Response:
    {
        "success": true,
        "results": {
            "documents_processed": 100,
            "answers_included": 25,
            "chunks_created": 500
        }
    }
    """
    try:
        data = request.get_json() or {}
        force = data.get('force', False)

        db = get_db()
        try:
            service = KnowledgeService(db)
            results = service.rebuild_embedding_index(
                tenant_id=g.tenant_id,
                force=force
            )

            if results.get("error"):
                return jsonify({
                    "success": False,
                    "error": results["error"]
                }), 500

            return jsonify({
                "success": True,
                "results": results
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# STATISTICS
# ============================================================================

@knowledge_bp.route('/stats', methods=['GET'])
@require_auth
def get_stats():
    """
    Get knowledge gap statistics.

    Response:
    {
        "success": true,
        "stats": {
            "by_status": {...},
            "by_category": {...},
            "total_gaps": 50,
            "total_answers": 120,
            "voice_answers": 30
        }
    }
    """
    try:
        db = get_db()
        try:
            service = KnowledgeService(db)
            stats = service.get_gap_stats(g.tenant_id)

            return jsonify({
                "success": True,
                "stats": stats
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# UPDATE GAP STATUS
# ============================================================================

@knowledge_bp.route('/gaps/<gap_id>/status', methods=['PUT'])
@require_auth
def update_gap_status(gap_id: str):
    """
    Update knowledge gap status.

    Request body:
    {
        "status": "answered" | "verified" | "closed"
    }
    """
    try:
        data = request.get_json()

        if not data or not data.get('status'):
            return jsonify({
                "success": False,
                "error": "status required"
            }), 400

        status_map = {
            'open': GapStatus.OPEN,
            'in_progress': GapStatus.IN_PROGRESS,
            'answered': GapStatus.ANSWERED,
            'verified': GapStatus.VERIFIED,
            'closed': GapStatus.CLOSED
        }

        new_status = status_map.get(data['status'].lower())
        if not new_status:
            return jsonify({
                "success": False,
                "error": "Invalid status"
            }), 400

        db = get_db()
        try:
            gap = db.query(KnowledgeGap).filter(
                KnowledgeGap.id == gap_id,
                KnowledgeGap.tenant_id == g.tenant_id
            ).first()

            if not gap:
                return jsonify({
                    "success": False,
                    "error": "Gap not found"
                }), 404

            gap.status = new_status
            gap.updated_at = utc_now()

            if new_status == GapStatus.CLOSED:
                gap.closed_at = utc_now()

            db.commit()

            return jsonify({
                "success": True,
                "gap": gap.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GAP FEEDBACK (for improving detection accuracy)
# ============================================================================

@knowledge_bp.route('/gaps/<gap_id>/feedback', methods=['POST'])
@require_auth
def submit_gap_feedback(gap_id: str):
    """
    Submit feedback on a knowledge gap's usefulness.
    This helps improve gap detection accuracy over time.

    Request body:
    {
        "useful": true | false,
        "comment": "Optional comment explaining why"
    }

    Response:
    {
        "success": true,
        "gap": { ... with updated feedback counts }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400

        useful = data.get('useful')
        comment = data.get('comment', '').strip()

        if useful is None:
            return jsonify({
                "success": False,
                "error": "'useful' field required (true/false)"
            }), 400

        db = get_db()
        try:
            gap = db.query(KnowledgeGap).filter(
                KnowledgeGap.id == gap_id,
                KnowledgeGap.tenant_id == g.tenant_id
            ).first()

            if not gap:
                return jsonify({
                    "success": False,
                    "error": "Gap not found"
                }), 404

            # Update feedback counts
            if useful:
                gap.feedback_useful = (gap.feedback_useful or 0) + 1
            else:
                gap.feedback_not_useful = (gap.feedback_not_useful or 0) + 1

            # Add comment if provided
            if comment:
                comments = gap.feedback_comments or []
                comments.append({
                    "user_id": g.user_id,
                    "useful": useful,
                    "comment": comment,
                    "timestamp": utc_now().isoformat()
                })
                gap.feedback_comments = comments

            gap.updated_at = utc_now()
            db.commit()

            return jsonify({
                "success": True,
                "gap": gap.to_dict(),
                "message": "Feedback recorded. Thank you for helping improve gap detection!"
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@knowledge_bp.route('/gaps/stats', methods=['GET'])
@require_auth
def get_gap_stats():
    """
    Get statistics about knowledge gaps including feedback summary.

    Response:
    {
        "success": true,
        "stats": {
            "total_gaps": 50,
            "open_gaps": 30,
            "closed_gaps": 20,
            "total_useful_feedback": 100,
            "total_not_useful_feedback": 20,
            "feedback_ratio": 0.83,
            "by_category": {...},
            "by_source_pattern": {...}
        }
    }
    """
    try:
        from sqlalchemy import func

        db = get_db()
        try:
            # Basic counts
            total = db.query(func.count(KnowledgeGap.id)).filter(
                KnowledgeGap.tenant_id == g.tenant_id
            ).scalar()

            open_count = db.query(func.count(KnowledgeGap.id)).filter(
                KnowledgeGap.tenant_id == g.tenant_id,
                KnowledgeGap.status == GapStatus.OPEN
            ).scalar()

            closed_count = db.query(func.count(KnowledgeGap.id)).filter(
                KnowledgeGap.tenant_id == g.tenant_id,
                KnowledgeGap.status == GapStatus.CLOSED
            ).scalar()

            # Feedback totals
            useful_total = db.query(func.sum(KnowledgeGap.feedback_useful)).filter(
                KnowledgeGap.tenant_id == g.tenant_id
            ).scalar() or 0

            not_useful_total = db.query(func.sum(KnowledgeGap.feedback_not_useful)).filter(
                KnowledgeGap.tenant_id == g.tenant_id
            ).scalar() or 0

            total_feedback = useful_total + not_useful_total
            feedback_ratio = useful_total / total_feedback if total_feedback > 0 else 0

            # By category
            category_counts = {}
            for category in GapCategory:
                count = db.query(func.count(KnowledgeGap.id)).filter(
                    KnowledgeGap.tenant_id == g.tenant_id,
                    KnowledgeGap.category == category
                ).scalar()
                category_counts[category.value] = count

            return jsonify({
                "success": True,
                "stats": {
                    "total_gaps": total,
                    "open_gaps": open_count,
                    "closed_gaps": closed_count,
                    "total_useful_feedback": useful_total,
                    "total_not_useful_feedback": not_useful_total,
                    "feedback_ratio": round(feedback_ratio, 2),
                    "by_category": category_counts
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
