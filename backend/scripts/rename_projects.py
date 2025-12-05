import os
#!/usr/bin/env python3
"""
Rename existing projects using LLM analysis of their documents.
Takes the current canonical_projects.json and generates better names based on actual content.
"""

import json
import pickle
from pathlib import Path
from openai import AzureOpenAI
from collections import defaultdict

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


DATA_DIR = Path("club_data")
client = OpenAI()

def load_embedding_index():
    """Load the embedding index"""
    embedding_file = DATA_DIR / "embedding_index.pkl"
    if embedding_file.exists():
        with open(embedding_file, 'rb') as f:
            return pickle.load(f)
    return None

def get_documents_for_space(space_name, embedding_index):
    """Get documents belonging to a specific space/stakeholder"""
    if not embedding_index:
        return []

    chunks = embedding_index.get('chunks', [])
    space_docs = []

    for chunk in chunks:
        # Match by space_name or stakeholder
        chunk_space = chunk.get('space_name', chunk.get('stakeholder', ''))
        if chunk_space == space_name:
            space_docs.append(chunk)

    # Deduplicate by doc_id
    seen_ids = set()
    unique_docs = []
    for doc in space_docs:
        doc_id = doc.get('doc_id') or doc.get('id') or doc.get('message_id')
        if doc_id and doc_id not in seen_ids:
            seen_ids.add(doc_id)
            unique_docs.append(doc)

    return unique_docs

def generate_project_name_and_description(documents, old_name):
    """Use LLM to generate a better project name and description"""

    if not documents:
        return old_name, "No documents available"

    # Sample up to 10 documents
    sample_docs = documents[:min(10, len(documents))]

    # Extract content
    doc_samples = []
    for i, doc in enumerate(sample_docs, 1):
        content = doc.get('content', doc.get('text', ''))[:400]
        doc_samples.append(f"Document {i}:\n{content}\n")

    combined_content = "\n".join(doc_samples)

    prompt = f"""Analyze these {len(documents)} documents that were previously grouped as "{old_name}".

{combined_content}

Based on the ACTUAL CONTENT above, generate:
1. A concise, specific project name (3-6 words) that describes what this project is really about
2. A 1-sentence description of the project's goal or deliverable

Guidelines:
- Be SPECIFIC, not generic
- Focus on the core deliverable, client, or topic
- Use domain-specific terminology (healthcare, consulting, research, etc.)
- Avoid names like "Startup Team" or "Group A"
- If it's personal documents (photos, receipts, personal files), name it clearly as such

Respond in JSON:
{{
  "name": "Specific Project Name",
  "description": "Brief description of what this project delivers"
}}

Examples:
Good: "UCLA Health Lupus Treatment Initiative", "Amgen Supply Chain Optimization", "Personal Finance & Travel Documents"
Bad: "Healthcare Project", "Consulting Work", "Team Documents"
"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        result = json.loads(response.choices[0].message.content)
        return result.get('name', old_name), result.get('description', '')

    except Exception as e:
        print(f"⚠ Failed to generate name: {e}")
        return old_name, ''

def main():
    print("="*70)
    print("PROJECT RENAMING: LLM-based intelligent naming")
    print("="*70)

    # Load current projects
    projects_file = DATA_DIR / "canonical_projects.json"
    if not projects_file.exists():
        print(f"✗ No canonical_projects.json found at {projects_file}")
        return

    with open(projects_file) as f:
        projects = json.load(f)

    print(f"\nFound {len(projects)} projects to rename")

    # Load embedding index
    print("\nLoading document index...")
    embedding_index = load_embedding_index()
    if not embedding_index:
        print("✗ Could not load embedding index")
        return

    chunks = embedding_index.get('chunks', [])
    print(f"✓ Loaded {len(chunks)} document chunks")

    # Rename each project
    updated_projects = {}

    for project_id, project in projects.items():
        old_name = project['name']
        old_desc = project.get('description', '')

        print(f"\n{'='*70}")
        print(f"Project: {old_name}")
        print(f"  Current docs: {project['document_count']}")

        # Get documents for this space
        documents = get_documents_for_space(old_name, embedding_index)

        if not documents:
            print(f"  ⚠ No documents found for '{old_name}', keeping original name")
            updated_projects[project_id] = project
            continue

        print(f"  Found {len(documents)} documents to analyze")
        print(f"  Generating new name...")

        # Generate new name
        new_name, new_desc = generate_project_name_and_description(documents, old_name)

        updated_projects[project_id] = {
            **project,
            'name': new_name,
            'description': new_desc,
            'document_count': len(documents),  # Update with actual count
            'original_name': old_name  # Keep track of original
        }

        print(f"  ✓ NEW: {new_name}")
        print(f"    {new_desc}")

    # Save updated projects
    with open(projects_file, 'w') as f:
        json.dump(updated_projects, f, indent=2)

    print(f"\n{'='*70}")
    print(f"✓ Renamed {len(updated_projects)} projects")
    print(f"✓ Saved to {projects_file}")
    print(f"{'='*70}")

    # Print summary
    print("\nFinal Project List:")
    for proj_id, proj in sorted(updated_projects.items(), key=lambda x: x[1]['document_count'], reverse=True):
        print(f"\n  {proj['name']}")
        print(f"    Documents: {proj['document_count']}")
        print(f"    {proj['description']}")
        if proj.get('original_name') and proj['original_name'] != proj['name']:
            print(f"    (was: {proj['original_name']})")

if __name__ == "__main__":
    main()
