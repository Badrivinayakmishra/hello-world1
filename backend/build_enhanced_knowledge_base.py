"""
Build Enhanced Knowledge Base for rishi2205
1. Load LlamaParse documents and deduplicate
2. Filter personal messages from chat
3. Use GPT to cluster/name projects
4. Generate technical + standard questions
5. Build RAG index
"""

import json
import pickle
import re
import os
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import defaultdict
from openai import AzureOpenAI

from config.config import Config
from deduplicate_documents import deduplicate_documents, calculate_completeness_score, PLACEHOLDER_PATTERNS
from message_filter_v2 import filter_messages_v2, calculate_professional_score_v2
from project_clusterer import generate_project_name, load_cache, save_cache

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
        ))

# Target user
TARGET_USER = "rishi2205"

# Projects (spaces) - will be dynamically named by GPT
PROJECTS = [
    "Vibio Health",
    "Startup Team (Eric, Badri, Rishit)",
    "Amgen Project Fall 2024",
    "BEAT at UCLA",
    "UCLA Health Project 2025",
    "Addiction Medicine - Data",
    "BEAT Healthcare Consulting",
    "Concierge Medicine + Addiction Medicine  (UCLA Health)",
    "UCLA Health",
    "Projects Summer"
]


def load_and_deduplicate_llamaparse_docs():
    """Load LlamaParse documents and deduplicate"""

    print("=" * 80)
    print("LOADING AND DEDUPLICATING LLAMAPARSE DOCUMENTS")
    print("=" * 80)

    club_dir = Config.OUTPUT_DIR / "club_project_classification" / "projects"

    project_files = [f"{p}.jsonl" for p in PROJECTS]

    all_docs = []
    project_doc_counts = defaultdict(int)

    for project_file in project_files:
        project_path = club_dir / project_file
        if not project_path.exists():
            continue

        project_name = project_file.replace('.jsonl', '')

        with open(project_path, 'r') as f:
            for line in f:
                doc = json.loads(line)
                if doc.get('metadata', {}).get('parser') == 'llamaparse':
                    doc['metadata']['project'] = project_name
                    all_docs.append(doc)
                    project_doc_counts[project_name] += 1

    print(f"\n📊 Loaded {len(all_docs)} LlamaParse documents from {len(project_doc_counts)} projects")

    # Deduplicate
    deduplicated_docs, dedup_info = deduplicate_documents(all_docs)

    return deduplicated_docs, dedup_info


