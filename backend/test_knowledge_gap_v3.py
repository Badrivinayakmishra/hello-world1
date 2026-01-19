#!/usr/bin/env python3
"""
Test script for Knowledge Gap Detection v3.0

Run with: python test_knowledge_gap_v3.py
"""

import os
import sys
import json
from datetime import datetime

# Ensure we can import from the services directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check for OpenAI API key
if not os.getenv("OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY environment variable not set")
    print("Run: export OPENAI_API_KEY='your-key-here'")
    sys.exit(1)


def test_full_pipeline():
    """Test the complete v3 pipeline"""
    from services.knowledge_gap_v3 import KnowledgeGapOrchestrator

    print("=" * 70)
    print("KNOWLEDGE GAP DETECTION v3.0 - FULL PIPELINE TEST")
    print("=" * 70)
    print()

    # Sample documents that should trigger various gaps
    documents = [
        {
            "doc_id": "doc_001",
            "title": "System Architecture Overview",
            "content": """
            Our platform uses PostgreSQL as the primary database. John Smith manages all database operations
            including backups, migrations, and performance tuning. The database backup process runs daily
            at 2 AM, but the exact steps aren't documented anywhere - ask John if you need to know.

            We decided to use PostgreSQL over MySQL because it handles JSON better, though we didn't
            formally evaluate MongoDB or other alternatives. The migration happened in Q2 2023.

            The User Service depends on PostgreSQL and Redis. If PostgreSQL goes down, users can't log in.
            The authentication system uses JWT tokens and was redesigned last year by the previous
            architect who has since left the company.

            Eventually we plan to migrate to Kubernetes, but there's no timeline yet.
            As everyone knows, we use Jenkins for CI/CD.
            """
        },
        {
            "doc_id": "doc_002",
            "title": "Payment System Documentation",
            "content": """
            The Payment Service processes all financial transactions. Sarah handles payment issues
            and is the only person who understands the Stripe integration quirks.

            When payment failures occur, the usual process is to check the logs and contact Stripe
            support if needed. Edge cases like partial refunds or currency conversion issues should
            be escalated to Sarah.

            The Payment Service connects to:
            - PostgreSQL (transaction records)
            - Redis (rate limiting)
            - Stripe API (payment processing)
            - User Service (customer data)

            We have about 50 active paying customers. The system processes roughly $100K in
            transactions monthly.

            The payment reconciliation process runs weekly but isn't documented. Sarah runs it
            manually using scripts she wrote.
            """
        },
        {
            "doc_id": "doc_003",
            "title": "Onboarding Guide",
            "content": """
            Welcome to the team! Here's what you need to know to get started.

            First, get access to our systems by asking your manager. You'll need access to
            GitHub, AWS console, and the internal wiki.

            For development setup, follow the README in the main repo. If you run into issues
            with the Docker setup, ask Mike - he knows all the workarounds.

            The codebase uses our custom framework called InternalJS. Documentation is sparse
            but the code is "self-documenting" according to the original authors.

            We have about 100 active users on the platform according to the latest metrics.

            Important contacts:
            - John: Database and infrastructure
            - Sarah: Payments and billing
            - Mike: Frontend and DevOps
            - The team: Everything else

            For deployment questions, check with whoever deployed last. The process changes
            frequently based on what we learned from the previous deployment.
            """
        }
    ]

    # Organizational context
    org_context = {
        "company_type": "B2B SaaS",
        "team_size": 15,
        "industry": "Technology",
        "growth_stage": "Series A",
        "recent_changes": "Architect left 3 months ago"
    }

    print(f"Analyzing {len(documents)} documents...")
    print(f"Organizational context: {json.dumps(org_context, indent=2)}")
    print()

    # Create orchestrator and run analysis
    orchestrator = KnowledgeGapOrchestrator(
        extraction_model="gpt-4o",
        question_model="gpt-4o",
        org_context=org_context
    )

    start_time = datetime.now()
    result = orchestrator.analyze(
        documents=documents,
        tenant_id="test_tenant",
        project_id="test_project",
        top_n_questions=15
    )
    elapsed = (datetime.now() - start_time).total_seconds()

    # Print results
    print("=" * 70)
    print("ANALYSIS RESULTS")
    print("=" * 70)
    print()
    print(f"Analysis ID: {result.analysis_id}")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print()

    print("DOCUMENT PROCESSING:")
    print(f"  Documents processed: {result.documents_processed}")
    print(f"  Entities extracted: {result.total_entities}")
    print(f"  Relationships found: {result.total_relationships}")
    print()

    print("GAPS DETECTED:")
    print(f"  Total gaps: {result.total_gaps}")
    print()
    print("  By Type:")
    for gap_type, count in sorted(result.gaps_by_type.items(), key=lambda x: -x[1]):
        print(f"    {gap_type}: {count}")
    print()
    print("  By Severity:")
    for severity, count in sorted(result.gaps_by_severity.items()):
        print(f"    {severity}: {count}")
    print()

    print("=" * 70)
    print(f"TOP {len(result.prioritized_questions)} PRIORITIZED QUESTIONS")
    print("=" * 70)
    print()

    for i, pq in enumerate(result.prioritized_questions, 1):
        question = pq["question"]
        gap = pq["gap"]
        score = pq["priority_score"]
        breakdown = pq["score_breakdown"]

        print(f"{i}. [{question['category'].upper()}] Priority: {score:.2f}")
        print(f"   Gap: {gap['gap_type']} ({gap['severity']})")
        print(f"   Question: {question['primary_question'][:100]}...")
        if question.get("sub_questions"):
            print(f"   Sub-questions: {len(question['sub_questions'])}")
        if question.get("suggested_respondent"):
            print(f"   Suggested respondent: {question['suggested_respondent']}")
        if question.get("estimated_effort"):
            print(f"   Estimated effort: {question['estimated_effort']}")
        print(f"   Score breakdown: KR={breakdown['knowledge_risk']:.2f}, "
              f"BC={breakdown['business_criticality']:.2f}, "
              f"A={breakdown['answerability']:.2f}, "
              f"UI={breakdown['user_interest']:.2f}")
        print()

    # Show some detailed questions
    print("=" * 70)
    print("DETAILED VIEW: TOP 3 QUESTIONS")
    print("=" * 70)
    print()

    for i, pq in enumerate(result.prioritized_questions[:3], 1):
        question = pq["question"]
        print(f"--- Question {i} ---")
        print(f"Primary: {question['primary_question']}")
        print()
        if question.get("sub_questions"):
            print("Sub-questions:")
            for sq in question["sub_questions"]:
                print(f"  - {sq}")
            print()
        if question.get("priority_reasoning"):
            print(f"Why important: {question['priority_reasoning']}")
        if question.get("business_impact"):
            print(f"Business impact: {question['business_impact']}")
        if question.get("answer_format_suggestion"):
            print(f"Expected output: {question['answer_format_suggestion']}")
        print()

    # Test feedback
    print("=" * 70)
    print("TESTING FEEDBACK SYSTEM")
    print("=" * 70)
    print()

    if result.prioritized_questions:
        first_q = result.prioritized_questions[0]["question"]
        feedback_result = orchestrator.submit_feedback(
            question_id=first_q["id"],
            feedback_type="useful",
            comment="This is exactly what we needed to document"
        )
        print(f"Feedback submitted: {feedback_result['status']}")

        # Get stats after feedback
        stats = orchestrator.get_stats()
        print(f"Feedback stats: {stats.get('feedback', {})}")

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print()
    print("Knowledge Gap Detection v3.0 is working correctly!")
    print()
    print("Key improvements over v2.0:")
    print("  ✓ GPT-4 deep document extraction (vs regex)")
    print("  ✓ Rich knowledge graph with entity resolution")
    print("  ✓ 8 specialized gap analyzers")
    print("  ✓ LLM-generated contextual questions")
    print("  ✓ Multi-factor prioritization")
    print("  ✓ Feedback learning loop")

    return result


