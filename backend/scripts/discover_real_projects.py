import os
#!/usr/bin/env python3
"""
Discover real projects by analyzing a sample of all documents with LLM.
Generates intelligent project groupings based on actual content, not metadata.
"""

import json
import pickle
import random
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
            docs_by_id[doc_id] = chunk

    return list(docs_by_id.values())

def discover_project_themes(sample_docs):
    """Use LLM to analyze documents and discover main project themes"""

    # Create content samples
    doc_samples = []
    for i, doc in enumerate(sample_docs[:50], 1):  # Analyze up to 50 docs
        content = doc.get('content', '')[:300]
        file_name = doc.get('metadata', {}).get('file_name', 'Unknown')
        doc_samples.append(f"Doc {i} ({file_name}):\n{content}\n")

    combined = "\n".join(doc_samples)

    prompt = f"""Analyze this sample of {len(sample_docs)} documents from a knowledge base.

{combined}

Based on the content above, identify 5-8 MAIN PROJECT THEMES or categories that these documents belong to.

For each theme, provide:
1. A specific, descriptive name (3-6 words)
2. A brief description of what documents in this category contain
3. Key topics or entities that define this category

Focus on:
- Professional projects (consulting, healthcare, research, business)
- Academic work (classes, assignments, research)
- Personal categories if significant (travel, finance, photos)
- Client/stakeholder-based groupings (UCLA Health, Amgen, etc.)

Respond in JSON:
{{
  "themes": [
    {{
      "name": "Project Name",
      "description": "What this project is about",
      "key_topics": ["topic1", "topic2", "topic3"]
    }}
  ]
}}

Be specific and content-based, not generic.
"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,  # Use gpt-4o for better analysis
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" },  # Force JSON response
            temperature=0.3
        )

        content = response.choices[0].message.content
        print(f"\nLLM Response:\n{content[:500]}...")  # Debug output

        result = json.loads(content)
        return result.get('themes', [])

    except Exception as e:
        print(f"⚠ Failed to discover themes: {e}")
        import traceback
        traceback.print_exc()
        return []

def classify_document_to_theme(doc, themes):
    """Use LLM to classify a document into one of the discovered themes"""

    content = doc.get('content', '')[:500]
    file_name = doc.get('metadata', {}).get('file_name', 'Unknown')

    theme_list = "\n".join([
        f"{i+1}. {t['name']}: {t['description']}"
        for i, t in enumerate(themes)
    ])

    prompt = f"""Which project theme does this document belong to?

DOCUMENT ({file_name}):
{content}

AVAILABLE THEMES:
{theme_list}

Respond with just the theme number (1-{len(themes)}), or 0 if none match well.
"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )

        theme_num = int(response.choices[0].message.content.strip())
        if 1 <= theme_num <= len(themes):
            return theme_num - 1
        return None

    except Exception as e:
        return None

def main():
    print("="*70)
    print("PROJECT DISCOVERY: Content-Based Theme Analysis")
    print("="*70)

    # Load all documents
    print("\nLoading documents...")
    all_docs = load_all_documents()

    if not all_docs:
        print("✗ No documents found")
        return

    print(f"✓ Loaded {len(all_docs)} unique documents")

    # Sample for theme discovery
    sample_size = min(100, len(all_docs))
    sample = random.sample(all_docs, sample_size)

    print(f"\nAnalyzing {sample_size} random documents to discover themes...")
    themes = discover_project_themes(sample)

    if not themes:
        print("✗ Could not discover themes")
        return

    print(f"\n✓ Discovered {len(themes)} project themes:")
    for i, theme in enumerate(themes, 1):
        print(f"\n  {i}. {theme['name']}")
        print(f"     {theme['description']}")
        print(f"     Topics: {', '.join(theme['key_topics'])}")

    # Classify a larger sample of documents
    print(f"\nClassifying {min(500, len(all_docs))} documents into themes...")

    theme_docs = defaultdict(list)
    classify_sample = random.sample(all_docs, min(500, len(all_docs)))

    for i, doc in enumerate(classify_sample, 1):
        if i % 50 == 0:
            print(f"  Classified {i}/{len(classify_sample)} documents...")

        theme_idx = classify_document_to_theme(doc, themes)
        if theme_idx is not None:
            theme_docs[theme_idx].append(doc)

    # Create canonical projects
    canonical_projects = {}

    for theme_idx, theme in enumerate(themes):
        docs_in_theme = theme_docs.get(theme_idx, [])

        # Estimate total documents in this theme based on sample
        sample_ratio = len(classify_sample) / len(all_docs)
        estimated_total = int(len(docs_in_theme) / sample_ratio) if sample_ratio > 0 else len(docs_in_theme)

        project_id = f"project_{theme_idx + 1}"
        canonical_projects[project_id] = {
            "id": project_id,
            "name": theme['name'],
            "description": theme['description'],
            "document_count": estimated_total,
            "status": "active",
            "key_topics": theme['key_topics'],
            "sample_doc_count": len(docs_in_theme)
        }

    # Save to file
    output_file = DATA_DIR / "canonical_projects.json"
    with open(output_file, 'w') as f:
        json.dump(canonical_projects, f, indent=2)

    print(f"\n{'='*70}")
    print(f"✓ Discovered {len(canonical_projects)} projects")
    print(f"✓ Saved to {output_file}")
    print(f"{'='*70}")

    # Print summary
    print("\nProject Summary (sorted by estimated size):")
    for proj_id, proj in sorted(canonical_projects.items(), key=lambda x: x[1]['document_count'], reverse=True):
        print(f"\n  {proj['name']}")
        print(f"    Estimated docs: ~{proj['document_count']}")
        print(f"    Sample docs: {proj['sample_doc_count']}")
        print(f"    {proj['description']}")

if __name__ == "__main__":
    main()
