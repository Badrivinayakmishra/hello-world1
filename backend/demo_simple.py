import os
"""
Simplified KnowledgeVault Demo
Works without BERTopic/HDBSCAN/ChromaDB (Python 3.14 compatible)
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from config.config import Config
from openai import AzureOpenAI

print("="*80)
print("KNOWLEDGEVAULT SIMPLIFIED DEMO")
print("="*80)
print("\nThis demo shows the core functionality without packages")
print("that don't support Python 3.14 yet (BERTopic, HDBSCAN, ChromaDB)")
print("="*80 + "\n")

# Step 1: Parse some emails
print("STEP 1: Parsing Enron Emails")
print("-"*80)

from data_processing.enron_parser import EnronParser

parser = EnronParser(Config.ENRON_MAILDIR)
emails = parser.parse_all_emails(
    output_path=str(Config.DATA_DIR / "unclustered" / "demo_emails.jsonl"),
    limit=50  # Just 50 emails for demo
)

stats = parser.get_statistics()
print(f"\n✓ Parsed {stats['total_emails']} emails")
print(f"✓ Found {stats['unique_employees']} unique employees")
print(f"\nTop 5 employees:")
sorted_emp = sorted(stats['emails_per_employee'].items(), key=lambda x: x[1], reverse=True)[:5]
for emp, count in sorted_emp:
    print(f"  - {emp}: {count} emails")

# Step 2: Cluster by employee
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
clusterer.save_employee_clusters(str(Config.DATA_DIR / "employee_clusters_demo"))

print(f"\n✓ Created {len(clusterer.employee_clusters)} employee clusters")

# Step 3: Simple project clustering (keyword-based instead of BERTopic)
print("\n" + "="*80)
print("STEP 3: Simple Project Clustering (Keyword-Based)")
print("-"*80)

def simple_project_clustering(documents):
    """Simple keyword-based clustering as alternative to BERTopic"""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import AgglomerativeClustering
    import numpy as np

    # Extract text
    texts = [doc['content'][:500] for doc in documents]  # First 500 chars

    if len(texts) < 3:
        # Too few documents, single cluster
        for doc in documents:
            doc['cluster_id'] = 'project_0'
            doc['cluster_label'] = 'general'
        return {'project_0': documents}

    # TF-IDF vectorization
    vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
    X = vectorizer.fit_transform(texts)

    # Agglomerative clustering
    n_clusters = min(3, len(documents) // 3)  # Max 3 clusters
    if n_clusters < 2:
        n_clusters = 1

    clustering = AgglomerativeClustering(n_clusters=n_clusters)
    labels = clustering.fit_predict(X.toarray())

    # Group by cluster
    clusters = defaultdict(list)
    for doc, label in zip(documents, labels):
        doc['cluster_id'] = f'project_{label}'
        doc['cluster_label'] = f'project_{label}'
        clusters[f'project_{label}'].append(doc)

    return dict(clusters)

# Cluster first employee's documents
first_emp = list(clusterer.employee_clusters.keys())[0]
emp_docs = clusterer.employee_clusters[first_emp]

projects = simple_project_clustering(emp_docs)
print(f"\n✓ Clustered {first_emp}'s {len(emp_docs)} documents into {len(projects)} projects")
for proj_id, docs in projects.items():
    print(f"  - {proj_id}: {len(docs)} documents")

# Step 4: Work/Personal Classification
print("\n" + "="*80)
print("STEP 4: Work vs Personal Classification")
print("-"*80)

client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )

# Classify a few documents
sample_docs = emp_docs[:3]
classifications = []

for i, doc in enumerate(sample_docs, 1):
    subject = doc['metadata'].get('subject', '')[:100]
    content = doc['content'][:300]

    prompt = f"""Classify this email as WORK or PERSONAL.

Subject: {subject}
Content: {content}

Respond with just: {{"category": "work" or "personal", "confidence": 0.0-1.0}}"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=50
        )

        result = response.choices[0].message.content.strip()
        # Parse JSON
        if '{' in result:
            start = result.index('{')
            end = result.rindex('}') + 1
            classification = json.loads(result[start:end])
            classifications.append(classification)
            print(f"  Email {i}: {classification['category'].upper()} (confidence: {classification['confidence']})")
    except Exception as e:
        print(f"  Email {i}: Error - {e}")

