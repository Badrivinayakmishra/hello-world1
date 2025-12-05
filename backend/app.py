import os
"""
KnowledgeVault Web Application
Flask-based frontend for querying the knowledge base
"""

from flask import Flask, render_template, request, jsonify
import json
import pickle
from pathlib import Path
from openai import AzureOpenAI
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

app = Flask(__name__)

# Load configuration
from config.config import Config

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Initialize OpenAI
client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )

# Add custom Jinja2 filter for number formatting
@app.template_filter('format_number')
def format_number(value):
    """Format number with commas for thousands"""
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return value

# Global variables for loaded data
search_index = None
employee_summaries = None
project_metadata = None

def load_data():
    """Load search index and metadata"""
    global search_index, employee_summaries, project_metadata

    print("Loading data...")

    # Load search index
    index_file = Config.DATA_DIR / "search_index.pkl"
    if index_file.exists():
        with open(index_file, 'rb') as f:
            search_index = pickle.load(f)
        print(f"✓ Loaded search index with {len(search_index['doc_ids'])} documents")
    else:
        print("⚠ Search index not found. Run run_full_pipeline.py first.")

    # Load employee summaries
    summaries_file = Config.OUTPUT_DIR / "employee_summaries.json"
    if summaries_file.exists():
        with open(summaries_file, 'r') as f:
            employee_summaries = json.load(f)
        print(f"✓ Loaded {len(employee_summaries)} employee summaries")
    else:
        employee_summaries = {}

    # Load project metadata
    metadata_file = Config.DATA_DIR / "project_clusters" / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            project_metadata = json.load(f)
        print(f"✓ Loaded project metadata for {len(project_metadata)} employees")
    else:
        project_metadata = {}

    print("✓ Data loaded successfully\n")

def search_documents(query, top_k=10):
    """Search documents using TF-IDF similarity"""
    if search_index is None:
        return []

    # Vectorize query
    query_vector = search_index['vectorizer'].transform([query])

    # Compute similarities
    similarities = cosine_similarity(query_vector, search_index['doc_vectors'])[0]

    # Get top-k
    top_indices = similarities.argsort()[-top_k:][::-1]

    results = []
    for idx in top_indices:
        if similarities[idx] > 0:  # Only include non-zero similarities
            doc_id = search_index['doc_ids'][idx]
            doc = search_index['doc_index'][doc_id]
            results.append({
                'doc_id': doc_id,
                'subject': doc['metadata'].get('subject', 'No subject'),
                'employee': doc['metadata'].get('employee', 'Unknown'),
                'timestamp': doc['metadata'].get('timestamp', ''),
                'content': doc['content'][:500],
                'score': float(similarities[idx]),
                'cluster': doc.get('cluster_label', 'unknown')
            })

    return results

def generate_answer(query, search_results):
    """Generate answer using RAG"""
    if not search_results:
        return "I couldn't find any relevant documents to answer your question."

    # Build context
    context_parts = []
    for i, result in enumerate(search_results[:5], 1):
        context_parts.append(
            f"[Document {i}]\n"
            f"From: {result['employee']}\n"
            f"Subject: {result['subject']}\n"
            f"Date: {result['timestamp']}\n"
            f"Content: {result['content']}\n"
        )

    context = "\n\n".join(context_parts)

    # Generate answer
    prompt = f"""Using the following documents from Enron's email archive, answer the user's question.

Provide a comprehensive answer based on the information in the documents. Include specific details and cite document numbers.

Documents:
{context}

Question: {query}

Answer:"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant analyzing Enron email data. Provide factual answers based on the provided documents and cite your sources."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=500
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating answer: {str(e)}"

@app.route('/')
def index():
    """Home page"""
    stats = {
        'total_documents': len(search_index['doc_ids']) if search_index else 0,
        'total_employees': len(employee_summaries) if employee_summaries else 0,
        'total_projects': sum(len(p) for p in project_metadata.values()) if project_metadata else 0
    }
    return render_template('index.html', stats=stats)

@app.route('/api/search', methods=['POST'])
def api_search():
    """Search API endpoint"""
    data = request.get_json()
    query = data.get('query', '')

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    # Search documents
    results = search_documents(query, top_k=10)

    # Generate answer
    answer = generate_answer(query, results)

    return jsonify({
        'query': query,
        'answer': answer,
        'sources': results,
        'num_sources': len(results)
    })

@app.route('/api/employees')
def api_employees():
    """Get all employees"""
    employees = []
    for emp, data in (employee_summaries or {}).items():
        employees.append({
            'name': emp,
            'summary': data.get('summary', ''),
            'total_emails': data.get('total_emails', 0),
            'projects': data.get('projects', 0)
        })

    # Sort by email count
    employees.sort(key=lambda x: x['total_emails'], reverse=True)

    return jsonify({'employees': employees})

@app.route('/api/employee/<employee_name>')
def api_employee_detail(employee_name):
    """Get employee details"""
    if employee_name not in (employee_summaries or {}):
        return jsonify({'error': 'Employee not found'}), 404

    summary_data = employee_summaries[employee_name]
    projects = project_metadata.get(employee_name, {})

    # Get sample documents
    sample_docs = []
    for proj_id, proj_data in list(projects.items())[:3]:
        proj_file = Path(proj_data['file'])
        if proj_file.exists():
            with open(proj_file, 'r') as f:
                for i, line in enumerate(f):
                    if i >= 3:  # Max 3 docs per project
                        break
                    doc = json.loads(line)
                    sample_docs.append({
                        'subject': doc['metadata'].get('subject', ''),
                        'timestamp': doc['metadata'].get('timestamp', ''),
                        'project': proj_id
                    })

    return jsonify({
        'name': employee_name,
        'summary': summary_data.get('summary', ''),
        'total_emails': summary_data.get('total_emails', 0),
        'num_projects': len(projects),
        'projects': list(projects.keys()),
        'sample_documents': sample_docs
    })

@app.route('/api/stats')
def api_stats():
    """Get system statistics"""
    return jsonify({
        'total_documents': len(search_index['doc_ids']) if search_index else 0,
        'total_employees': len(employee_summaries) if employee_summaries else 0,
        'total_projects': sum(len(p) for p in project_metadata.values()) if project_metadata else 0,
        'index_features': search_index['doc_vectors'].shape[1] if search_index else 0
    })

if __name__ == '__main__':
    print("="*80)
    print("KNOWLEDGEVAULT WEB APPLICATION")
    print("="*80)

    # Load data
    load_data()

    print("="*80)
    print("Starting web server...")
    print("="*80)
    print("\n🌐 Open your browser to: http://localhost:5001")
    print("\nPress Ctrl+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=5001)
