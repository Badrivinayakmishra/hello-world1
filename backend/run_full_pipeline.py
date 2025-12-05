import os
"""
Full Pipeline for All Enron Data
Python 3.14 compatible version
"""

import sys
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import pickle

sys.path.insert(0, str(Path(__file__).parent))

from config.config import Config
from openai import AzureOpenAI
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

print("="*80)
print("KNOWLEDGEVAULT - FULL PIPELINE")
print("Processing ALL Enron Data")
print("="*80)
print(f"Started: {datetime.now()}")
print("="*80 + "\n")

start_time = datetime.now()

# Step 1: Parse ALL emails
print("STEP 1: Parsing ALL Enron Emails")
print("-"*80)

from data_processing.enron_parser import EnronParser

parser = EnronParser(Config.ENRON_MAILDIR)
emails = parser.parse_all_emails(
    output_path=str(Config.DATA_DIR / "unclustered" / "all_enron_emails.jsonl"),
    limit=None  # Process ALL emails
)

stats = parser.get_statistics()
print(f"\n✓ Parsed {stats['total_emails']} emails")
print(f"✓ Found {stats['unique_employees']} unique employees")

# Step 2: Employee Clustering
print("\n" + "="*80)
print("STEP 2: Clustering by Employee")
print("-"*80)

from clustering.employee_clustering import EmployeeClusterer

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


clusterer = EmployeeClusterer()
clusterer.cluster_by_employee(emails)
clusterer.save_employee_clusters(str(Config.DATA_DIR / "employee_clusters"))
clusterer.generate_statistics()
clusterer.print_statistics()

# Step 3: Project Clustering for each employee
print("\n" + "="*80)
print("STEP 3: Project Clustering (All Employees)")
print("-"*80)