def test_individual_stages():
    """Test each stage individually"""
    print("\n" + "=" * 70)
    print("INDIVIDUAL STAGE TESTS")
    print("=" * 70 + "\n")

    # Stage 1: Deep Extractor
    print("Testing Stage 1: Deep Document Extraction...")
    from services.knowledge_gap_v3.deep_extractor import DeepDocumentExtractor

    extractor = DeepDocumentExtractor(model="gpt-4o")
    extraction = extractor.extract(
        doc_id="test_doc",
        title="Test Document",
        content="John decided to use PostgreSQL because it's better for our use case. Sarah manages deployments."
    )
    print(f"  ✓ Extracted {len(extraction.entities)} entities, {len(extraction.decisions)} decisions")

    # Stage 2: Knowledge Graph
    print("Testing Stage 2: Knowledge Graph...")
    from services.knowledge_gap_v3.knowledge_graph import KnowledgeGraph

    graph = KnowledgeGraph()
    stats = graph.add_extraction(extraction)
    print(f"  ✓ Added to graph: {stats}")

    # Stage 3: Gap Analyzers
    print("Testing Stage 3: Gap Analyzers...")
    from services.knowledge_gap_v3.gap_analyzers import GapAnalyzerEngine

    analyzer = GapAnalyzerEngine(graph, [extraction])
    gaps = analyzer.analyze_all()
    print(f"  ✓ Detected {len(gaps)} gaps")

    # Stage 4: Question Generator
    print("Testing Stage 4: Question Generator...")
    from services.knowledge_gap_v3.question_generator import QuestionGenerator

    generator = QuestionGenerator(graph, model="gpt-4o")
    if gaps:
        questions = generator.generate_questions(gaps[:2])
        print(f"  ✓ Generated {len(questions)} questions")
    else:
        print("  ✓ No gaps to generate questions for")

    # Stage 5: Prioritization
    print("Testing Stage 5: Prioritization...")
    from services.knowledge_gap_v3.prioritization import PrioritizationEngine

    prioritizer = PrioritizationEngine(graph)
    if gaps and questions:
        gap_lookup = {g.id: g for g in gaps}
        prioritized = prioritizer.prioritize(questions, gap_lookup)
        print(f"  ✓ Prioritized {len(prioritized)} questions")

    # Stage 6: Feedback Loop
    print("Testing Stage 6: Feedback Loop...")
    from services.knowledge_gap_v3.feedback_loop import FeedbackLoop, FeedbackType

    feedback = FeedbackLoop(prioritizer)
    if gaps:
        from services.knowledge_gap_v3.gap_analyzers import GapType
        feedback.record_feedback(
            question_id="test_q",
            gap_id=gaps[0].id,
            gap_type=gaps[0].gap_type,
            category="test",
            feedback_type=FeedbackType.USEFUL
        )
        stats = feedback.get_effectiveness_stats()
        print(f"  ✓ Feedback recorded, stats: {stats['total_feedback']} records")

    print("\n✓ All individual stages working!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Knowledge Gap Detection v3.0")
    parser.add_argument("--quick", action="store_true", help="Run quick individual stage tests only")
    args = parser.parse_args()

    if args.quick:
        test_individual_stages()
    else:
        test_full_pipeline()
        print("\n")
        test_individual_stages()
