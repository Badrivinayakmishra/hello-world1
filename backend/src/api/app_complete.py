import os
"""
Complete KnowledgeVault Web Application
Shows all methodology results in the frontend
"""

from flask import Flask, render_template, request, jsonify
import json
import pickle
from pathlib import Path
from openai import AzureOpenAI
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from config.config import Config
from gap_analysis.gap_analyzer import GapAnalyzer

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


app = Flask(__name__)

# Use club_data directory for stakeholder data
CLUB_DATA_DIR = Path(__file__).parent / "club_data"

# Initialize OpenAI
client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )

# Global variables
search_index = None
employee_summaries = None
project_metadata = None
gap_analysis_cache = {}
stakeholder_graph = None

# Add custom Jinja2 filter
@app.template_filter('format_number')
def format_number(value):
    """Format number with commas"""
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return value

def load_data():
    """Load all data"""
    global search_index, employee_summaries, project_metadata, stakeholder_graph

    print("Loading data...")

    # Load search index
    index_file = Config.DATA_DIR / "search_index.pkl"
    if index_file.exists():
        with open(index_file, 'rb') as f:
            search_index = pickle.load(f)
        print(f"✓ Loaded search index with {len(search_index['doc_ids'])} documents")

    # Load employee summaries
    summaries_file = Config.OUTPUT_DIR / "employee_summaries.json"
    if summaries_file.exists():
        with open(summaries_file, 'r') as f:
            employee_summaries = json.load(f)
        print(f"✓ Loaded {len(employee_summaries)} employee summaries")

    # Load project metadata
    metadata_file = Config.DATA_DIR / "project_clusters" / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            project_metadata = json.load(f)
        print(f"✓ Loaded project metadata for {len(project_metadata)} employees")

    # Load stakeholder graph from club_data
    try:
        from rag.stakeholder_graph import StakeholderGraph, build_stakeholder_graph
        stakeholder_file = CLUB_DATA_DIR / "stakeholder_graph.pkl"

        # Also load club embedding index for stakeholder data
        club_embedding_file = CLUB_DATA_DIR / "embedding_index.pkl"
        club_chunks = []
        club_doc_index = {}

        if club_embedding_file.exists():
            with open(club_embedding_file, 'rb') as f:
                club_index = pickle.load(f)
            club_chunks = club_index.get('chunks', [])
            # Build doc_index from chunks
            for chunk in club_chunks:
                doc_id = chunk.get('doc_id', '')
                if doc_id and doc_id not in club_doc_index:
                    club_doc_index[doc_id] = {
                        'content': chunk.get('content', ''),
                        'metadata': chunk.get('metadata', {})
                    }
            print(f"✓ Loaded club embedding index ({len(club_chunks)} chunks)")

        # Get doc_index from the embedding file directly
        club_doc_index = club_index.get('doc_index', {})

        if stakeholder_file.exists():
            stakeholder_graph = StakeholderGraph.load(stakeholder_file)
            print(f"✓ Stakeholder graph loaded ({stakeholder_graph.get_stats()['total_people']} people)")
        elif club_doc_index:
            # Build from club data if not cached
            stakeholder_graph = build_stakeholder_graph(club_chunks, club_doc_index)
            stakeholder_graph.save(stakeholder_file)
            print(f"✓ Stakeholder graph built ({stakeholder_graph.get_stats()['total_people']} people)")
        else:
            stakeholder_graph = StakeholderGraph()
            print("⚠ Stakeholder graph empty - no club documents to process")
    except Exception as e:
        import traceback
        print(f"⚠ Stakeholder graph not loaded: {e}")
        traceback.print_exc()
        stakeholder_graph = None

    print("✓ Data loaded successfully\n")

def search_documents(query, top_k=20):
    """Search documents using TF-IDF"""
    if search_index is None:
        return []

    query_vector = search_index['vectorizer'].transform([query])
    similarities = cosine_similarity(query_vector, search_index['doc_vectors'])[0]
    top_indices = similarities.argsort()[-top_k:][::-1]

    results = []
    for idx in top_indices:
        if similarities[idx] > 0:
            doc_id = search_index['doc_ids'][idx]
            doc = search_index['doc_index'][doc_id]
            results.append({
                'doc_id': doc_id,
                'subject': doc['metadata'].get('subject', 'No subject'),
                'employee': doc['metadata'].get('employee', 'Unknown'),
                'timestamp': doc['metadata'].get('timestamp', ''),
                'content': doc['content'][:2000],  # Increased from 500 to 2000
                'full_content': doc['content'],
                'score': float(similarities[idx]),
                'cluster': doc.get('cluster_label', 'unknown')
            })

    return results

