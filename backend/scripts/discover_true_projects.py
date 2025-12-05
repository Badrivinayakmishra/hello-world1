import os
#!/usr/bin/env python3
"""
Discover TRUE projects using LLM-first clustering.
Projects are defined by shared deliverables, goals, and entities - NOT by space/team membership.

This uses the sophisticated clustering logic to find documents that are actually part of the same project,
even if they're in different Google Chat spaces or teams.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pickle
from openai import AzureOpenAI
from clustering.llm_first_clusterer import LLMFirstClusterer
from collections import defaultdict, Counter

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


DATA_DIR = Path("club_data")
client = OpenAI()

def load_all_documents():
    """Load all documents from embedding index"""
    embedding_file = DATA_DIR / "embedding_index.pkl"
    if not embedding_file.exists():
        return []

    with open(embedding_file, 'rb') as f:
        data = pickle.load(f)

    chunks = data.get('chunks', [])

    # Deduplicate by doc_id
    docs_by_id = {}
    for chunk in chunks:
        doc_id = chunk.get('doc_id')
        if doc_id and doc_id not in docs_by_id:
            # Prepare document in format expected by clusterer
            docs_by_id[doc_id] = {
                'id': doc_id,
                'content': chunk.get('content', ''),
                'metadata': chunk.get('metadata', {}),
                **chunk  # Include all original fields
            }

    return list(docs_by_id.values())

def generate_project_name_from_cluster(clusterer, cluster_doc_ids):
    """Generate intelligent project name from cluster using the signatures"""

    # Get signatures for documents in this cluster
    signatures = []
    for doc_id in cluster_doc_ids[:20]:  # Sample up to 20 docs
        if doc_id in clusterer.signatures:
            signatures.append(clusterer.signatures[doc_id])

    if not signatures:
        return "Unknown Project", "No project information available"

    # Aggregate information from signatures
    all_deliverables = [s.core_deliverable for s in signatures if s.core_deliverable != "Unknown"]
    all_goals = [s.project_goal for s in signatures if s.project_goal != "Unknown"]
    all_entities = []
    all_keywords = []

    for s in signatures:
        all_entities.extend(s.key_entities)
        all_keywords.extend(s.technical_keywords)

    # Find most common elements
    deliverable_counts = Counter(all_deliverables)
    entity_counts = Counter(all_entities)
    keyword_counts = Counter(all_keywords)

    # Get top elements
    top_deliverable = deliverable_counts.most_common(1)[0][0] if deliverable_counts else "Project Work"
    top_entities = [e for e, c in entity_counts.most_common(3)]
    top_keywords = [k for k, c in keyword_counts.most_common(5)]

    # Create summary for LLM
    summary = f"""Based on {len(signatures)} documents analyzed:

Core Deliverable: {top_deliverable}
Key Entities: {', '.join(top_entities) if top_entities else 'None'}
Technical Keywords: {', '.join(top_keywords) if top_keywords else 'None'}
Sample Goals:
{chr(10).join(f'- {g}' for g in list(set(all_goals))[:5])}

Generate a concise, specific project name (3-6 words) and description.
Focus on the actual work being done, the client/stakeholder, and the domain.

Respond in JSON:
{{
  "name": "Specific Project Name",
  "description": "One-sentence description of the project's purpose and deliverable"
}}
"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": summary}],
            response_format={"type": "json_object"},
            temperature=0.2
        )

        result = json.loads(response.choices[0].message.content)
        return result.get('name', top_deliverable), result.get('description', '')

    except Exception as e:
        print(f"⚠ Name generation failed: {e}")
        # Fallback: use most common deliverable and entity
        if top_entities:
            name = f"{top_entities[0]} - {top_deliverable}"
        else:
            name = top_deliverable
        return name, f"Project focused on {top_deliverable.lower()}"

def main():
    print("="*70)
    print("TRUE PROJECT DISCOVERY: Content-Based LLM Clustering")
    print("="*70)
    print("\nThis finds ACTUAL projects based on shared goals, deliverables,")
    print("and entities - regardless of which space/team they came from.\n")

    # Load all documents
    print("Loading documents...")
    all_docs = load_all_documents()

    if not all_docs:
        print("✗ No documents found")
        return

    print(f"✓ Loaded {len(all_docs)} unique documents")

    # Sample for testing (you can increase this later)
    # For full analysis, remove this line
    sample_size = min(200, len(all_docs))  # Start with 200 docs for testing
    import random
    sample_docs = random.sample(all_docs, sample_size)
    print(f"\n📊 Processing sample of {len(sample_docs)} documents")
    print("   (Increase sample_size in script for full analysis)\n")

    # Initialize LLM-first clusterer
    print("Initializing LLM-first clusterer...")
    clusterer = LLMFirstClusterer()

    # Run clustering
    print("\nRunning LLM-first clustering...")
    print("This will:")
    print("  1. Extract project signatures from each document")
    print("  2. Compare documents using LLM to find shared projects")
    print("  3. Build similarity graph and detect communities")
    print("  4. Validate and merge clusters\n")

    try:
        results = clusterer.process_documents(sample_docs)
        clusters = results.get('projects', {})

        # Clusters are already in the format: {cluster_id: [doc_ids]}
        if not clusters:
            print("\n⚠ No projects discovered")
            return

    except Exception as e:
        print(f"\n✗ Clustering failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"\n✓ Discovered {len(clusters)} distinct projects!")

    # Generate names for each cluster
    canonical_projects = {}

    print("\nGenerating project names from content...")
    for i, (cluster_id, doc_ids) in enumerate(sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True), 1):
        print(f"\n[{i}/{len(clusters)}] Cluster with {len(doc_ids)} documents")

        name, description = generate_project_name_from_cluster(clusterer, doc_ids)

        # Estimate total size based on sample
        sample_ratio = len(sample_docs) / len(all_docs)
        estimated_total = int(len(doc_ids) / sample_ratio) if sample_ratio > 0 else len(doc_ids)

        project_id = f"project_{i}"
        canonical_projects[project_id] = {
            "id": project_id,
            "name": name,
            "description": description,
            "document_count": estimated_total,
            "sample_doc_count": len(doc_ids),
            "status": "active",
            "discovery_method": "llm_first_clustering"
        }

        print(f"  ✓ {name}")
        print(f"    {description}")
        print(f"    Estimated docs: ~{estimated_total} ({len(doc_ids)} in sample)")

    # Save to file
    output_file = DATA_DIR / "canonical_projects.json"
    with open(output_file, 'w') as f:
        json.dump(canonical_projects, f, indent=2)

    print(f"\n{'='*70}")
    print(f"✓ TRUE PROJECT DISCOVERY COMPLETE")
    print(f"{'='*70}")
    print(f"  Discovered: {len(canonical_projects)} real projects")
    print(f"  Sample analyzed: {len(sample_docs)} docs")
    print(f"  Total docs in system: {len(all_docs)}")
    print(f"  Saved to: {output_file}")
    print(f"{'='*70}")

    # Print final summary
    print("\nDiscovered Projects (sorted by estimated size):")
    for proj_id, proj in sorted(canonical_projects.items(), key=lambda x: x[1]['document_count'], reverse=True):
        print(f"\n  {proj['name']}")
        print(f"    ~{proj['document_count']} documents")
        print(f"    {proj['description']}")

    print(f"\n💡 To analyze ALL documents, edit this script and increase sample_size")

if __name__ == "__main__":
    main()
