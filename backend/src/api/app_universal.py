"""
KnowledgeVault Universal Web Application
Complete workflow with all steps:
- Step 0: Connect APIs (Gmail, Slack, GitHub)
- Step 1: Filter Messages
- Step 2: Answer Questions
- Step 3: RAG Search
- Step 4: Stakeholder Map
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import pickle
from pathlib import Path
from openai import AzureOpenAI
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend on different port

# Configuration
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "club_data"
TARGET_USER = "rishi2205"

# Load OpenAI API key
import os
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )

# Global variables
search_index = None
embedding_index = None
knowledge_gaps = None
user_spaces = None
kb_metadata = None
enhanced_rag = None
stakeholder_graph = None
connector_manager = None
document_manager = None

# Custom filter
@app.template_filter('format_number')
def format_number(value):
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return value


def load_data():
    """Load the knowledge base for rishi2205"""
    global search_index, embedding_index, knowledge_gaps, user_spaces, kb_metadata, enhanced_rag, stakeholder_graph, connector_manager, document_manager

    print("Loading data...")

    # Load search index
    search_file = DATA_DIR / "search_index.pkl"
    if search_file.exists():
        with open(search_file, 'rb') as f:
            search_index = pickle.load(f)
        print(f"✓ Search index loaded ({len(search_index.get('doc_ids', []))} docs)")

    # Load embedding index
    embedding_file = DATA_DIR / "embedding_index.pkl"
    if embedding_file.exists():
        with open(embedding_file, 'rb') as f:
            embedding_index = pickle.load(f)
        print(f"✓ Embedding index loaded ({len(embedding_index.get('chunks', []))} chunks)")

    # Load knowledge gaps
    gaps_file = DATA_DIR / "knowledge_gaps.json"
    if gaps_file.exists():
        with open(gaps_file, 'r') as f:
            knowledge_gaps = json.load(f)
        print(f"✓ Knowledge gaps loaded ({len(knowledge_gaps)} gaps)")
    else:
        knowledge_gaps = []

    # Load user spaces (projects)
    spaces_file = DATA_DIR / "user_spaces.json"
    if spaces_file.exists():
        with open(spaces_file, 'r') as f:
            user_spaces = json.load(f)
        print(f"✓ User spaces loaded ({len(user_spaces)} spaces)")
    else:
        user_spaces = []

    # Load metadata
    meta_file = DATA_DIR / "knowledge_base_metadata.json"
    if meta_file.exists():
        with open(meta_file, 'r') as f:
            kb_metadata = json.load(f)
        print(f"✓ KB metadata loaded")
    else:
        kb_metadata = {}

    # Initialize Enhanced RAG
    # Try to load Enhanced RAG v2 first, fall back to v1
    try:
        from rag.enhanced_rag_v2 import EnhancedRAGv2
        embedding_index_path = str(DATA_DIR / "embedding_index.pkl")
        enhanced_rag = EnhancedRAGv2(
            embedding_index_path=embedding_index_path,
            openai_api_key=OPENAI_API_KEY,
            use_reranker=True,
            use_mmr=True,
            cache_results=True
        )
        print("✓ Enhanced RAG v2.0 initialized (with hallucination detection)")
    except Exception as e:
        print(f"⚠ Enhanced RAG v2 failed, trying v1: {e}")
        try:
            from rag.enhanced_rag import EnhancedRAG
            embedding_index_path = str(DATA_DIR / "embedding_index.pkl")
            enhanced_rag = EnhancedRAG(
                embedding_index_path=embedding_index_path,
                openai_api_key=OPENAI_API_KEY,
                use_reranker=True,
                use_mmr=True,
                cache_queries=True
            )
            print("✓ Enhanced RAG v1 initialized (fallback)")
        except Exception as e2:
            import traceback
            print(f"⚠ Enhanced RAG not loaded: {e2}")
            traceback.print_exc()
            enhanced_rag = None

    # Initialize Stakeholder Graph
    try:
        from rag.stakeholder_graph import StakeholderGraph, build_stakeholder_graph
        stakeholder_file = DATA_DIR / "stakeholder_graph.pkl"
        if stakeholder_file.exists():
            stakeholder_graph = StakeholderGraph.load(stakeholder_file)
            print(f"✓ Stakeholder graph loaded ({stakeholder_graph.get_stats()['total_people']} people)")
        elif embedding_index:
            doc_index = embedding_index.get('doc_index', {})
            chunks = embedding_index.get('chunks', [])
            stakeholder_graph = build_stakeholder_graph(chunks, doc_index)
            stakeholder_graph.save(stakeholder_file)
            print(f"✓ Stakeholder graph built ({stakeholder_graph.get_stats()['total_people']} people)")
        else:
            stakeholder_graph = StakeholderGraph()
            print("⚠ Stakeholder graph empty - no documents to process")
    except Exception as e:
        print(f"⚠ Stakeholder graph not loaded: {e}")
        stakeholder_graph = None

    # Initialize Connector Manager
    try:
        from connectors.connector_manager import ConnectorManager
        connector_manager = ConnectorManager(config_dir=DATA_DIR / "connectors")
        print("✓ Connector manager initialized")
    except Exception as e:
        print(f"⚠ Connector manager not loaded: {e}")
        connector_manager = None

    # Initialize Document Manager
    try:
        from document_manager import DocumentManager
        LLAMAPARSE_KEY = os.getenv("LLAMAPARSE_API_KEY", "")
        document_manager = DocumentManager(
            api_key=OPENAI_API_KEY,
            llamaparse_key=LLAMAPARSE_KEY
        )
        print("✓ Document manager initialized")
    except Exception as e:
        print(f"⚠ Document manager not loaded: {e}")
        document_manager = None

    print("✓ Data loaded successfully\n")


# ============================================================================
# Main Routes
# ============================================================================

@app.route('/')
def index():
    """Home page with workflow"""
    stats = {
        'target_user': TARGET_USER,
        'total_documents': len(embedding_index.get('chunks', [])) if embedding_index else 0,
        'total_gaps': len(knowledge_gaps) if knowledge_gaps else 0,
    }
    return render_template('index_workflow.html', stats=stats)


# ============================================================================
# Step 0: Connectors API
# ============================================================================

@app.route('/api/connectors')
def api_connectors():
    """Get available connector types"""
    global connector_manager

    # Return static list
    connectors = [
        {
            'type': 'gmail',
            'name': 'Gmail',
            'icon': 'mail',
            'description': 'Sync emails from your Gmail account',
            'auth_type': 'oauth',
            'status': 'not_configured',
            'required_scopes': ['https://www.googleapis.com/auth/gmail.readonly']
        },
        {
            'type': 'slack',
            'name': 'Slack',
            'icon': 'slack',
            'description': 'Sync messages from Slack workspaces',
            'auth_type': 'token',
            'status': 'not_configured',
            'required_scopes': ['channels:history', 'users:read']
        },
        {
            'type': 'github',
            'name': 'GitHub',
            'icon': 'github',
            'description': 'Sync code, issues, and PRs from GitHub repos',
            'auth_type': 'token',
            'status': 'not_configured',
            'required_scopes': ['repo', 'read:org']
        }
    ]

    if connector_manager:
        user_connectors = connector_manager.get_user_connectors(TARGET_USER)
        for conn in connectors:
            user_conn = next((c for c in user_connectors if c['connector_type'] == conn['type']), None)
            if user_conn:
                conn['status'] = user_conn['status']
                conn['last_sync'] = user_conn.get('last_sync')

    return jsonify({
        'connectors': connectors,
        'configured_count': sum(1 for c in connectors if c['status'] == 'connected')
    })


@app.route('/api/connectors/add', methods=['POST'])
def api_add_connector():
    """Add a new connector"""
    data = request.get_json()
    connector_type = data.get('type')
    token = data.get('token')

    if not connector_type or not token:
        return jsonify({'error': 'Missing type or token'}), 400

    # For now, just acknowledge
    return jsonify({
        'success': True,
        'message': f'{connector_type} connector added successfully',
        'connector': {
            'type': connector_type,
            'status': 'connected'
        }
    })


# ============================================================================
# Gmail OAuth Routes
# ============================================================================

# Store for OAuth states and connected accounts (in production, use database)
gmail_oauth_states = {}
gmail_connected_accounts = {}

@app.route('/api/connectors/gmail/auth')
def gmail_auth():
    """Start Gmail OAuth flow - returns auth URL"""
    import os
    import secrets

    try:
        from connectors.gmail_connector import GmailConnector

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5003/api/connectors/gmail/callback")

        # Store state for verification
        gmail_oauth_states[state] = {
            'created': datetime.now().isoformat(),
            'redirect_uri': redirect_uri
        }

        # Get auth URL
        auth_url = GmailConnector.get_auth_url(redirect_uri, state)

        return jsonify({
            'success': True,
            'auth_url': auth_url,
            'state': state
        })

    except ImportError as e:
        return jsonify({
            'success': False,
            'error': 'Gmail dependencies not installed. Run: pip install google-auth google-auth-oauthlib google-api-python-client'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/connectors/gmail/callback')
def gmail_callback():
    """Handle Gmail OAuth callback"""
    import os
    import asyncio

    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    # Check for errors from Google
    if error:
        return f"""
        <html>
        <body>
            <h2>Authorization Failed</h2>
            <p>Error: {error}</p>
            <p>Please close this window and try again.</p>
            <script>
                setTimeout(function() {{
                    window.close();
                }}, 3000);
            </script>
        </body>
        </html>
        """

    # Verify state
    if state not in gmail_oauth_states:
        return f"""
        <html>
        <body>
            <h2>Invalid State</h2>
            <p>The authorization state is invalid. Please try again.</p>
            <script>
                setTimeout(function() {{
                    window.close();
                }}, 3000);
            </script>
        </body>
        </html>
        """

    try:
        from connectors.gmail_connector import GmailConnector

        stored_state = gmail_oauth_states.pop(state)
        redirect_uri = stored_state['redirect_uri']

        # Exchange code for tokens
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tokens = loop.run_until_complete(GmailConnector.exchange_code(code, redirect_uri))
        loop.close()

        # Store connected account (in production, store in database with user ID)
        gmail_connected_accounts['default'] = {
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'expiry': tokens.get('expiry'),
            'connected_at': datetime.now().isoformat()
        }

        # Return success page that closes popup and notifies parent
        return f"""
        <html>
        <body>
            <h2 style="color: green;">Gmail Connected Successfully!</h2>
            <p>You can close this window now.</p>
            <script>
                // Notify parent window
                if (window.opener) {{
                    window.opener.postMessage({{ type: 'GMAIL_CONNECTED', success: true }}, '*');
                }}
                // Close popup after 2 seconds
                setTimeout(function() {{
                    window.close();
                }}, 2000);
            </script>
        </body>
        </html>
        """

    except Exception as e:
        return f"""
        <html>
        <body>
            <h2>Authorization Error</h2>
            <p>Failed to complete authorization: {str(e)}</p>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{ type: 'GMAIL_CONNECTED', success: false, error: '{str(e)}' }}, '*');
                }}
                setTimeout(function() {{
                    window.close();
                }}, 3000);
            </script>
        </body>
        </html>
        """


@app.route('/api/connectors/gmail/status')
def gmail_status():
    """Check Gmail connection status"""
    if 'default' in gmail_connected_accounts:
        account = gmail_connected_accounts['default']
        return jsonify({
            'connected': True,
            'connected_at': account.get('connected_at'),
            'has_refresh_token': bool(account.get('refresh_token'))
        })
    return jsonify({
        'connected': False
    })


@app.route('/api/connectors/gmail/disconnect', methods=['POST'])
def gmail_disconnect():
    """Disconnect Gmail account"""
    if 'default' in gmail_connected_accounts:
        del gmail_connected_accounts['default']
        return jsonify({
            'success': True,
            'message': 'Gmail disconnected successfully'
        })
    return jsonify({
        'success': False,
        'message': 'No Gmail account connected'
    })


@app.route('/api/connectors/gmail/sync', methods=['POST'])
def gmail_sync():
    """Sync emails from connected Gmail account"""
    import asyncio

    if 'default' not in gmail_connected_accounts:
        return jsonify({
            'success': False,
            'error': 'Gmail not connected'
        }), 400

    try:
        from connectors.gmail_connector import GmailConnector
        from connectors.base_connector import ConnectorConfig

        account = gmail_connected_accounts['default']

        # Create connector config
        config = ConnectorConfig(
            connector_type='gmail',
            user_id='default',
            credentials={
                'access_token': account['access_token'],
                'refresh_token': account['refresh_token']
            },
            settings={
                'max_results': 50,
                'labels': ['INBOX', 'SENT']
            }
        )

        # Create connector and sync
        connector = GmailConnector(config)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        documents = loop.run_until_complete(connector.sync())
        loop.close()

        # Check if we should cluster the emails into projects
        cluster_emails = request.json.get('cluster_into_projects', True) if request.is_json else True
        projects_created = 0

        if cluster_emails and documents:
            try:
                from clustering.llm_first_clusterer import LLMFirstClusterer

                # Convert Gmail documents to the format expected by the clusterer
                # IMPORTANT: Only pass content and doc_id - NO METADATA
                docs_for_clustering = []
                for doc in documents:
                    docs_for_clustering.append({
                        'doc_id': doc.doc_id,
                        'content': doc.content  # Content only, no metadata
                    })

                # Run LLM-first high-accuracy clustering
                clusterer = LLMFirstClusterer(
                    openai_api_key=OPENAI_API_KEY,
                    cache_dir=str(DATA_DIR / "llm_cluster_cache")
                )

                projects = clusterer.process_documents(
                    docs_for_clustering,
                    embedding_threshold=0.6,  # Pre-filter threshold
                    llm_threshold=0.5,  # Min LLM confidence to connect docs
                    merge_threshold=0.85  # Min confidence to merge clusters
                )

                # Save results
                clusterer.save_results(str(DATA_DIR))

                # Update global canonical_projects
                global canonical_projects
                canonical_projects = {
                    pid: {
                        'id': p.id,
                        'name': p.name,
                        'description': p.description,
                        'document_ids': p.document_ids,
                        'document_count': len(p.document_ids),
                        'confidence': p.confidence,
                        'validation_status': p.validation_status
                    }
                    for pid, p in projects.items()
                }

                projects_created = len(projects)
                print(f"✓ Clustered {len(documents)} emails into {projects_created} projects")

            except Exception as cluster_error:
                print(f"⚠ Email clustering failed: {cluster_error}")
                import traceback
                traceback.print_exc()

        return jsonify({
            'success': True,
            'documents_synced': len(documents),
            'projects_created': projects_created,
            'documents': [
                {
                    'doc_id': doc.doc_id,
                    'title': doc.title,
                    'author': doc.author,
                    'timestamp': doc.timestamp.isoformat() if doc.timestamp else None
                }
                for doc in documents[:10]  # Return first 10 as preview
            ]
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Step 1: Message Review API
# ============================================================================

@app.route('/api/messages/review')
def api_messages_review():
    """Get messages that need review"""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    space_filter = request.args.get('space', '')

    # Load uncertain messages from filter results
    uncertain_file = DATA_DIR / "filter_v2_uncertain.json"
    messages = []

    if uncertain_file.exists():
        with open(uncertain_file, 'r') as f:
            uncertain_data = json.load(f)
        messages = uncertain_data if isinstance(uncertain_data, list) else uncertain_data.get('messages', [])

    # Filter by space if specified
    if space_filter:
        messages = [m for m in messages if m.get('space', '') == space_filter]

    # Paginate
    total = len(messages)
    start = (page - 1) * per_page
    end = start + per_page
    page_messages = messages[start:end]

    return jsonify({
        'messages': page_messages,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })


@app.route('/api/messages/review/count')
def api_review_count():
    """Get count of messages needing review"""
    uncertain_file = DATA_DIR / "filter_v2_uncertain.json"
    count = 0

    if uncertain_file.exists():
        with open(uncertain_file, 'r') as f:
            data = json.load(f)
        count = len(data) if isinstance(data, list) else len(data.get('messages', []))

    return jsonify({'count': count})


@app.route('/api/messages/decide', methods=['POST'])
def api_message_decide():
    """Record a decision for a message"""
    data = request.get_json()
    message_id = data.get('message_id')
    decision = data.get('decision')  # 'include' or 'exclude'

    # Store decision (in real app, would save to database)
    decisions_file = DATA_DIR / "message_decisions.json"
    decisions = {}
    if decisions_file.exists():
        with open(decisions_file, 'r') as f:
            decisions = json.load(f)

    decisions[message_id] = decision

    with open(decisions_file, 'w') as f:
        json.dump(decisions, f)

    return jsonify({'success': True})


@app.route('/api/spaces')
def api_spaces():
    """Get all user spaces/projects"""
    return jsonify({'spaces': user_spaces or []})


# ============================================================================
# Step 2: Questions API
# ============================================================================

@app.route('/api/questions')
def api_questions_v1():
    """Get knowledge gap questions, optionally filtered by project - Enhanced version"""
    global knowledge_gaps, canonical_projects

    project_filter = request.args.get('project')
    question_type = request.args.get('type', '')

    if not knowledge_gaps:
        return jsonify({'questions': [], 'projects': [], 'total': 0})

    # Group questions by project
    project_questions = {}

    for gap in knowledge_gaps:
        project = gap.get('project', 'General')
        if project not in project_questions:
            project_questions[project] = {
                'project': project,
                'questions': [],
                'answered_count': 0,
                'total_count': 0
            }

        question = {
            'id': gap.get('id', len(project_questions[project]['questions'])),
            'type': gap.get('type', 'unknown'),
            'description': gap.get('description', ''),
            'severity': gap.get('severity', 'medium'),
            'answered': gap.get('answered', False),
            'answer': gap.get('answer', '')
        }

        # Filter by type if specified
        if question_type and question['type'] != question_type:
            continue

        project_questions[project]['questions'].append(question)
        project_questions[project]['total_count'] += 1
        if question['answered']:
            project_questions[project]['answered_count'] += 1

    # Convert to list
    result = list(project_questions.values())

    # Filter by project if specified
    if project_filter:
        result = [p for p in result if p['project'].lower() == project_filter.lower()]

    # Sort by total questions
    result.sort(key=lambda x: x['total_count'], reverse=True)

    # Also return flat list for backwards compatibility
    flat_questions = knowledge_gaps or []
    if question_type:
        flat_questions = [q for q in flat_questions if q.get('type', '') == question_type]
    if project_filter:
        flat_questions = [q for q in flat_questions if q.get('project', '') == project_filter]

    return jsonify({
        'projects': result,
        'questions': flat_questions,  # Backwards compatibility
        'total_projects': len(result),
        'total_questions': sum(p['total_count'] for p in result)
    })


@app.route('/api/questions/answer-legacy', methods=['POST'])
def api_answer_question_v1():
    """Submit an answer to a knowledge gap question and add to RAG"""
    global knowledge_gaps, enhanced_rag

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    question_id = data.get('question_id')
    answer = data.get('answer', '').strip()
    project = data.get('project', '')
    question_text = data.get('question', '')

    if not answer:
        return jsonify({'error': 'Answer cannot be empty'}), 400

    # Find and update the question
    updated = False
    for gap in (knowledge_gaps or []):
        gap_id = gap.get('id', '')
        # Match by ID or by description
        if str(gap_id) == str(question_id) or gap.get('description', '') == question_text:
            gap['answered'] = True
            gap['answer'] = answer
            gap['answered_at'] = datetime.now().isoformat()
            updated = True
            break

    if updated:
        # Save updated knowledge gaps
        gaps_file = DATA_DIR / "knowledge_gaps.json"
        with open(gaps_file, 'w') as f:
            json.dump(knowledge_gaps, f, indent=2)

        # Also save to answers file for backwards compatibility
        answers_file = DATA_DIR / "question_answers.json"
        answers = {}
        if answers_file.exists():
            with open(answers_file, 'r') as f:
                answers = json.load(f)

        answers[str(question_id)] = {
            'answer': answer,
            'timestamp': datetime.now().isoformat(),
            'project': project
        }

        with open(answers_file, 'w') as f:
            json.dump(answers, f, indent=2)

        return jsonify({
            'success': True,
            'message': 'Answer recorded successfully',
            'added_to_rag': False  # TODO: implement RAG addition
        })

    return jsonify({
        'success': False,
        'error': 'Question not found'
    }), 404


# ============================================================================
# Step 3: RAG Search API
# ============================================================================

@app.route('/api/search', methods=['POST'])
def api_search():
    """Search the knowledge base"""
    global enhanced_rag, stakeholder_graph

    data = request.get_json()
    query = data.get('query', '')

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    # Check if this is a "who" question for stakeholder graph
    query_lower = query.lower().strip()
    is_who_query = (
        query_lower.startswith('who ') or
        query_lower.startswith('who\'s ') or
        ' who ' in query_lower or
        'who knows' in query_lower or
        'who is' in query_lower or
        'who worked' in query_lower or
        'who handles' in query_lower or
        'contact for' in query_lower
    )

    if is_who_query and stakeholder_graph:
        # Use stakeholder graph for "who" queries
        result = stakeholder_graph.answer_who_question(query)

        # Format answer
        answer_parts = []
        if result['answer_type'] == 'domain_experts':
            domain = result.get('domain', 'this area')
            if result['results']:
                answer_parts.append(f"People with expertise in {domain}:\n")
                for r in result['results'][:30]:
                    exp_str = f"- {r['name']}"
                    if r.get('roles'):
                        exp_str += f" ({', '.join(r['roles'][:2])})"
                    if r.get('projects'):
                        exp_str += f" - worked on {', '.join(list(r['projects'])[:2])}"
                    answer_parts.append(exp_str)
            else:
                answer_parts.append(f"No experts found for {domain} in the knowledge base.")

        elif result['answer_type'] == 'project_team':
            project = result.get('project', 'this project')
            if result['results']:
                answer_parts.append(f"Team members for {project}:\n")
                for r in result['results']:
                    answer_parts.append(f"- {r['name']}")
            else:
                answer_parts.append(f"No team members found for {project}.")

        elif result['answer_type'] == 'person_info':
            if result['results']:
                r = result['results'][0]
                info = f"{r['name']}"
                if r.get('roles'):
                    info += f" is a {', '.join(r['roles'])}"
                if r.get('expertise'):
                    info += f" with expertise in {', '.join(r['expertise'])}"
                if r.get('projects'):
                    info += f". Projects: {', '.join(list(r['projects'])[:5])}"
                answer_parts.append(info)
            else:
                answer_parts.append("Person not found in the knowledge base.")

        return jsonify({
            'query': query,
            'answer': '\n'.join(answer_parts),
            'search_type': 'stakeholder_graph',
            'query_type': result.get('answer_type', 'unknown'),
            'sources': []
        })

    # Use enhanced RAG for regular queries
    if enhanced_rag:
        try:
            result = enhanced_rag.query(query)

            # Convert numpy types to native Python types for JSON serialization
            def convert_numpy(obj):
                import numpy as np
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: convert_numpy(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy(i) for i in obj]
                return obj

            sources = convert_numpy(result.get('sources', []))

            return jsonify({
                'query': query,
                'answer': result.get('answer', 'No answer generated'),
                'sources': sources,
                'search_type': 'enhanced_rag',
                'num_sources': int(result.get('num_sources', 0)),
                'confidence': float(result.get('confidence', 0)),
                'query_type': result.get('query_type', 'unknown'),
                'expanded_query': result.get('expanded_query', query),
                'model': result.get('model', 'gpt-4o'),
                'retrieval_time': float(result.get('retrieval_time', 0)),
                'validated': result.get('validated', False),
                'features': {
                    'reranking': True,
                    'mmr_diversity': True,
                    'query_expansion': True,
                    'semantic_chunking': True,
                    'caching': True
                }
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({
                'query': query,
                'answer': f'Error: {str(e)}',
                'sources': [],
                'search_type': 'error'
            })

    # Fallback to basic search
    return jsonify({
        'query': query,
        'answer': 'RAG not initialized. Please check configuration.',
        'sources': [],
        'search_type': 'fallback'
    })


# ============================================================================
# Step 4: Stakeholder API
# ============================================================================

@app.route('/api/stakeholders')
def api_stakeholders():
    """Get all stakeholders (people) from the graph"""
    global stakeholder_graph
    if stakeholder_graph is None:
        return jsonify({'error': 'Stakeholder graph not loaded', 'people': [], 'total': 0})

    # Non-person terms to filter out at API level
    NON_PERSON_TERMS = {
        'countries', 'producing', 'global', 'production', 'blueberry', 'blueberries',
        'federal', 'regulations', 'artificial', 'intelligence', 'kaiser', 'permanente',
        'da vinci', 'implementation', 'strategy', 'focus', 'areas', 'take', 'evaluations',
        'supply', 'chain', 'shadowing', 'proposal', 'market', 'growth', 'competitive',
        'row', 'labels', 'gen', 'ped', 'metric', 'tons', 'southern', 'hemisphere',
        'neonatal', 'intensive', 'emergency', 'department', 'governing', 'law',
        'overview', 'charter', 'timeline', 'sponsor', 'manager', 'file', 'copy',
        'ucla', 'health', 'business', 'plan', 'presentation', 'main', 'topics',
        # Additional filter terms
        'vice', 'president', 'amendment', 'process', 'processing', 'facilities', 'facility',
        'director', 'operation', 'room', 'hematopoietic', 'cell', 'therapy', 'immune',
        'effector', 'context', 'average', 'length', 'soft', 'costs', 'initial', 'outlay',
        'adverse', 'effects', 'service', 'line', 'first', 'steps', 'next', 'steps',
        'key', 'findings', 'total', 'revenue', 'action', 'items', 'important', 'dates',
        'problem', 'statement', 'current', 'state', 'recommendation', 'analysis',
        # More filter terms
        'engagement', 'briefing', 'all', 'events', 'gestational', 'age', 'pulmonary', 'atresia',
        'higher', 'level', 'prolonged', 'stays', 'bruin', 'political', 'review', 'delhi',
        'jersey', 'legal', 'remedies', 'disclosing', 'party', 'full', 'name', 'flight', 'details',
        'delta', 'air', 'pauls', 'travel', 'new', 'york', 'los', 'angeles', 'san', 'francisco',
        'north', 'south', 'east', 'west', 'central', 'pacific', 'atlantic', 'region',
    }

    def is_likely_person(name: str) -> bool:
        """Check if name looks like a real person"""
        # Filter out names with newlines (malformed data)
        if '\n' in name or '\r' in name:
            return False

        # Filter out very long names (likely parsing errors)
        if len(name) > 40:
            return False

        normalized = name.lower()
        words = normalized.split()

        # Check if any word matches non-person terms
        for word in words:
            if word in NON_PERSON_TERMS:
                return False

        # Check full name against phrases
        for term in NON_PERSON_TERMS:
            if term in normalized:
                return False

        # Must have at least 2 words (first and last name)
        if len(words) < 2:
            return False

        # Max 4 words in a name
        if len(words) > 4:
            return False

        # Known good names (whitelist)
        known_names = {
            'rishit jain', 'eric yang', 'badri mishra', 'badri vinayak mishra',
            'pranav reddy', 'stewart fang', 'alan tran', 'aarushi maheshwari',
            'melaney stricklin', 'danny zhu', 'rohit guha', 'shawn wang', 'gil travish',
        }
        if normalized in known_names:
            return True

        # Filter out names that are too generic
        generic_words = {'the', 'and', 'for', 'with', 'from', 'into', 'by', 'or', 'to'}
        if any(w in generic_words for w in words):
            return False

        return True

    people_list = []
    for name, person in stakeholder_graph.people.items():
        if is_likely_person(person.name):
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


@app.route('/api/stakeholders/expertise')
def api_expertise_domains():
    """Get all expertise domains and people count"""
    global stakeholder_graph
    if stakeholder_graph is None:
        return jsonify({'domains': []})

    domains = []
    for domain, people in stakeholder_graph.expertise_people.items():
        domains.append({
            'domain': domain,
            'people_count': len(people),
            'people': list(people)[:5]
        })

    domains.sort(key=lambda x: x['people_count'], reverse=True)
    return jsonify({'domains': domains})


@app.route('/api/stakeholders/projects')
def api_stakeholder_projects():
    """Get all projects with their team members"""
    global stakeholder_graph
    if stakeholder_graph is None:
        return jsonify({'projects': [], 'total': 0})

    projects_list = []
    for name, project in stakeholder_graph.projects.items():
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

    projects_list.sort(key=lambda x: len(x['team']), reverse=True)

    return jsonify({
        'projects': projects_list,
        'total': len(projects_list)
    })


# ============================================================================
# Stats API
# ============================================================================

@app.route('/api/stats')
def api_stats():
    """Get system statistics"""
    return jsonify({
        'total_documents': len(embedding_index.get('chunks', [])) if embedding_index else 0,
        'total_gaps': len(knowledge_gaps) if knowledge_gaps else 0,
        'total_spaces': len(user_spaces) if user_spaces else 0,
        'stakeholder_count': stakeholder_graph.get_stats()['total_people'] if stakeholder_graph else 0
    })


@app.route('/api/all-emails')
def api_all_emails():
    """Get all documents/emails for the Documents page"""
    if not search_index:
        return jsonify({'success': False, 'emails': []})

    emails = []
    doc_ids = search_index.get('doc_ids', [])
    doc_index = search_index.get('doc_index', {})

    for i, doc_id in enumerate(doc_ids[:500]):  # Limit to 500 for performance
        doc = doc_index.get(doc_id, {})
        metadata = doc.get('metadata', {})
        content = doc.get('content', '')

        emails.append({
            'id': doc_id,
            'subject': metadata.get('file_name', doc_id),
            'content': content[:200] if content else '',
            'date': metadata.get('date', '2024-01-01'),
            'from': metadata.get('project', 'Unknown Project')
        })

    return jsonify({
        'success': True,
        'emails': emails
    })


@app.route('/api/training-materials')
def api_training_materials():
    """Get training materials - currently empty as requested"""
    return jsonify({
        'success': True,
        'materials': {
            'videos': [],
            'documents': []
        }
    })


@app.route('/api/document/<doc_id>')
def api_get_document(doc_id):
    """Get a specific document by ID - for document viewer/download"""
    if not search_index:
        return jsonify({'success': False, 'error': 'No search index loaded'}), 404

    doc_index = search_index.get('doc_index', {})
    doc = doc_index.get(doc_id)

    if not doc:
        return jsonify({'success': False, 'error': 'Document not found'}), 404

    metadata = doc.get('metadata', {})
    content = doc.get('content', '')

    # Build document response with full content
    return jsonify({
        'success': True,
        'document': {
            'id': doc_id,
            'title': metadata.get('file_name', doc_id),
            'content': content,
            'metadata': {
                'project': metadata.get('project', 'Unknown'),
                'date': metadata.get('date', ''),
                'file_path': metadata.get('file_path', ''),
                'file_type': metadata.get('file_type', 'text'),
                'source': metadata.get('source', 'unknown')
            },
            'view_url': f'/api/document/{doc_id}/view',
            'download_url': f'/api/document/{doc_id}/download'
        }
    })


@app.route('/api/document/<doc_id>/view')
def api_view_document(doc_id):
    """Render document for viewing in browser"""
    if not search_index:
        return "Document not found", 404

    doc_index = search_index.get('doc_index', {})
    doc = doc_index.get(doc_id)

    if not doc:
        return "Document not found", 404

    metadata = doc.get('metadata', {})
    content = doc.get('content', '')
    title = metadata.get('file_name', doc_id)

    # Simple HTML view
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                   max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
            h1 {{ color: #333; border-bottom: 2px solid #f60; padding-bottom: 10px; }}
            .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
            .content {{ white-space: pre-wrap; background: #f5f5f5; padding: 20px; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <h1>{title}</h1>
        <div class="meta">
            <strong>Project:</strong> {metadata.get('project', 'Unknown')} |
            <strong>Date:</strong> {metadata.get('date', 'N/A')}
        </div>
        <div class="content">{content}</div>
    </body>
    </html>
    """
    return html