def generate_answer(query, search_results):
    """Generate answer using RAG"""
    if not search_results:
        return "I couldn't find any relevant documents to answer your question."

    # Use top 10 results instead of 5
    context_parts = []
    for i, result in enumerate(search_results[:10], 1):
        # Format timestamp nicely
        timestamp = result['timestamp']
        if timestamp:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime('%Y-%m-%d')
            except:
                timestamp = str(timestamp)[:10]

        context_parts.append(
            f"[Document {i}] (Relevance: {result['score']:.2%})\n"
            f"From: {result['employee']}\n"
            f"Date: {timestamp}\n"
            f"Subject: {result['subject']}\n"
            f"Content: {result['full_content'][:1500]}\n"  # Use more context
        )

    context = "\n---\n".join(context_parts)

    prompt = f"""You are analyzing Enron email data to answer questions about the company's operations, projects, and employee activities.

Based on the email documents below, provide a comprehensive and detailed answer to the user's question.

IMPORTANT INSTRUCTIONS:
1. Provide specific details from the documents
2. Cite document numbers when referencing information (e.g., "According to Document 1...")
3. If documents discuss multiple aspects, organize your answer with clear sections
4. Include relevant names, dates, and numbers from the emails
5. If the documents don't fully answer the question, state what information is available and what's missing
6. Be factual and avoid speculation

EMAIL DOCUMENTS:
{context}

USER QUESTION: {query}

COMPREHENSIVE ANSWER:"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert analyst with deep knowledge of Enron's operations. You provide detailed, well-structured answers based on email evidence. You always cite your sources using document numbers."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,  # Lower temperature for more factual responses
            max_tokens=1500   # Increased for longer, detailed answers
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
    return render_template('index_complete.html', stats=stats)

@app.route('/api/search', methods=['POST'])
def api_search():
    """Search API"""
    data = request.get_json()
    query = data.get('query', '')

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    results = search_documents(query, top_k=10)
    answer = generate_answer(query, results)

    return jsonify({
        'query': query,
        'answer': answer,
        'sources': results,
        'num_sources': len(results)
    })

@app.route('/api/employees')
def api_employees():
    """Get all employees with summaries"""
    employees = []
    for emp, data in (employee_summaries or {}).items():
        employees.append({
            'name': emp,
            'summary': data.get('summary', ''),
            'total_emails': data.get('total_emails', 0),
            'projects': data.get('projects', 0)
        })

    employees.sort(key=lambda x: x['total_emails'], reverse=True)
    return jsonify({'employees': employees})

@app.route('/api/projects')
def api_projects():
    """Get all project clusters"""
    if not project_metadata:
        return jsonify({'projects': []})

    projects_list = []
    for employee, projects in list(project_metadata.items())[:20]:  # Top 20 employees
        for project_id, project_info in projects.items():
            projects_list.append({
                'employee': employee,
                'project_id': project_id,
                'document_count': project_info['document_count'],
                'file': project_info['file']
            })

    return jsonify({'projects': projects_list})

@app.route('/api/employee/<employee_name>/gaps')
def api_employee_gaps(employee_name):
    """Get gap analysis for an employee"""

    # Check cache
    if employee_name in gap_analysis_cache:
        return jsonify(gap_analysis_cache[employee_name])

    # Load employee documents
    employee_file = Config.DATA_DIR / "employee_clusters" / f"{employee_name}.jsonl"

    if not employee_file.exists():
        return jsonify({'error': 'Employee not found'}), 404

    # Load sample documents
    documents = []
    with open(employee_file, 'r') as f:
        for i, line in enumerate(f):
            if i >= 30:  # Sample 30
                break
            documents.append(json.loads(line))

    # Run gap analysis
    analyzer = GapAnalyzer(api_key=Config.OPENAI_API_KEY)

    project_data = {
        'project_name': f'{employee_name}_overview',
        'documents': documents
    }

    gaps = analyzer.analyze_project_gaps(project_data)

    # Cache result
    gap_analysis_cache[employee_name] = gaps

    return jsonify(gaps)

@app.route('/api/stats')
def api_stats():
    """Get system statistics"""
    return jsonify({
        'total_documents': len(search_index['doc_ids']) if search_index else 0,
        'total_employees': len(employee_summaries) if employee_summaries else 0,
        'total_projects': sum(len(p) for p in project_metadata.values()) if project_metadata else 0,
        'index_features': search_index['doc_vectors'].shape[1] if search_index else 0
    })

# ============================================================================
# Stakeholder Graph Endpoints
# ============================================================================

@app.route('/api/stakeholders')
def api_stakeholders():
    """Get all stakeholders (people) from the graph"""
    global stakeholder_graph
    if stakeholder_graph is None:
        return jsonify({'error': 'Stakeholder graph not loaded', 'people': [], 'total': 0})

    people_list = []
    for name, person in stakeholder_graph.people.items():
        people_list.append({
            'name': person.name,
            'roles': list(person.roles),
            'expertise': list(person.expertise),
            'projects': list(person.projects),
            'documents': len(person.documents),
            'mentions': person.mentions,
            'email': person.email
        })

    # Sort by mentions (most mentioned first)
    people_list.sort(key=lambda x: x['mentions'], reverse=True)

    return jsonify({
        'people': people_list,
        'stats': stakeholder_graph.get_stats(),
        'total': len(people_list)
    })


@app.route('/api/stakeholders/projects')
def api_stakeholder_projects():
    """Get all projects with their team members"""
    global stakeholder_graph
    if stakeholder_graph is None:
        return jsonify({'projects': [], 'total': 0})

    projects_list = []
    for name, project in stakeholder_graph.projects.items():
        # Get team member names
        team = []
        for member_name in project.members:
            if member_name in stakeholder_graph.people:
                person = stakeholder_graph.people[member_name]
                team.append({
                    'name': person.name,
                    'roles': list(person.roles),
                    'expertise': list(person.expertise)
                })

        projects_list.append({
            'name': project.name,
            'team': team,
            'topics': list(project.topics),
            'documents': len(project.documents),
            'status': project.status,
            'client': project.client
        })

    # Sort by number of team members
    projects_list.sort(key=lambda x: len(x['team']), reverse=True)

    return jsonify({
        'projects': projects_list,
        'total': len(projects_list)
    })


@app.route('/api/stakeholders/query', methods=['POST'])
def api_stakeholder_query():
    """Answer 'who' questions using the stakeholder graph"""
    global stakeholder_graph
    data = request.get_json()
    question = data.get('question', '')

    if not question:
        return jsonify({'error': 'No question provided'}), 400

    if stakeholder_graph is None:
        return jsonify({'error': 'Stakeholder graph not loaded', 'results': []})

    result = stakeholder_graph.answer_who_question(question)

    # Format a natural language answer
    answer_text = ""
    if result['answer_type'] == 'project_team':
        if result['results']:
            names = [r['name'] for r in result['results']]
            answer_text = f"The team for {result.get('project', 'this project')} includes: {', '.join(names)}"
        else:
            answer_text = f"No team members found for {result.get('project', 'this project')}"

    elif result['answer_type'] == 'domain_experts':
        if result['results']:
            experts = []
            for r in result['results']:
                exp_str = f"{r['name']}"
                if r['roles']:
                    exp_str += f" ({', '.join(r['roles'][:2])})"
                experts.append(exp_str)
            answer_text = f"People with expertise in {result.get('domain', 'this area')}: {', '.join(experts)}"
        else:
            answer_text = f"No experts found for {result.get('domain', 'this area')}"

    elif result['answer_type'] == 'person_info':
        if result['results']:
            r = result['results'][0]
            answer_text = f"{r['name']}"
            if r['roles']:
                answer_text += f" is a {', '.join(r['roles'])}"
            if r['expertise']:
                answer_text += f" with expertise in {', '.join(r['expertise'])}"
            if r['projects']:
                answer_text += f". Projects: {', '.join(list(r['projects'])[:3])}"
        else:
            answer_text = "Person not found in the knowledge base"

    return jsonify({
        'question': question,
        'answer': answer_text,
        'details': result
    })


if __name__ == '__main__':
    print("="*80)
    print("KNOWLEDGEVAULT - COMPLETE WEB APPLICATION")
    print("="*80)

    load_data()

    print("="*80)
    print("Starting web server...")
    print("="*80)
    print("\n🌐 Open your browser to: http://localhost:5001")
    print("\nPress Ctrl+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