def cluster_projects_simple(documents, n_clusters=None):
    """Simple project clustering using TF-IDF + Agglomerative"""
    if len(documents) < 3:
        for doc in documents:
            doc['cluster_id'] = 'project_0'
            doc['cluster_label'] = 'general'
        return {'project_0': documents}

    # Extract text
    texts = [doc['content'][:1000] for doc in documents]

    # TF-IDF
    vectorizer = TfidfVectorizer(max_features=200, stop_words='english', max_df=0.8)
    try:
        X = vectorizer.fit_transform(texts)
    except:
        # If TF-IDF fails, single cluster
        for doc in documents:
            doc['cluster_id'] = 'project_0'
            doc['cluster_label'] = 'general'
        return {'project_0': documents}

    # Auto-determine clusters
    if n_clusters is None:
        n_clusters = min(5, max(2, len(documents) // 20))

    clustering = AgglomerativeClustering(n_clusters=n_clusters)
    labels = clustering.fit_predict(X.toarray())

    # Group by cluster
    clusters = defaultdict(list)
    for doc, label in zip(documents, labels):
        doc['cluster_id'] = f'project_{label}'
        doc['cluster_label'] = f'project_{label}'
        clusters[f'project_{label}'].append(doc)

    return dict(clusters)

# Process each employee
project_metadata = {}
for employee, emp_docs in clusterer.employee_clusters.items():
    if len(emp_docs) < 5:
        continue  # Skip employees with too few documents

    print(f"  Clustering {employee} ({len(emp_docs)} docs)...")

    projects = cluster_projects_simple(emp_docs)

    # Save projects
    emp_dir = Config.DATA_DIR / "project_clusters" / employee
    emp_dir.mkdir(parents=True, exist_ok=True)

    project_metadata[employee] = {}

    for proj_id, proj_docs in projects.items():
        # Save project JSONL
        proj_file = emp_dir / f"{proj_id}.jsonl"
        with open(proj_file, 'w', encoding='utf-8') as f:
            for doc in proj_docs:
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')

        project_metadata[employee][proj_id] = {
            'document_count': len(proj_docs),
            'file': str(proj_file)
        }

    print(f"    ✓ Created {len(projects)} projects")

# Save project metadata
metadata_file = Config.DATA_DIR / "project_clusters" / "metadata.json"
with open(metadata_file, 'w', encoding='utf-8') as f:
    json.dump(project_metadata, f, indent=2)

print(f"\n✓ Clustered projects for {len(project_metadata)} employees")

# Step 4: Build search index
print("\n" + "="*80)
print("STEP 4: Building Search Index")
print("-"*80)

# Create master search index
all_docs = []
doc_index = {}

for employee, projects in project_metadata.items():
    for project_id, proj_meta in projects.items():
        proj_file = Path(proj_meta['file'])
        with open(proj_file, 'r', encoding='utf-8') as f:
            for line in f:
                doc = json.loads(line)
                all_docs.append(doc)
                doc_index[doc['doc_id']] = doc

print(f"  Indexing {len(all_docs)} documents...")

# Create TF-IDF index
texts = [doc['content'][:1000] for doc in all_docs]
vectorizer = TfidfVectorizer(max_features=500, stop_words='english', max_df=0.7)
doc_vectors = vectorizer.fit_transform(texts)

print(f"  ✓ Created TF-IDF index with {doc_vectors.shape[1]} features")

# Save index
index_data = {
    'vectorizer': vectorizer,
    'doc_vectors': doc_vectors,
    'doc_ids': [doc['doc_id'] for doc in all_docs],
    'doc_index': doc_index
}

index_file = Config.DATA_DIR / "search_index.pkl"
with open(index_file, 'wb') as f:
    pickle.dump(index_data, f)

print(f"  ✓ Saved search index to {index_file}")

# Step 5: Generate employee summaries
print("\n" + "="*80)
print("STEP 5: Generating Employee Summaries")
print("-"*80)

client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )

employee_summaries = {}

# Generate summaries for top 10 employees by document count
top_employees = sorted(
    clusterer.employee_clusters.items(),
    key=lambda x: len(x[1]),
    reverse=True
)[:10]

for employee, emp_docs in top_employees:
    print(f"  Generating summary for {employee}...")

    # Sample subjects
    subjects = [doc['metadata'].get('subject', '')[:100] for doc in emp_docs[:20]]
    subjects_text = '\n'.join(f"- {s}" for s in subjects if s)

    prompt = f"""Analyze this employee's email data and provide a brief summary.

Employee: {employee}
Total emails: {len(emp_docs)}
Sample subjects:
{subjects_text}

Provide a 2-3 sentence summary of their main responsibilities and projects.
Be specific and factual based on the email subjects."""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150
        )

        summary = response.choices[0].message.content.strip()
        employee_summaries[employee] = {
            'summary': summary,
            'total_emails': len(emp_docs),
            'projects': len(project_metadata.get(employee, {}))
        }

        print(f"    ✓ {summary[:80]}...")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        employee_summaries[employee] = {
            'summary': f"Employee with {len(emp_docs)} emails",
            'total_emails': len(emp_docs),
            'projects': len(project_metadata.get(employee, {}))
        }

# Save summaries
summaries_file = Config.OUTPUT_DIR / "employee_summaries.json"
with open(summaries_file, 'w', encoding='utf-8') as f:
    json.dump(employee_summaries, f, indent=2)

print(f"\n✓ Generated {len(employee_summaries)} employee summaries")

# Final Statistics
print("\n" + "="*80)
print("PIPELINE COMPLETE!")
print("="*80)

elapsed = (datetime.now() - start_time).total_seconds()

print(f"\nStatistics:")
print(f"  Total emails: {stats['total_emails']:,}")
print(f"  Total employees: {stats['unique_employees']}")
print(f"  Employees with projects: {len(project_metadata)}")
print(f"  Total projects: {sum(len(p) for p in project_metadata.values())}")
print(f"  Documents indexed: {len(all_docs):,}")
print(f"\nOutput files:")
print(f"  Unclustered data: {Config.DATA_DIR / 'unclustered'}")
print(f"  Employee clusters: {Config.DATA_DIR / 'employee_clusters'}")
print(f"  Project clusters: {Config.DATA_DIR / 'project_clusters'}")
print(f"  Search index: {index_file}")
print(f"  Employee summaries: {summaries_file}")
print(f"\nProcessing time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
print("="*80)

print("\n✅ Ready for frontend! Run: python3 app.py")