def load_and_filter_chat_messages():
    """Load chat messages and filter out personal ones"""

    print("\n" + "=" * 80)
    print("LOADING AND FILTERING CHAT MESSAGES")
    print("=" * 80)

    takeout_path = Path("/Users/rishitjain/Downloads/Takeout/Google Chat/Groups")

    if not takeout_path.exists():
        print(f"❌ Takeout not found: {takeout_path}")
        return [], [], [], [], {}

    user_messages = []
    space_docs = []
    user_spaces = []
    needs_review_messages = []
    project_name_map = {}  # space_id -> generated project name

    for space_dir in takeout_path.iterdir():
        if not space_dir.is_dir():
            continue
        if space_dir.name.startswith("DM "):
            continue

        group_info_file = space_dir / "group_info.json"
        if not group_info_file.exists():
            continue

        with open(group_info_file, 'r') as f:
            group_info = json.load(f)

        space_name = group_info.get('name', space_dir.name)
        members = group_info.get('members', [])

        # Check if rishi2205 is in this space
        is_member = any(TARGET_USER in m.get('email', '').lower() for m in members)

        if not is_member:
            continue

        # Read messages
        messages_file = space_dir / "messages.json"
        space_messages = []
        space_files = []

        if messages_file.exists():
            with open(messages_file, 'r') as f:
                messages = json.load(f)

            for msg in messages.get('messages', []):
                text = msg.get('text', '')
                if not text or len(text.strip()) < 5:
                    continue

                space_messages.append({
                    'content': text,
                    'sender': msg.get('creator', {}).get('email', ''),
                    'timestamp': msg.get('created_date', '')
                })

                # Collect file names
                for att in msg.get('attached_files', []):
                    fname = att.get('export_name', '')
                    if fname:
                        space_files.append(fname)

        if len(space_messages) < 3:
            continue

        # Generate GPT-based project name
        print(f"\n📂 Processing space: {space_name}")
        naming_result = generate_project_name(
            space_dir.name, space_name, space_messages, space_files
        )
        generated_name = naming_result['generated_name']
        project_name_map[space_dir.name] = generated_name
        print(f"   ✓ Project name: {generated_name}")

        # Filter messages with improved v2 filter (uses GPT for uncertain ones)
        filter_result = filter_messages_v2(space_messages, use_gpt_for_uncertain=True)
        print(f"   ✓ Messages: {filter_result['stats']['professional']} professional, "
              f"{filter_result['stats']['personal']} personal, "
              f"{filter_result['stats']['needs_review']} need review")

        user_spaces.append({
            'space_id': space_dir.name,
            'space_name': space_name,
            'generated_name': generated_name,
            'members': [m.get('email', '') for m in members],
            'member_count': len(members),
            'message_stats': filter_result['stats']
        })

        # Process professional messages
        for msg_result in filter_result['professional']:
            original_msg = msg_result.get('original_message', {})
            creator_email = original_msg.get('sender', '')
            text = original_msg.get('content', '') or msg_result.get('content', '')
            timestamp = original_msg.get('timestamp', '')

            msg_data = {
                'content': text,
                'metadata': {
                    'space': generated_name,  # Use generated name
                    'space_id': space_dir.name,
                    'sender': creator_email,
                    'timestamp': timestamp,
                    'type': 'message',
                    'professional_score': msg_result.get('professional_score', 75)
                }
            }

            if TARGET_USER in creator_email.lower():
                user_messages.append(msg_data)

            space_docs.append(msg_data)

        # Track messages needing review (should be 0 with v2 filter + GPT)
        for msg_result in filter_result['needs_review']:
            original_msg = msg_result.get('original_message', {})
            needs_review_messages.append({
                'content': original_msg.get('content', '') or msg_result.get('content', ''),
                'space': generated_name,
                'space_id': space_dir.name,
                'sender': original_msg.get('sender', ''),
                'professional_score': msg_result.get('professional_score', 50),
                'reasons': msg_result.get('reasons', [])
            })

    print(f"\n✅ Found {len(user_spaces)} spaces with {TARGET_USER}")
    print(f"✅ Found {len(user_messages)} professional messages FROM {TARGET_USER}")
    print(f"✅ Found {len(space_docs)} professional messages total")
    print(f"⚠️  {len(needs_review_messages)} messages need user review")

    return user_messages, space_docs, user_spaces, needs_review_messages, project_name_map


