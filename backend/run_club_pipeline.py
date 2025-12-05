"""
Universal KnowledgeVault Pipeline for ANY Company/Organization
Works with Google Chat Takeout data, emails, documents, etc.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
import numpy as np
from tqdm import tqdm
from openai import AzureOpenAI

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Configuration for Club Data
CLUB_DATA_DIR = Path("/Users/rishitjain/Downloads/Takeout")
OUTPUT_DIR = Path("/Users/rishitjain/Downloads/knowledgevault_backend/club_data")
OUTPUT_DIR.mkdir(exist_ok=True)

# Subdirectories
UNCLUSTERED_DIR = OUTPUT_DIR / "unclustered"
EMPLOYEE_CLUSTERS_DIR = OUTPUT_DIR / "employee_clusters"
PROJECT_CLUSTERS_DIR = OUTPUT_DIR / "project_clusters"
SEARCH_INDEX_FILE = OUTPUT_DIR / "search_index.pkl"
SUMMARIES_FILE = OUTPUT_DIR / "employee_summaries.json"

for dir in [UNCLUSTERED_DIR, EMPLOYEE_CLUSTERS_DIR, PROJECT_CLUSTERS_DIR]:
    dir.mkdir(exist_ok=True)

# OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "os.getenv("OPENAI_API_KEY", "")")


def parse_google_chat_messages(messages_file, group_name):
    """Parse Google Chat messages.json file"""
    documents = []

    try:
        with open(messages_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        messages = data.get('messages', [])

        for i, msg in enumerate(messages):
            creator = msg.get('creator', {})
            employee_name = creator.get('name', 'Unknown')
            employee_email = creator.get('email', '')

            # Extract email username as employee ID
            employee_id = employee_email.split('@')[0] if employee_email else employee_name.lower().replace(' ', '-')

            text = msg.get('text', '')
            created_date = msg.get('created_date', '')

            # Skip empty messages
            if not text or text.strip() == '':
                continue

            doc_id = f"{group_name}_{msg.get('message_id', i)}"

            documents.append({
                'doc_id': doc_id,
                'content': text,
                'metadata': {
                    'employee': employee_id,
                    'employee_name': employee_name,
                    'employee_email': employee_email,
                    'group': group_name,
                    'timestamp': created_date,
                    'source_type': 'google_chat'
                },
                'source_hyperlink': f"Google Chat - {group_name}"
            })

    except Exception as e:
        print(f"  Error parsing {messages_file}: {e}")

    return documents


def scan_all_chat_data():
    """Scan all Google Chat data"""
    print("="*80)
    print("STEP 1: Parsing All Google Chat Messages")
    print("-"*80)

    all_documents = []

    # Scan Groups
    groups_dir = CLUB_DATA_DIR / "Google Chat" / "Groups"

    if groups_dir.exists():
        group_folders = [f for f in groups_dir.iterdir() if f.is_dir()]

        print(f"Found {len(group_folders)} chat groups/spaces")

        for group_folder in tqdm(group_folders, desc="Processing groups"):
            group_name = group_folder.name
            messages_file = group_folder / "messages.json"

            if messages_file.exists():
                docs = parse_google_chat_messages(messages_file, group_name)
                all_documents.extend(docs)

    print(f"\n✓ Parsed {len(all_documents)} total messages")

    # Save unclustered
    unclustered_file = UNCLUSTERED_DIR / "all_messages.jsonl"
    with open(unclustered_file, 'w', encoding='utf-8') as f:
        for doc in all_documents:
            f.write(json.dumps(doc) + '\n')

    print(f"✓ Saved to {unclustered_file}")

    return all_documents


def cluster_by_employee(documents):
    """Cluster documents by employee"""
    print("\n" + "="*80)
    print("STEP 2: Clustering by Employee")
    print("-"*80)

    employee_clusters = defaultdict(list)

    for doc in documents:
        employee = doc['metadata']['employee']
        employee_clusters[employee].append(doc)

    print(f"Found {len(employee_clusters)} unique employees")

    # Save employee clusters
    for employee, docs in employee_clusters.items():
        employee_file = EMPLOYEE_CLUSTERS_DIR / f"{employee}.jsonl"
        with open(employee_file, 'w', encoding='utf-8') as f:
            for doc in docs:
                f.write(json.dumps(doc) + '\n')

        print(f"  {employee}: {len(docs)} messages")

    return employee_clusters


def cluster_projects_simple(employee, documents):
    """Simple project clustering using TF-IDF + Agglomerative Clustering"""
    if len(documents) < 5:
        # Too few documents, treat as one project
        return {'project_0': documents}

    # Extract text
    texts = [doc['content'][:1000] for doc in documents]

    # TF-IDF vectorization
    vectorizer = TfidfVectorizer(max_features=100, stop_words='english', max_df=0.8, min_df=2)

    try:
        X = vectorizer.fit_transform(texts)
    except:
        # If TF-IDF fails (e.g., all stopwords), return single project
        return {'project_0': documents}

    # Determine number of clusters (max 5, or 1 cluster per 10 documents)
    n_clusters = min(5, max(2, len(documents) // 10))

    # Agglomerative clustering
    try:
        clustering = AgglomerativeClustering(n_clusters=n_clusters, metric='euclidean', linkage='ward')
        labels = clustering.fit_predict(X.toarray())
    except:
        # If clustering fails, return single project
        return {'project_0': documents}

    # Group by cluster
    projects = defaultdict(list)
    for doc, label in zip(documents, labels):
        projects[f'project_{label}'].append(doc)

    return dict(projects)


def create_project_clusters(employee_clusters):
    """Create project clusters for each employee"""
    print("\n" + "="*80)
    print("STEP 3: Clustering by Project")
    print("-"*80)

    project_metadata = {}

    for employee, docs in tqdm(employee_clusters.items(), desc="Clustering projects"):
        # Cluster projects
        projects = cluster_projects_simple(employee, docs)

        # Save projects
        employee_project_dir = PROJECT_CLUSTERS_DIR / employee
        employee_project_dir.mkdir(exist_ok=True)

        project_metadata[employee] = {}

        for project_id, project_docs in projects.items():
            project_file = employee_project_dir / f"{project_id}.jsonl"

            with open(project_file, 'w', encoding='utf-8') as f:
                for doc in project_docs:
                    f.write(json.dumps(doc) + '\n')

            project_metadata[employee][project_id] = {
                'document_count': len(project_docs),
                'file': str(project_file)
            }

    # Save metadata
    metadata_file = PROJECT_CLUSTERS_DIR / "metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(project_metadata, f, indent=2)

    total_projects = sum(len(p) for p in project_metadata.values())
    print(f"\n✓ Created {total_projects} project clusters across {len(project_metadata)} employees")

    return project_metadata


def build_search_index(all_documents):
    """Build TF-IDF search index"""
    print("\n" + "="*80)
    print("STEP 4: Building Search Index")
    print("-"*80)

    # Extract texts
    texts = [doc['content'] for doc in all_documents]

    # Build TF-IDF vectorizer
    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words='english',
        ngram_range=(1, 2),
        max_df=0.85,
        min_df=2
    )

    doc_vectors = vectorizer.fit_transform(texts)

    # Create document index
    doc_index = {doc['doc_id']: doc for doc in all_documents}

    # Save index
    index_data = {
        'vectorizer': vectorizer,
        'doc_vectors': doc_vectors,
        'doc_ids': [doc['doc_id'] for doc in all_documents],
        'doc_index': doc_index
    }

    with open(SEARCH_INDEX_FILE, 'wb') as f:
        pickle.dump(index_data, f)

    print(f"✓ Indexed {len(all_documents)} documents")
    print(f"✓ Saved to {SEARCH_INDEX_FILE}")

    return index_data


def generate_employee_summaries(employee_clusters, project_metadata):
    """Generate AI summaries for each employee"""
    print("\n" + "="*80)
    print("STEP 5: Generating Employee Summaries")
    print("-"*80)

    client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
    employee_summaries = {}

    for employee, docs in tqdm(employee_clusters.items(), desc="Generating summaries"):
        # Sample messages
        sample_messages = [doc['content'][:200] for doc in docs[:20]]
        messages_text = '\n'.join(f"- {msg}" for msg in sample_messages if msg.strip())

        prompt = f"""Analyze this person's chat messages and provide a brief summary.