# ============================================================================
# Feedback Collection API - For improving RAG accuracy
# ============================================================================

# In-memory feedback store (in production, use database)
feedback_store = []

@app.route('/api/feedback', methods=['POST'])
def api_feedback():
    """
    Collect user feedback on RAG answers for continuous improvement.

    Request body:
    {
        "query": "original question",
        "answer": "generated answer",
        "rating": "up" or "down",
        "source_ids": ["doc_1", "doc_2"],
        "comment": "optional user comment"
    }
    """
    global feedback_store

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    feedback_entry = {
        'id': len(feedback_store) + 1,
        'timestamp': datetime.now().isoformat(),
        'query': data.get('query', ''),
        'answer': data.get('answer', '')[:500],  # Truncate for storage
        'rating': data.get('rating', 'neutral'),  # 'up', 'down', 'neutral'
        'source_ids': data.get('source_ids', []),
        'comment': data.get('comment', ''),
        'user_id': data.get('user_id', 'anonymous')
    }

    feedback_store.append(feedback_entry)

    # Log negative feedback for analysis
    if feedback_entry['rating'] == 'down':
        print(f"[Feedback] Negative feedback on query: {feedback_entry['query'][:50]}...")

    return jsonify({
        'success': True,
        'feedback_id': feedback_entry['id'],
        'message': 'Feedback recorded. Thank you for helping improve our system!'
    })