def generate_technical_questions(llamaparse_docs, project_name_map):
    """Generate technical questions based on document content using GPT"""

    print("\n" + "=" * 80)
    print("GENERATING TECHNICAL QUESTIONS")
    print("=" * 80)

    technical_questions = []

    # Group docs by project
    docs_by_project = defaultdict(list)
    for doc in llamaparse_docs:
        project = doc.get('metadata', {}).get('project', 'Unknown')
        docs_by_project[project].append(doc)

    for project_name, docs in docs_by_project.items():
        if not docs:
            continue

        print(f"\n📂 Analyzing: {project_name}")

        # Combine document content for analysis (limit to avoid token limits)
        combined_content = ""
        for doc in docs[:5]:  # Limit to 5 docs per project
            content = doc.get('content', '')[:2000]
            file_name = doc.get('metadata', {}).get('file_name', 'Unknown')
            combined_content += f"\n\n--- {file_name} ---\n{content}"

        if len(combined_content) < 100:
            continue

        # Use GPT to generate technical questions
        prompt = f"""Analyze these project documents and generate 5-7 specific technical questions about DECISIONS and TRADEOFFS.

Project: {project_name}

Documents:
{combined_content[:4000]}

FOCUS ON THESE QUESTION TYPES:
1. WHY questions - "Why did the team decide to use X instead of Y?"
2. TRADEOFF questions - "What were the tradeoffs considered when choosing X?"
3. ALTERNATIVE questions - "What alternatives were evaluated before selecting X?"
4. ASSUMPTION questions - "What assumptions underlie the decision to do X?"
5. METHODOLOGY questions - "Why was this particular methodology/approach chosen?"
6. DATA questions - "What data sources informed the decision on X?"
7. CHALLENGE questions - "What challenges influenced the choice of X?"

Examples of GOOD questions:
- Why did the team choose to focus on the NICU market instead of other hospital units?
- What tradeoffs were considered when deciding the pricing model?
- Why was TAM calculated using X methodology instead of Y?
- What assumptions drove the 15% growth rate projection?
- Why did the team prioritize feature A over feature B?

BAD questions to avoid:
- What is the goal of the project? (too generic)
- What are the success metrics? (too generic)
- How much is the market size? (just asks for a number)

Output format - one question per line, no numbering or bullets:"""

        try:
            response = client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You generate specific technical questions about project documents to identify knowledge gaps."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=500
            )

            questions_text = response.choices[0].message.content
            questions = [q.strip() for q in questions_text.strip().split('\n') if q.strip() and '?' in q]

            for q in questions[:5]:  # Limit to 5 questions per project
                # Clean up the question
                q = re.sub(r'^[\d\.\-\*]+\s*', '', q)  # Remove numbering
                q = q.strip()

                if len(q) > 20:
                    technical_questions.append({
                        'type': 'technical',
                        'description': q,
                        'project': project_name,
                        'severity': 'medium',
                        'is_standard': False,
                        'source': 'gpt_analysis'
                    })

            print(f"   ✓ Generated {len(questions)} questions")

        except Exception as e:
            print(f"   ❌ Error generating questions: {e}")

    print(f"\n✅ Generated {len(technical_questions)} technical questions total")
    return technical_questions


def create_enhanced_gap_analysis(llamaparse_docs, user_spaces, project_name_map):
    """Create gap analysis with standard + technical questions"""

    print("\n" + "=" * 80)
    print("CREATING ENHANCED GAP ANALYSIS")
    print("=" * 80)

    gaps = []

    # Get unique project names (using generated names where available)
    project_names = set()
    for space in user_spaces:
        project_names.add(space.get('generated_name', space.get('space_name')))

    for doc in llamaparse_docs:
        project_names.add(doc.get('metadata', {}).get('project', 'Unknown'))

    # Standard questions for each project
    for project_name in project_names:
        if project_name == 'Unknown':
            continue

        # Goal question
        gaps.append({
            'type': 'project_goal',
            'description': f'What was the main goal of {project_name}?',
            'project': project_name,
            'severity': 'high',
            'is_standard': True
        })

        # Success criteria
        gaps.append({
            'type': 'success_criteria',
            'description': f'What were the success metrics for {project_name}?',
            'project': project_name,
            'severity': 'high',
            'is_standard': True
        })

        # Outcome
        gaps.append({
            'type': 'project_outcome',
            'description': f'What was the final deliverable for {project_name}?',
            'project': project_name,
            'severity': 'medium',
            'is_standard': True
        })

    # Generate technical questions
    technical_questions = generate_technical_questions(llamaparse_docs, project_name_map)
    gaps.extend(technical_questions)

    # Document-specific gaps (placeholders, missing data)
    for doc in llamaparse_docs:
        content = doc.get('content', '')
        file_name = doc.get('metadata', {}).get('file_name', 'Unknown')
        project = doc.get('metadata', {}).get('project', 'Unknown')

        for pattern in PLACEHOLDER_PATTERNS[:7]:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                gap_desc = f"Document '{file_name}' contains placeholder '{matches[0]}'"
                if not any(g['description'] == gap_desc for g in gaps):
                    gaps.append({
                        'type': 'missing_value',
                        'description': gap_desc,
                        'file': file_name,
                        'project': project,
                        'severity': 'high',
                        'is_standard': False
                    })

    # Deduplicate
    seen = set()
    unique_gaps = []
    for gap in gaps:
        key = (gap['description'], gap.get('project', ''))
        if key not in seen:
            seen.add(key)
            unique_gaps.append(gap)

    print(f"\n✅ Created {len(unique_gaps)} knowledge gaps:")
    print(f"   • Standard questions: {len([g for g in unique_gaps if g.get('is_standard')])}")
    print(f"   • Technical questions: {len([g for g in unique_gaps if g.get('source') == 'gpt_analysis'])}")
    print(f"   • Missing value gaps: {len([g for g in unique_gaps if g.get('type') == 'missing_value'])}")

    return unique_gaps