Person: {employee}
Total messages: {len(docs)}
Sample messages:
{messages_text}

Provide a 2-3 sentence summary of their main activities, responsibilities, and contributions based on the messages.
Be specific and factual."""

        try:
            response = client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150
            )

            summary = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"\n  Error for {employee}: {e}")
            summary = f"Member with {len(docs)} messages"

        employee_summaries[employee] = {
            'summary': summary,
            'total_messages': len(docs),
            'projects': len(project_metadata.get(employee, {}))
        }

    # Save summaries
    with open(SUMMARIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(employee_summaries, f, indent=2)

    print(f"\n✓ Generated {len(employee_summaries)} employee summaries")
    print(f"✓ Saved to {SUMMARIES_FILE}")

    return employee_summaries


def main():
    """Run the complete pipeline"""
    print("="*80)
    print("UNIVERSAL KNOWLEDGEVAULT PIPELINE")
    print("Processing Club/Organization Data")
    print("="*80)

    # Step 1: Parse all messages
    all_documents = scan_all_chat_data()

    # Step 2: Cluster by employee
    employee_clusters = cluster_by_employee(all_documents)

    # Step 3: Cluster by project
    project_metadata = create_project_clusters(employee_clusters)

    # Step 4: Build search index
    search_index = build_search_index(all_documents)

    # Step 5: Generate employee summaries
    employee_summaries = generate_employee_summaries(employee_clusters, project_metadata)

    # Final stats
    print("\n" + "="*80)
    print("PIPELINE COMPLETE!")
    print("="*80)
    print(f"\nTotal Documents: {len(all_documents):,}")
    print(f"Total Employees: {len(employee_clusters)}")
    print(f"Total Projects: {sum(len(p) for p in project_metadata.values())}")
    print(f"\nData saved to: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