@app.route('/api/feedback/stats')
def api_feedback_stats():
    """Get feedback statistics for monitoring"""
    total = len(feedback_store)
    positive = sum(1 for f in feedback_store if f['rating'] == 'up')
    negative = sum(1 for f in feedback_store if f['rating'] == 'down')

    return jsonify({
        'total_feedback': total,
        'positive': positive,
        'negative': negative,
        'satisfaction_rate': positive / total if total > 0 else 0,
        'recent_negative': [f for f in feedback_store if f['rating'] == 'down'][-5:]
    })


# Import datetime for feedback timestamps
from datetime import datetime

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"



# ============================================================================
# Intelligent Project Clustering API
# ============================================================================

# Global variable for intelligent project clusterer
intelligent_clusterer = None
canonical_projects = {}

@app.route('/api/projects')
def api_projects():
    """Get all canonical projects from intelligent clustering"""
    global canonical_projects

    # Try to load from file if not in memory
    if not canonical_projects:
        projects_file = DATA_DIR / "canonical_projects.json"
        if projects_file.exists():
            with open(projects_file, 'r') as f:
                data = json.load(f)
                canonical_projects = data

    if not canonical_projects:
        # Return legacy user_spaces if no canonical projects
        if user_spaces:
            return jsonify({
                'projects': [
                    {
                        'id': s.get('space_id', str(i)),
                        'name': s.get('generated_project_name', s.get('space_name', f'Project {i}')),
                        'description': '',
                        'document_count': s.get('message_count', 0) + s.get('file_count', 0),
                        'team_members': s.get('members', []),
                        'status': 'active',
                        'source': 'legacy'
                    }
                    for i, s in enumerate(user_spaces)
                ],
                'total': len(user_spaces),
                'source': 'legacy_spaces'
            })
        return jsonify({'projects': [], 'total': 0})

    projects_list = []
    for pid, proj in canonical_projects.items():
        projects_list.append({
            'id': pid,
            'name': proj.get('name', 'Unknown'),
            'description': proj.get('description', ''),
            'document_count': proj.get('document_count', 0),
            'status': proj.get('status', 'active')
        })

    # Sort by document count
    projects_list.sort(key=lambda x: x['document_count'], reverse=True)

    return jsonify({
        'projects': projects_list,
        'total': len(projects_list)
    })