print(f"\n✓ Classified {len(classifications)} emails")

# Step 5: Gap Analysis
print("\n" + "="*80)
print("STEP 5: Gap Analysis")
print("-"*80)

gap_prompt = f"""Analyze this project's documentation and identify knowledge gaps.

Employee: {first_emp}
Total Documents: {len(emp_docs)}
Sample Subjects:
{chr(10).join(f"- {doc['metadata'].get('subject', 'No subject')[:80]}" for doc in emp_docs[:10])}

What critical information is missing? Generate 3 specific questions to fill gaps.

Respond as JSON: {{"gaps": [...], "questions": [...]}}"""

try:
    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[{"role": "user", "content": gap_prompt}],
        temperature=0.3,
        max_tokens=500
    )

    result = response.choices[0].message.content.strip()
    if '{' in result:
        start = result.index('{')
        end = result.rindex('}') + 1
        gaps = json.loads(result[start:end])

        print("\nIdentified Gaps:")
        for gap in gaps.get('gaps', [])[:3]:
            print(f"  - {gap}")

        print("\nGenerated Questions:")
        for q in gaps.get('questions', [])[:3]:
            print(f"  ? {q}")

        print(f"\n✓ Generated {len(gaps.get('questions', []))} questions")
except Exception as e:
    print(f"✗ Gap analysis failed: {e}")

# Step 6: Simple RAG Query (without vector DB)
print("\n" + "="*80)
print("STEP 6: Simple RAG Query (Keyword-Based)")
print("-"*80)

def simple_search(query, documents, top_k=3):
    """Simple keyword-based search instead of vector search"""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    # All document texts
    doc_texts = [doc['content'][:1000] for doc in documents]

    # Vectorize
    vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
    doc_vectors = vectorizer.fit_transform(doc_texts)
    query_vector = vectorizer.transform([query])

    # Compute similarity
    similarities = cosine_similarity(query_vector, doc_vectors)[0]

    # Get top-k
    top_indices = similarities.argsort()[-top_k:][::-1]

    results = []
    for idx in top_indices:
        results.append({
            'doc': documents[idx],
            'score': similarities[idx]
        })

    return results

# Test query
test_query = "What projects were discussed in these emails?"
print(f"\nQuery: {test_query}")
print("-"*80)

search_results = simple_search(test_query, emp_docs, top_k=3)

# Build context
context = "\n\n".join([
    f"[Doc {i+1}] Subject: {r['doc']['metadata'].get('subject', 'No subject')}\n"
    f"Content: {r['doc']['content'][:300]}..."
    for i, r in enumerate(search_results)
])

# Generate answer
rag_prompt = f"""Using these documents, answer the question.

Documents:
{context}

Question: {test_query}

Provide a brief answer:"""

try:
    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[{"role": "user", "content": rag_prompt}],
        temperature=0.3,
        max_tokens=200
    )

    answer = response.choices[0].message.content.strip()
    print(f"\nAnswer:\n{answer}")

    print(f"\nSources ({len(search_results)}):")
    for i, r in enumerate(search_results, 1):
        print(f"  {i}. {r['doc']['metadata'].get('subject', 'No subject')[:60]} (score: {r['score']:.3f})")

    print(f"\n✓ RAG query completed successfully!")
except Exception as e:
    print(f"✗ RAG query failed: {e}")

# Final Summary
print("\n" + "="*80)
print("DEMO COMPLETE!")
print("="*80)
print("\n✅ Successfully demonstrated:")
print("  1. ✓ Email parsing (50 documents)")
print("  2. ✓ Employee clustering")
print("  3. ✓ Simple project clustering (TF-IDF + Agglomerative)")
print("  4. ✓ Work/Personal classification (GPT-4o-mini)")
print("  5. ✓ Gap analysis and question generation")
print("  6. ✓ Simple RAG query system (TF-IDF + GPT-4o-mini)")
print("\n⚠️  Note: This demo uses simplified algorithms due to Python 3.14")
print("    For full BERTopic clustering, use Python 3.10-3.13")
print("\n📊 Check outputs in:")
print(f"    {Config.DATA_DIR}")
print("="*80)