def build_search_index(llamaparse_docs, user_messages, space_docs, project_name_map):
    """Build combined search index with filtered, deduplicated docs"""

    print("\n" + "=" * 80)
    print("BUILDING SEARCH INDEX")
    print("=" * 80)

    all_docs = []
    doc_id = 0

    # Add deduplicated LlamaParse docs
    for doc in llamaparse_docs:
        doc_id += 1
        project = doc['metadata'].get('project', 'Unknown')

        all_docs.append({
            'doc_id': f"llamaparse_{doc_id}",
            'content': doc['content'],
            'metadata': doc['metadata'],
            'cluster_label': project,
            'priority': 1,
            'is_latest': True
        })

    # Add user messages (filtered)
    for msg in user_messages:
        doc_id += 1
        all_docs.append({
            'doc_id': f"user_msg_{doc_id}",
            'content': msg['content'],
            'metadata': msg['metadata'],
            'cluster_label': msg['metadata'].get('space', 'Unknown'),
            'priority': 2,
            'is_latest': True
        })

    # Add space messages (filtered)
    for msg in space_docs:
        doc_id += 1
        all_docs.append({
            'doc_id': f"space_msg_{doc_id}",
            'content': msg['content'],
            'metadata': msg['metadata'],
            'cluster_label': msg['metadata'].get('space', 'Unknown'),
            'priority': 3,
            'is_latest': True
        })

    print(f"\n📊 Building index for {len(all_docs)} total items:")
    print(f"   - {len(llamaparse_docs)} deduplicated LlamaParse documents")
    print(f"   - {len(user_messages)} filtered messages from {TARGET_USER}")
    print(f"   - {len(space_docs)} filtered team messages")

    # Build TF-IDF
    doc_contents = [d['content'] for d in all_docs]
    doc_ids = [d['doc_id'] for d in all_docs]

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        stop_words='english',
        min_df=1,
        max_df=0.95
    )

    doc_vectors = vectorizer.fit_transform(doc_contents)

    print(f"  ✓ Created {doc_vectors.shape[0]} document vectors")
    print(f"  ✓ Feature dimensions: {doc_vectors.shape[1]}")

    doc_index = {d['doc_id']: d for d in all_docs}

    search_index = {
        'vectorizer': vectorizer,
        'doc_vectors': doc_vectors,
        'doc_ids': doc_ids,
        'doc_index': doc_index,
        'metadata': {
            'total_documents': len(all_docs),
            'llamaparse_docs': len(llamaparse_docs),
            'user_messages': len(user_messages),
            'space_messages': len(space_docs),
            'target_user': TARGET_USER,
            'source': 'club_enhanced',
            'deduplicated': True,
            'filtered': True
        }
    }

    return search_index, all_docs