@app.route('/api/projects/<project_id>')
def api_project_detail(project_id):
    """Get detailed information about a specific project"""
    global canonical_projects

    if not canonical_projects:
        projects_file = DATA_DIR / "canonical_projects.json"
        if projects_file.exists():
            with open(projects_file, 'r') as f:
                canonical_projects = json.load(f)

    project = canonical_projects.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    return jsonify({
        'success': True,
        'project': project
    })


@app.route('/api/projects/<project_id>/documents')
def api_project_documents(project_id):
    """Get all documents in a project"""
    global canonical_projects

    if not canonical_projects:
        projects_file = DATA_DIR / "canonical_projects.json"
        if projects_file.exists():
            with open(projects_file, 'r') as f:
                canonical_projects = json.load(f)

    project = canonical_projects.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found', 'documents': []}), 404

    doc_ids = project.get('document_ids', [])
    documents = []

    if search_index:
        doc_index = search_index.get('doc_index', {})
        for doc_id in doc_ids[:100]:  # Limit to 100
            doc = doc_index.get(doc_id, {})
            if doc:
                documents.append({
                    'id': doc_id,
                    'title': doc.get('metadata', {}).get('file_name', doc_id),
                    'content_preview': doc.get('content', '')[:200],
                    'date': doc.get('metadata', {}).get('date', '')
                })

    return jsonify({
        'project_id': project_id,
        'project_name': project.get('name', ''),
        'documents': documents,
        'total': len(doc_ids)
    })


