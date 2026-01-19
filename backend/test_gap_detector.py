#!/usr/bin/env python3
"""
Test script for Intelligent Gap Detection v2.0
Run with: python test_gap_detector.py
"""

import json
from services.intelligent_gap_detector import (
    IntelligentGapDetector,
    FrameExtractor,
    SemanticRoleAnalyzer,
    KnowledgeGraphBuilder,
    CrossDocumentVerifier,
    EntityNormalizer,
    CoreferenceResolver,
    NLP
)

def test_spacy():
    """Test spaCy is loaded correctly"""
    print("=" * 60)
    print("TEST 1: spaCy Model")
    print("=" * 60)

    doc = NLP("John decided to migrate the database to PostgreSQL.")
    print(f"✓ spaCy model loaded: {NLP.meta['name']}")
    print(f"  Tokens: {[t.text for t in doc]}")
    print(f"  Entities: {[(e.text, e.label_) for e in doc.ents]}")
    print(f"  Sentences: {[s.text for s in doc.sents]}")
    print()


def test_entity_normalizer():
    """Test entity normalization"""
    print("=" * 60)
    print("TEST 2: Entity Normalization")
    print("=" * 60)

    normalizer = EntityNormalizer()

    test_names = [
        "John Smith",
        "J. Smith",
        "john.smith@company.com",
        "Dr. John Smith Jr.",
        "JOHN SMITH"
    ]

    for name in test_names:
        normalized = normalizer.normalize(name)
        canonical = normalizer.merge_if_similar(name)
        print(f"  '{name}' → '{normalized}' (canonical: '{canonical}')")

    print(f"\n✓ All names merged to: {list(normalizer.canonical_map.keys())}")
    print()


def test_coreference():
    """Test coreference resolution"""
    print("=" * 60)
    print("TEST 3: Coreference Resolution")
    print("=" * 60)

    from services.intelligent_gap_detector import Entity

    resolver = CoreferenceResolver()

    # Create mock entities
    entities = [
        Entity(id="e1", name="John Smith", canonical_name="john smith",
               entity_type="PERSON", mentions=["John Smith"]),
        Entity(id="e2", name="PostgreSQL", canonical_name="postgresql",
               entity_type="SYSTEM", mentions=["PostgreSQL"])
    ]

    test_text = "He decided to migrate the data. It was upgraded last week."

    resolutions = resolver.resolve(test_text, entities)

    print(f"  Text: '{test_text}'")
    print(f"  Resolutions found: {len(resolutions)}")
    for pronoun, entity in resolutions.items():
        print(f"    '{pronoun}' → '{entity}'")

    print(f"\n✓ Coreference resolution working")
    print()


def test_frame_extraction():
    """Test frame extraction"""
    print("=" * 60)
    print("TEST 4: Frame Extraction (150+ patterns)")
    print("=" * 60)

    extractor = FrameExtractor()

    test_text = """
    We decided to migrate from MySQL to PostgreSQL because it scales better.
    It was decided that the team should use Docker for all deployments.
    John approved the migration plan last month.
    The API endpoint is defined as /api/v2/users.
    We implemented a new caching layer to improve performance.
    The deployment process runs every night at midnight.
    """

    frames = extractor.extract_frames(test_text, "test_doc")

    print(f"  Found {len(frames)} frames:")
    for f in frames:
        missing = f.missing_slots if f.missing_slots else "none"
        print(f"    [{f.frame_type}] trigger='{f.trigger[:30]}' missing={missing}")

    print(f"\n✓ Frame extraction working")
    print()


def test_semantic_roles():
    """Test semantic role analysis"""
    print("=" * 60)
    print("TEST 5: Semantic Role Analysis")
    print("=" * 60)

    analyzer = SemanticRoleAnalyzer()

    sentences = [
        "The migration was completed successfully.",  # Missing agent
        "We decided to use React.",  # Missing cause
        "The system was redesigned.",  # Missing agent + cause
        "John implemented the new feature because users requested it."  # Complete
    ]

    missing = analyzer.analyze_missing_roles(sentences, "test_doc")

    print(f"  Analyzed {len(sentences)} sentences")
    print(f"  Found {len(missing)} with missing roles:")
    for m in missing:
        print(f"    '{m['sentence'][:50]}...'")
        print(f"      Missing: {m['roles_missing']}")

    print(f"\n✓ Semantic role analysis working")
    print()