def save_knowledge_base(search_index, user_spaces, gaps, dedup_info, needs_review_messages, project_name_map):
    """Save the enhanced knowledge base"""

    print("\n" + "=" * 80)
    print("SAVING KNOWLEDGE BASE")
    print("=" * 80)

    output_dir = Path('/Users/rishitjain/Downloads/knowledgevault_backend/club_data')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save search index
    index_file = output_dir / 'search_index.pkl'
    if index_file.exists():
        backup = output_dir / 'search_index_backup.pkl'
        index_file.rename(backup)

    with open(index_file, 'wb') as f:
        pickle.dump(search_index, f)
    print(f"✓ Saved search index")

    # Save user spaces (with generated names)
    with open(output_dir / 'user_spaces.json', 'w') as f:
        json.dump(user_spaces, f, indent=2)
    print(f"✓ Saved user spaces")

    # Save gaps
    with open(output_dir / 'knowledge_gaps.json', 'w') as f:
        json.dump(gaps, f, indent=2)
    print(f"✓ Saved {len(gaps)} knowledge gaps")

    # Save deduplication info
    with open(output_dir / 'deduplication_info.json', 'w') as f:
        json.dump(dedup_info, f, indent=2)
    print(f"✓ Saved deduplication info")

    # Save messages needing review (for frontend)
    with open(output_dir / 'messages_needs_review.json', 'w') as f:
        json.dump(needs_review_messages, f, indent=2)
    print(f"✓ Saved {len(needs_review_messages)} messages for review")

    # Save project name mapping
    with open(output_dir / 'project_name_map.json', 'w') as f:
        json.dump(project_name_map, f, indent=2)
    print(f"✓ Saved project name mapping")

    # Save metadata
    metadata = {
        'target_user': TARGET_USER,
        'total_docs': search_index['metadata']['total_documents'],
        'llamaparse_docs': search_index['metadata']['llamaparse_docs'],
        'user_messages': search_index['metadata']['user_messages'],
        'spaces': len(user_spaces),
        'gaps_identified': len(gaps),
        'messages_need_review': len(needs_review_messages),
        'source': 'club_enhanced',
        'deduplicated': True,
        'filtered': True,
        'original_doc_count': dedup_info['original_count'],
        'removed_duplicates': dedup_info['removed_count']
    }

    with open(output_dir / 'knowledge_base_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved metadata")

    print(f"\n📁 All files saved to: {output_dir}")


def main():
    """Main pipeline"""

    print("\n🎯 ENHANCED KNOWLEDGE BASE BUILDER")
    print("   For user: rishi2205")
    print("   Features: Deduplication + Message Filtering + GPT Clustering + Technical Questions\n")

    # Step 1: Load and deduplicate LlamaParse documents
    llamaparse_docs, dedup_info = load_and_deduplicate_llamaparse_docs()

    if not llamaparse_docs:
        print("❌ No documents found!")
        return

    # Step 2: Load and filter chat messages + GPT project naming
    user_messages, space_docs, user_spaces, needs_review, project_name_map = load_and_filter_chat_messages()

    if not user_spaces:
        print("❌ No spaces found for user!")
        return

    # Step 3: Build search index
    search_index, all_docs = build_search_index(llamaparse_docs, user_messages, space_docs, project_name_map)

    # Step 4: Create enhanced gap analysis
    gaps = create_enhanced_gap_analysis(llamaparse_docs, user_spaces, project_name_map)

    # Step 5: Save everything
    save_knowledge_base(search_index, user_spaces, gaps, dedup_info, needs_review, project_name_map)

    print("\n" + "=" * 80)
    print("✅ ENHANCED KNOWLEDGE BASE COMPLETE!")
    print("=" * 80)

    print(f"\n📊 Summary:")
    print(f"   • User: {TARGET_USER}")
    print(f"   • Original LlamaParse Docs: {dedup_info['original_count']}")
    print(f"   • After Deduplication: {dedup_info['deduplicated_count']}")
    print(f"   • Duplicates Removed: {dedup_info['removed_count']}")
    print(f"   • Professional Messages: {len(user_messages) + len(space_docs)}")
    print(f"   • Messages Need Review: {len(needs_review)}")
    print(f"   • Projects: {len(user_spaces)}")
    print(f"   • Knowledge Gaps: {len(gaps)}")
    print(f"      - Standard: {len([g for g in gaps if g.get('is_standard')])}")
    print(f"      - Technical: {len([g for g in gaps if g.get('source') == 'gpt_analysis'])}")

    print(f"\n🚀 Next: Restart app_universal.py and test!")


if __name__ == "__main__":
    main()