@app.route('/api/projects/<project_id>/gaps')
def api_project_gaps(project_id):
    """Get knowledge gaps for a specific project"""
    global canonical_projects, knowledge_gaps

    if not canonical_projects:
        projects_file = DATA_DIR / "canonical_projects.json"
        if projects_file.exists():
            with open(projects_file, 'r') as f:
                canonical_projects = json.load(f)

    project = canonical_projects.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found', 'gaps': []}), 404

    project_name = project.get('name', '')

    # Filter knowledge gaps for this project
    project_gaps = []
    if knowledge_gaps:
        for gap in knowledge_gaps:
            gap_project = gap.get('project', '')
            # Match by project name or topics
            if gap_project.lower() == project_name.lower():
                project_gaps.append(gap)
            elif any(topic.lower() in gap.get('description', '').lower()
                    for topic in project.get('key_topics', [])):
                project_gaps.append(gap)

    return jsonify({
        'project_id': project_id,
        'project_name': project_name,
        'gaps': project_gaps,
        'total': len(project_gaps)
    })


@app.route('/api/projects/reprocess', methods=['POST'])
def api_reprocess_projects():
    """Trigger LLM-first high-accuracy clustering on all documents"""
    global canonical_projects

    try:
        from clustering.llm_first_clusterer import LLMFirstClusterer

        # Get all documents from search index
        if not search_index:
            return jsonify({'error': 'No search index loaded'}), 400

        doc_index = search_index.get('doc_index', {})
        documents = []

        # CONTENT ONLY - NO METADATA
        for doc_id, doc in doc_index.items():
            documents.append({
                'doc_id': doc_id,
                'content': doc.get('content', '')
            })

        if not documents:
            return jsonify({'error': 'No documents found'}), 400

        print(f"\n{'='*70}")
        print(f"RE-CLUSTERING {len(documents)} DOCUMENTS")
        print(f"{'='*70}")

        # Initialize LLM-first clusterer
        clusterer = LLMFirstClusterer(
            openai_api_key=OPENAI_API_KEY,
            cache_dir=str(DATA_DIR / "llm_cluster_cache")
        )

        # Process documents with high-accuracy settings
        projects = clusterer.process_documents(
            documents,
            embedding_threshold=0.6,  # Pre-filter
            llm_threshold=0.5,  # LLM confidence to connect
            merge_threshold=0.85  # Merge confidence
        )

        # Save results
        clusterer.save_results(str(DATA_DIR))

        # Reload canonical_projects from saved file
        projects_file = DATA_DIR / "canonical_projects.json"
        if projects_file.exists():
            with open(projects_file, 'r') as f:
                canonical_projects = json.load(f)

        print(f"✓ Loaded {len(canonical_projects)} projects into memory")

        # Get summary
        summary = clusterer.get_project_summary()

        return jsonify({
            'success': True,
            'message': f'Successfully clustered {len(documents)} documents into {len(projects)} projects',
            'projects_created': len(projects),
            'documents_processed': len(documents),
            'summary': summary
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Voice Transcription API (OpenAI Whisper)
# ============================================================================

@app.route('/api/transcribe', methods=['POST'])
def api_transcribe():
    """Transcribe audio using OpenAI Whisper API (best-in-class transcription)"""
    import tempfile
    import os

    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']

    if not audio_file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        # Transcribe with Whisper
        with open(tmp_path, 'rb') as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="en",
                response_format="text"
            )

        # Clean up
        os.unlink(tmp_path)

        return jsonify({
            'transcript': transcript,
            'success': True
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Intelligent Knowledge Gap Detection System
# ============================================================================

def analyze_document_completeness(doc_content: str, doc_metadata: dict, project_name: str) -> list:
    """Use GPT-4o to analyze what's missing from a document"""

    prompt = f"""Analyze this document from project "{project_name}" and identify specific knowledge gaps.

Document metadata:
- Type: {doc_metadata.get('file_type', 'unknown')}
- Subject: {doc_metadata.get('subject', 'N/A')}
- Source: {doc_metadata.get('source', 'unknown')}

Document content (first 3000 chars):
{doc_content[:3000]}

Identify 2-5 SPECIFIC knowledge gaps based on ACTUAL content analysis. For each gap:
1. What specific information is mentioned but not explained?
2. What decisions are referenced without rationale?
3. What outcomes/results are missing?
4. What stakeholder perspectives are absent?
5. What technical details need clarification?

Return JSON array with gaps:
[
  {{
    "type": "decision_rationale|missing_outcome|unexplained_reference|stakeholder_gap|technical_gap|process_gap",
    "description": "Specific question about what's missing (reference actual content)",
    "context": "Quote or reference from doc that shows the gap",
    "severity": "high|medium|low",
    "confidence": 0.0-1.0
  }}
]

Only return gaps you're confident about based on actual document content. Return empty array if document is complete."""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        gaps = result if isinstance(result, list) else result.get('gaps', [])

        # Add project context
        for gap in gaps:
            gap['project'] = project_name
            gap['source_doc'] = doc_metadata.get('file_name', 'unknown')
            gap['is_standard'] = False
            gap['source'] = 'content_analysis'

        return gaps
    except Exception as e:
        print(f"Error analyzing document: {e}")
        return []


def detect_cross_project_gaps(projects_data: dict) -> list:
    """Identify information that exists in one project but is missing in similar projects"""

    if len(projects_data) < 2:
        return []

    # Build summary of what each project has documented
    project_summaries = {}
    for project, docs in projects_data.items():
        topics = set()
        for doc in docs:
            content = doc.get('content', '')[:1000].lower()
            # Extract key topics
            if 'budget' in content or 'cost' in content:
                topics.add('budget')
            if 'timeline' in content or 'deadline' in content:
                topics.add('timeline')
            if 'stakeholder' in content or 'client' in content:
                topics.add('stakeholders')
            if 'risk' in content:
                topics.add('risks')
            if 'outcome' in content or 'result' in content:
                topics.add('outcomes')
            if 'lesson' in content or 'learned' in content:
                topics.add('lessons_learned')
            if 'metric' in content or 'kpi' in content:
                topics.add('metrics')
            if 'decision' in content:
                topics.add('decisions')
        project_summaries[project] = topics

    # Find gaps by comparison
    gaps = []
    all_topics = set()
    for topics in project_summaries.values():
        all_topics.update(topics)

    topic_questions = {
        'budget': 'What was the budget allocation and final cost for {project}?',
        'timeline': 'What was the project timeline and were milestones met for {project}?',
        'stakeholders': 'Who were the key stakeholders and their roles in {project}?',
        'risks': 'What risks were identified and how were they mitigated in {project}?',
        'outcomes': 'What were the final outcomes and deliverables for {project}?',
        'lessons_learned': 'What lessons were learned from {project}?',
        'metrics': 'What success metrics were used to evaluate {project}?',
        'decisions': 'What key decisions were made and why in {project}?'
    }

    for project, topics in project_summaries.items():
        missing = all_topics - topics
        for topic in missing:
            if topic in topic_questions:
                gaps.append({
                    'type': 'cross_project_gap',
                    'description': topic_questions[topic].format(project=project),
                    'project': project,
                    'severity': 'medium',
                    'is_standard': False,
                    'source': 'cross_project_analysis',
                    'context': f"Other projects have {topic} documented, but {project} doesn't"
                })

    return gaps


def generate_followup_questions(question: str, answer: str, project: str) -> list:
    """Generate intelligent follow-up questions based on an answer"""

    prompt = f"""Based on this Q&A from project "{project}", generate 1-3 smart follow-up questions.

Question: {question}
Answer: {answer}

Generate follow-up questions that:
1. Dig deeper into specifics mentioned
2. Ask for evidence or examples
3. Explore implications or next steps
4. Clarify any ambiguous parts

Return JSON array:
[
  {{
    "description": "Follow-up question text",
    "type": "clarification|evidence|implication|detail",
    "severity": "medium",
    "reason": "Why this follow-up is important"
  }}
]

Only generate genuinely useful follow-ups. Return empty array if answer is complete."""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        followups = result if isinstance(result, list) else result.get('questions', result.get('followups', []))

        for q in followups:
            q['project'] = project
            q['is_standard'] = False
            q['source'] = 'followup_generation'
            q['parent_question'] = question[:100]

        return followups
    except Exception as e:
        print(f"Error generating followups: {e}")
        return []


@app.route('/api/questions/generate', methods=['POST'])
def api_generate_questions():
    """Generate intelligent questions by analyzing documents"""
    global knowledge_gaps, embedding_index

    data = request.get_json() or {}
    project_filter = data.get('project')
    force_regenerate = data.get('force', False)

    try:
        new_gaps = []
        projects_data = {}

        # Get documents from embedding index
        if embedding_index and 'chunks' in embedding_index:
            chunks = embedding_index['chunks']

            # Group by project
            for chunk in chunks[:200]:  # Limit for performance
                metadata = chunk.get('metadata', {})
                project = metadata.get('project', metadata.get('space_name', 'General'))

                if project_filter and project.lower() != project_filter.lower():
                    continue

                if project not in projects_data:
                    projects_data[project] = []
                projects_data[project].append({
                    'content': chunk.get('text', ''),
                    'metadata': metadata
                })

        # Analyze each project's documents
        for project, docs in projects_data.items():
            # Sample documents for analysis (max 5 per project)
            sample_docs = docs[:5]

            for doc in sample_docs:
                doc_gaps = analyze_document_completeness(
                    doc['content'],
                    doc['metadata'],
                    project
                )
                new_gaps.extend(doc_gaps)

        # Add cross-project gap detection
        cross_gaps = detect_cross_project_gaps(projects_data)
        new_gaps.extend(cross_gaps)

        # Deduplicate by description similarity
        seen_descriptions = set()
        unique_gaps = []
        for gap in new_gaps:
            desc_key = gap['description'][:50].lower()
            if desc_key not in seen_descriptions:
                seen_descriptions.add(desc_key)
                gap['id'] = f"gen_{len(unique_gaps)}_{hash(gap['description']) % 10000}"
                unique_gaps.append(gap)

        # Merge with existing gaps if not force regenerate
        if not force_regenerate and knowledge_gaps:
            # Keep existing gaps, add new ones
            existing_descs = {g['description'][:50].lower() for g in knowledge_gaps}
            for gap in unique_gaps:
                if gap['description'][:50].lower() not in existing_descs:
                    knowledge_gaps.append(gap)
        else:
            knowledge_gaps = unique_gaps

        # Save updated gaps
        gaps_file = DATA_DIR / "knowledge_gaps.json"
        with open(gaps_file, 'w') as f:
            json.dump(knowledge_gaps, f, indent=2)

        return jsonify({
            'success': True,
            'new_gaps_count': len(unique_gaps),
            'total_gaps': len(knowledge_gaps),
            'projects_analyzed': len(projects_data),
            'message': f"Generated {len(unique_gaps)} new questions from document analysis"
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/questions/answer', methods=['POST'])
def api_answer_question_v2():
    """Enhanced answer submission with follow-up question generation"""
    global knowledge_gaps, enhanced_rag

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    question_id = data.get('question_id')
    answer = data.get('answer', '').strip()
    project = data.get('project', '')
    question_text = data.get('question', '')
    generate_followups = data.get('generate_followups', True)

    if not answer:
        return jsonify({'error': 'Answer cannot be empty'}), 400

    # Find and update the question
    updated = False
    original_question = None
    for gap in (knowledge_gaps or []):
        gap_id = gap.get('id', '')
        if str(gap_id) == str(question_id) or gap.get('description', '') == question_text:
            gap['answered'] = True
            gap['answer'] = answer
            gap['answered_at'] = datetime.now().isoformat()
            original_question = gap.get('description', question_text)
            updated = True
            break

    followup_questions = []

    if updated:
        # Save updated knowledge gaps
        gaps_file = DATA_DIR / "knowledge_gaps.json"
        with open(gaps_file, 'w') as f:
            json.dump(knowledge_gaps, f, indent=2)

        # Generate follow-up questions
        if generate_followups and original_question:
            followup_questions = generate_followup_questions(original_question, answer, project)

            # Add follow-ups to knowledge gaps
            for fq in followup_questions:
                fq['id'] = f"followup_{len(knowledge_gaps)}_{hash(fq['description']) % 10000}"
                knowledge_gaps.append(fq)

            # Save again with follow-ups
            with open(gaps_file, 'w') as f:
                json.dump(knowledge_gaps, f, indent=2)

        # Add to RAG if available
        if enhanced_rag:
            try:
                qa_content = f"Q: {original_question}\nA: {answer}"
                enhanced_rag.add_document(
                    content=qa_content,
                    metadata={
                        'source': 'knowledge_gap_answer',
                        'project': project,
                        'type': 'qa_pair',
                        'timestamp': datetime.now().isoformat()
                    }
                )
            except Exception as e:
                print(f"Error adding to RAG: {e}")

        return jsonify({
            'success': True,
            'message': 'Answer saved successfully',
            'added_to_rag': enhanced_rag is not None,
            'followup_questions': followup_questions,
            'followup_count': len(followup_questions)
        })

    return jsonify({
        'success': False,
        'message': 'Question not found'
    }), 404


@app.route('/api/questions/analyze-project', methods=['POST'])
def api_analyze_project():
    """Deep analysis of a specific project to find all gaps"""
    global embedding_index

    data = request.get_json() or {}
    project_name = data.get('project')

    if not project_name:
        return jsonify({'error': 'Project name required'}), 400

    try:
        project_docs = []

        # Gather all docs for this project
        if embedding_index and 'chunks' in embedding_index:
            for chunk in embedding_index['chunks']:
                metadata = chunk.get('metadata', {})
                proj = metadata.get('project', metadata.get('space_name', ''))
                if proj.lower() == project_name.lower():
                    project_docs.append({
                        'content': chunk.get('text', ''),
                        'metadata': metadata
                    })

        if not project_docs:
            return jsonify({
                'error': f'No documents found for project: {project_name}',
                'gaps': []
            })

        # Comprehensive project analysis prompt
        combined_content = "\n\n---\n\n".join([d['content'][:1500] for d in project_docs[:10]])

        prompt = f"""Perform a comprehensive knowledge gap analysis for project "{project_name}".

Here are {len(project_docs)} documents from this project (showing first 10):

{combined_content}

Analyze what's MISSING and generate specific questions across these categories:

1. PROJECT FUNDAMENTALS
   - Goals, objectives, success criteria
   - Scope, constraints, assumptions

2. STAKEHOLDERS & DECISIONS
   - Key decision makers and their rationale
   - Client/stakeholder expectations

3. PROCESS & METHODOLOGY
   - Approach taken and why
   - Tools, frameworks used

4. OUTCOMES & LEARNINGS
   - Results, deliverables, impact
   - Lessons learned, what would you do differently

5. TECHNICAL DETAILS
   - Implementation specifics
   - Challenges and solutions

Return JSON:
{{
  "project_summary": "Brief summary of what IS documented",
  "completeness_score": 0.0-1.0,
  "gaps": [
    {{
      "type": "category from above",
      "description": "Specific question",
      "severity": "high|medium|low",
      "context": "What in the docs suggests this is missing"
    }}
  ]
}}"""

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # Add project context to gaps
        gaps = result.get('gaps', [])
        for gap in gaps:
            gap['project'] = project_name
            gap['is_standard'] = False
            gap['source'] = 'deep_project_analysis'
            gap['id'] = f"deep_{hash(gap['description']) % 100000}"

        return jsonify({
            'project': project_name,
            'documents_analyzed': len(project_docs),
            'summary': result.get('project_summary', ''),
            'completeness_score': result.get('completeness_score', 0),
            'gaps': gaps,
            'gap_count': len(gaps)
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================================================
# Gamma API Integration for Presentations
# ============================================================================

GAMMA_TEMPLATE_STRUCTURE = """
You are creating a professional business plan presentation with EXACTLY 23 slides.
Follow this EXACT structure from the template:

SLIDE 1: Title slide - Full-screen image background, centered title, subtitle below
SLIDE 2: "Meet the Team" - Grid layout with 4 team member photos and names/roles
SLIDE 3: "Executive Summary" - Two-column layout, key bullet points, metrics highlighted
SLIDE 4: SECTION DIVIDER - "Problem & Opportunity" with dark background
SLIDE 5: "Problem Statement" - Left image, right text with 3-4 key pain points
SLIDE 6: "Background/Context" - Full-width content with supporting data
SLIDE 7: SECTION DIVIDER - "Our Solution" with dark background
SLIDE 8: "Financial Analysis" - Charts, graphs, key financial metrics
SLIDE 9: "Revenue Model" - Pricing tiers or revenue breakdown
SLIDE 10: "Success Metrics/KPIs" - Grid of 4-6 key metrics with icons
SLIDE 11: "Market Size (TAM/SAM/SOM)" - Concentric circles visualization
SLIDE 12: "Competitive Analysis" - Comparison matrix or positioning map
SLIDE 13: "Go-to-Market Strategy" - Timeline or phased approach
SLIDE 14: "Recommendation" - Side-by-side comparison, clear recommendation highlighted
SLIDE 15: SECTION DIVIDER - "Implementation" with dark background
SLIDE 16: "Risk Analysis" - Risk matrix or categorized risks with mitigations
SLIDE 17: "Implementation Timeline" - Gantt chart or phased roadmap
SLIDE 18: "Resource Requirements" - Team structure, budget breakdown
SLIDE 19: "Cost Analysis" - Detailed cost breakdown table
SLIDE 20: "ROI Projections" - Charts showing projected returns
SLIDE 21: "Next Steps" - Numbered action items with owners/dates
SLIDE 22: "Q&A / Discussion" - Simple slide with contact info
SLIDE 23: SECTION DIVIDER - "Appendix" with dark background (or Thank You slide)

Use professional business styling: clean fonts, consistent colors, data-driven visuals.
Each slide should have minimal text - use bullet points, not paragraphs.
"""

@app.route('/api/gamma/generate', methods=['POST'])
def api_gamma_generate():
    """Generate a presentation using Gamma API with template structure"""
    try:
        data = request.json
        gamma_api_key = data.get('gamma_api_key')
        topic = data.get('topic', 'Concierge Medicine Business Plan')
        content = data.get('content', '')
        team_members = data.get('team_members', [])

        if not gamma_api_key:
            return jsonify({'error': 'Gamma API key required'}), 400

        # Build structured input text with slide breaks
        structured_input = build_gamma_structured_input(topic, content, team_members)

        # Call Gamma API
        import requests

        gamma_payload = {
            "inputText": structured_input,
            "textMode": "preserve",  # Keep our structure
            "cardSplit": "inputTextBreaks",  # Use our --- breaks
            "additionalInstructions": GAMMA_TEMPLATE_STRUCTURE,
            "cardOptions": {
                "dimensions": "16:9"
            }
        }

        response = requests.post(
            "https://public-api.gamma.app/v1.0/generations",
            headers={
                "Authorization": f"Bearer {gamma_api_key}",
                "Content-Type": "application/json"
            },
            json=gamma_payload
        )

        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'success': True,
                'gamma_url': result.get('url'),
                'gamma_id': result.get('id'),
                'structured_input_preview': structured_input[:500] + '...'
            })
        else:
            return jsonify({
                'error': f'Gamma API error: {response.status_code}',
                'details': response.text
            }), response.status_code

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


def build_gamma_structured_input(topic: str, content: str, team_members: list) -> str:
    """Build structured input text for Gamma with slide breaks"""

    # If content is provided, use GPT to structure it into the template
    if content:
        prompt = f"""
        Take this content about "{topic}" and structure it into EXACTLY 23 slides following this format.
        Use "---" on its own line to separate slides.

        CONTENT:
        {content}

        TEAM MEMBERS: {json.dumps(team_members) if team_members else 'Not specified'}

        OUTPUT FORMAT (use exactly this structure with --- between slides):

        # {topic}
        [Compelling subtitle]
        ---
        # Meet the Team
        [Team member grid - use provided names or placeholders]
        ---
        # Executive Summary
        - Key point 1
        - Key point 2
        - Key point 3
        ---
        # Problem & Opportunity
        [Section divider]
        ---
        # Problem Statement
        [Pain points from the content]
        ---
        # Background
        [Context and market situation]
        ---
        # Our Solution
        [Section divider]
        ---
        # Financial Analysis
        [Financial data and projections]
        ---
        # Revenue Model
        [How the business makes money]
        ---
        # Success Metrics
        [KPIs and targets]
        ---
        # Market Size
        TAM: [Total Addressable Market]
        SAM: [Serviceable Addressable Market]
        SOM: [Serviceable Obtainable Market]
        ---
        # Competitive Analysis
        [Competitor comparison]
        ---
        # Go-to-Market Strategy
        [Launch and growth plan]
        ---
        # Recommendation
        [Clear recommendation with rationale]
        ---
        # Implementation
        [Section divider]
        ---
        # Risk Analysis
        [Key risks and mitigations]
        ---
        # Implementation Timeline
        [Phased roadmap]
        ---
        # Resource Requirements
        [Team and budget needs]
        ---
        # Cost Analysis
        [Detailed costs]
        ---
        # ROI Projections
        [Return on investment]
        ---
        # Next Steps
        1. [Action item]
        2. [Action item]
        3. [Action item]
        ---
        # Q&A
        [Contact information]
        ---
        # Thank You
        [Closing message]

        Generate the full structured content now:
        """

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000
        )

        return response.choices[0].message.content

    else:
        # Generate content from scratch for the topic
        prompt = f"""
        Create a comprehensive 23-slide business plan presentation about: {topic}

        TEAM MEMBERS: {json.dumps(team_members) if team_members else 'Use placeholder names'}

        Use "---" on its own line to separate each slide.
        Follow a professional business plan structure:
        1. Title
        2. Team
        3. Executive Summary
        4-6. Problem/Opportunity
        7-14. Solution, Financials, Market, Competition
        15-22. Implementation, Risks, Timeline, Resources
        23. Closing

        Make it detailed, data-driven, and professional.
        Include realistic numbers and metrics for {topic}.
        """

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=4000
        )

        return response.choices[0].message.content


@app.route('/api/gamma/preview-structure', methods=['POST'])
def api_gamma_preview_structure():
    """Preview the structured content before sending to Gamma"""
    try:
        data = request.json
        topic = data.get('topic', 'Concierge Medicine Business Plan')
        content = data.get('content', '')
        team_members = data.get('team_members', [])

        structured_input = build_gamma_structured_input(topic, content, team_members)

        # Count slides
        slide_count = structured_input.count('---') + 1

        return jsonify({
            'success': True,
            'slide_count': slide_count,
            'structured_content': structured_input,
            'template_structure': GAMMA_TEMPLATE_STRUCTURE
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500




# ============================================================================
# Document Management Endpoints
# ============================================================================

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """Upload and process a document"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    user_id = request.form.get('user_id', 'default')

    result = document_manager.upload_file(file, user_id)

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/documents/review')
def get_documents_for_review():
    """Get documents needing user review"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    user_id = request.args.get('user_id', 'default')
    review_docs = document_manager.get_documents_for_review(user_id)

    return jsonify({
        'success': True,
        'count': len(review_docs),
        'documents': review_docs
    })


@app.route('/api/documents/<doc_id>/decision', methods=['POST'])
def user_document_decision(doc_id):
    """Process user's decision on a document"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    data = request.get_json()
    decision = data.get('decision')  # 'keep' or 'delete'
    user_id = data.get('user_id', 'default')

    if not decision:
        return jsonify({'success': False, 'error': 'Decision required'}), 400

    result = document_manager.user_decision(doc_id, decision, user_id)
    return jsonify(result)


@app.route('/api/documents/ready-for-rag')
def get_documents_ready_for_rag():
    """Get all work documents ready for RAG processing"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    user_id = request.args.get('user_id', 'default')
    work_docs = document_manager.get_documents_ready_for_rag(user_id)

    return jsonify({
        'success': True,
        'count': len(work_docs),
        'documents': work_docs
    })


@app.route('/api/documents/stats')
def get_document_stats():
    """Get document statistics"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    user_id = request.args.get('user_id', 'default')
    stats = document_manager.get_statistics(user_id)

    return jsonify({
        'success': True,
        'stats': stats
    })


@app.route('/api/documents/categories')
def get_categories():
    """Get available document categories"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    return jsonify({
        'success': True,
        'categories': document_manager.CATEGORIES
    })


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("KNOWLEDGEVAULT - UNIVERSAL WEB APPLICATION")
    print("=" * 80)

    load_data()

    print("=" * 80)
    print("Starting web server...")
    print("=" * 80)
    print("\n Open your browser to: http://localhost:5003")
    print("\nPress Ctrl+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=5003, use_reloader=False)