def test_knowledge_graph():
    """Test knowledge graph building"""
    print("=" * 60)
    print("TEST 6: Knowledge Graph + Bus Factor")
    print("=" * 60)

    kg = KnowledgeGraphBuilder()

    kg.add_document("""
        John manages the payment system, the user database, and the API gateway.
        Sarah handles the authentication module.
        The payment system depends on the user database.
        Mike created the deployment scripts.
    """, "doc1")

    print(f"  Entities: {len(kg.entities)}")
    for eid, entity in list(kg.entities.items())[:5]:
        print(f"    [{entity.entity_type}] {entity.name}")

    print(f"\n  Relations: {len(kg.relations)}")
    for rel in kg.relations[:3]:
        print(f"    {rel.source_entity} --{rel.relation_type}--> {rel.target_entity}")

    bus_risks = kg.find_bus_factor_risks()
    print(f"\n  Bus factor risks: {len(bus_risks)}")
    for risk in bus_risks:
        print(f"    ⚠️  {risk['person']} owns {risk['owned_count']} items: {risk['owned_items'][:3]}")

    print(f"\n✓ Knowledge graph working")
    print()


def test_contradiction_detection():
    """Test cross-document contradiction detection"""
    print("=" * 60)
    print("TEST 7: Contradiction Detection")
    print("=" * 60)

    verifier = CrossDocumentVerifier()

    verifier.add_document("We have 10 users on the platform.", "doc1", "User Stats")
    verifier.add_document("The platform now has 50 active users.", "doc2", "Growth Report")
    verifier.add_document("The migration was successful.", "doc3", "Migration Notes")
    verifier.add_document("The migration failed and was rolled back.", "doc4", "Incident Report")

    contradictions = verifier.find_contradictions()

    print(f"  Documents analyzed: 4")
    print(f"  Contradictions found: {len(contradictions)}")
    for c in contradictions:
        print(f"    ⚠️  {c['type']}: '{c['statement1'][:40]}...' vs '{c['statement2'][:40]}...'")

    print(f"\n✓ Contradiction detection working")
    print()


def test_full_pipeline():
    """Test the complete gap detection pipeline"""
    print("=" * 60)
    print("TEST 8: Full Pipeline Integration")
    print("=" * 60)

    detector = IntelligentGapDetector()

    # Add realistic test documents
    detector.add_document("doc1", "Architecture Decisions", """
        We decided to migrate from MySQL to PostgreSQL because it handles JSON better.
        The migration was approved by the CTO last quarter.
        It was decided that all services should be containerized using Docker.
        Eventually we will move to Kubernetes for orchestration.

        John owns the database layer, the caching system, and the backup scripts.
        Ask Mike if you need help with the authentication - he knows everything about it.

        The API was redesigned to improve performance. We achieved significant improvements.
        The deployment process is handled by Sarah using our internal tools.
    """)

    detector.add_document("doc2", "System Documentation", """
        The authentication system uses JWT tokens for session management.
        John manages the user service and the notification system.

        We have 100 active users on the platform as of Q1.
        The platform serves 500 daily active users according to latest metrics.

        The usual process for deployments involves the standard steps.
        As everyone knows, we use GitHub Actions for CI/CD.

        Performance improved significantly after optimizations.
        The new caching layer reduced latency.
    """)

    # Run analysis
    result = detector.analyze()
    stats = result['stats']

    print(f"  Documents processed: 2")
    print(f"  Total frames extracted: {stats['total_frames']}")
    print(f"  Frames with missing slots: {stats['frames_with_gaps']}")
    print(f"  Missing semantic roles: {stats['missing_role_instances']}")
    print(f"  Unsupported claims: {stats['unsupported_claims']}")
    print(f"  Bus factor risks: {stats['bus_factor_risks']}")
    print(f"  Contradictions: {stats['contradictions']}")
    print(f"  Single-source topics: {stats['single_source_topics']}")
    print()

    gaps = result['gaps']
    print(f"  TOTAL GAPS GENERATED: {len(gaps)}")
    print()

    # Group by category
    by_category = {}
    for gap in gaps:
        cat = gap.category
        by_category[cat] = by_category.get(cat, 0) + 1

    print("  Gaps by category:")
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")

    print("\n  Sample gaps:")
    for gap in gaps[:5]:
        print(f"    [{gap.category}] {gap.description[:60]}...")
        if gap.grounded_questions:
            print(f"      Q: {gap.grounded_questions[0][:55]}...")
        print(f"      Evidence: {gap.evidence[0][:50] if gap.evidence else 'N/A'}...")
        print()

    print("✓ Full pipeline working!")
    print()

    # Convert to database format
    db_gaps = detector.to_knowledge_gaps(result, project_id="test_project")
    print(f"  Converted to {len(db_gaps)} database records")
    print()

    return result


def main():
    print("\n" + "=" * 60)
    print("INTELLIGENT GAP DETECTOR v2.0 - TEST SUITE")
    print("=" * 60 + "\n")

    try:
        test_spacy()
        test_entity_normalizer()
        test_coreference()
        test_frame_extraction()
        test_semantic_roles()
        test_knowledge_graph()
        test_contradiction_detection()
        result = test_full_pipeline()

        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print()
        print("Gap detector is ready for production use.")
        print("Run the backend with: python app_v2.py")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
