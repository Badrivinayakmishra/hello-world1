import os
#!/usr/bin/env python3
"""
Discover real projects using LLM-first clustering and generate proper project names.
This replaces stakeholder group names with actual project names based on content.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pickle
from openai import AzureOpenAI
from clustering.llm_first_clusterer import LLMFirstClusterer
from collections import defaultdict

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


DATA_DIR = Path("club_data")
client = OpenAI()

def load_documents():
    """Load all documents from the backend's data store"""
    # Try different data sources

    # First try embedding index (this has chunks which represent documents)
    embedding_file = DATA_DIR / "embedding_index.pkl"
    if embedding_file.exists():
        with open(embedding_file, 'rb') as f:
            data = pickle.load(f)

            # Get chunks from embedding index
            chunks = data.get('chunks', [])
            if chunks:
                print(f"✓ Loaded {len(chunks)} chunks from embedding_index.pkl")

                # Group chunks by doc_id to get unique documents
                docs_by_id = {}
                for chunk in chunks:
                    doc_id = chunk.get('doc_id') or chunk.get('id') or chunk.get('message_id')
                    if doc_id and doc_id not in docs_by_id:
                        docs_by_id[doc_id] = chunk

                print(f"✓ Found {len(docs_by_id)} unique documents")
                return list(docs_by_id.values())

    # Try search index
    search_file = DATA_DIR / "search_index.pkl"
    if search_file.exists():
        with open(search_file, 'rb') as f:
            data = pickle.load(f)
            docs = data.get('messages', [])
            if docs:
                print(f"✓ Loaded {len(docs)} documents from search_index.pkl")
                return docs

    # Try classified directory
    classified_dir = DATA_DIR / "classified"
    if classified_dir.exists():
        all_docs = []
        for json_file in classified_dir.glob("*.json"):
            with open(json_file) as f:
                doc = json.load(f)
                all_docs.append(doc)
        if all_docs:
            print(f"✓ Loaded {len(all_docs)} documents from classified/*.json")
            return all_docs

    print("✗ No documents found in any data source")
    return []

def generate_project_name_and_description(cluster_docs, cluster_id):
    """Use LLM to generate a proper project name and description from cluster documents"""

    # Sample up to 10 documents from the cluster for analysis
    sample_docs = cluster_docs[:min(10, len(cluster_docs))]

    # Extract key content from documents
    doc_summaries = []
    for i, doc in enumerate(sample_docs, 1):
        content = doc.get('content', doc.get('text', ''))[:500]  # First 500 chars
        doc_summaries.append(f"Document {i}:\n{content}\n")

    combined_content = "\n".join(doc_summaries)

    prompt = f"""Analyze these {len(cluster_docs)} documents that belong to the same project cluster.

{combined_content}

Based on the content above, generate:
1. A concise project name (3-6 words max) that describes what this project is actually about
2. A 1-sentence description of the project's goal or deliverable

Focus on:
- The core deliverable or outcome
- The client/stakeholder if mentioned
- The domain (healthcare, marketing, supply chain, etc.)
- Key technical focus

Avoid generic names like "Startup Team" or "Group A". Use specific, content-based names.

Respond in JSON:
{{
  "name": "Specific Project Name",
  "description": "Brief description of what this project delivers or aims to achieve"
}}

Examples of good names:
- "UCLA Health Lupus Treatment Initiative"
- "Amgen Supply Chain Optimization"
- "Nike E-commerce Platform Redesign"

Examples of bad names (too generic):
- "Healthcare Project"
- "Consulting Work"
- "Team A Documents"
"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        result = json.loads(response.choices[0].message.content)
        return result.get('name', f'Project {cluster_id}'), result.get('description', '')

    except Exception as e:
        print(f"⚠ Failed to generate name for cluster {cluster_id}: {e}")
        return f'Project {cluster_id}', ''

def main():
    print("="*70)
    print("PROJECT DISCOVERY: LLM-First Clustering with Smart Naming")
    print("="*70)

    # Load documents
    documents = load_documents()
    if not documents:
        print("No documents to process")
        return

    print(f"\nProcessing {len(documents)} documents...")

    # Initialize clusterer
    clusterer = LLMFirstClusterer()

    # Run clustering
    print("\nPhase 1: Extracting project signatures...")
    project_assignments = clusterer.cluster_documents(documents)

    # Group documents by cluster
    clusters = defaultdict(list)
    for doc_id, cluster_id in project_assignments.items():
        # Find the document
        doc = next((d for d in documents if d.get('id') == doc_id or d.get('message_id') == doc_id), None)
        if doc:
            clusters[cluster_id].append(doc)

    print(f"\n✓ Found {len(clusters)} project clusters")

    # Generate names for each cluster
    canonical_projects = {}

    for i, (cluster_id, cluster_docs) in enumerate(sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True), 1):
        print(f"\nCluster {i}/{len(clusters)}: {len(cluster_docs)} documents")
        print("  Generating project name...")

        name, description = generate_project_name_and_description(cluster_docs, cluster_id)

        project_id = f"project_{i}"
        canonical_projects[project_id] = {
            "id": project_id,
            "name": name,
            "description": description,
            "document_count": len(cluster_docs),
            "status": "active",
            "cluster_id": cluster_id
        }

        print(f"  ✓ {name}")
        print(f"    {description}")

    # Save to canonical_projects.json
    output_file = DATA_DIR / "canonical_projects.json"
    with open(output_file, 'w') as f:
        json.dump(canonical_projects, f, indent=2)

    print(f"\n{'='*70}")
    print(f"✓ Discovered {len(canonical_projects)} projects")
    print(f"✓ Saved to {output_file}")
    print(f"{'='*70}")

    # Print summary
    print("\nProject Summary:")
    for proj_id, proj in sorted(canonical_projects.items(), key=lambda x: x[1]['document_count'], reverse=True):
        print(f"\n  {proj['name']}")
        print(f"    Documents: {proj['document_count']}")
        print(f"    {proj['description']}")

if __name__ == "__main__":
    main()
