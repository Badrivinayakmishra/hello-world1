"""
GPT-Based Project Clustering Module
Uses GPT to analyze messages and files to generate concise project names.

Strategy:
1. Sample messages and file names from each space/group
2. Send to GPT for analysis
3. Get back a short, concise project name (2-5 words max)
4. Cache results to avoid repeated API calls
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from openai import AzureOpenAI

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Initialize OpenAI client
client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        ))

# Cache file for project names
CACHE_FILE = Path('/Users/rishitjain/Downloads/knowledgevault_backend/club_data/project_names_cache.json')


def load_cache() -> Dict:
    """Load cached project names"""
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_cache(cache: Dict):
    """Save project names to cache"""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def extract_sample_content(messages: List[Dict], files: List[str], max_messages: int = 10) -> str:
    """
    Extract sample content from messages and files for GPT analysis.
    """
    content_parts = []

    # Sample messages (prioritize longer, more informative ones)
    sorted_messages = sorted(messages, key=lambda x: len(x.get('content', '')), reverse=True)
    for msg in sorted_messages[:max_messages]:
        text = msg.get('content', '')[:200]
        if len(text) > 20:  # Skip very short messages
            content_parts.append(f"Message: {text}")

    # Include file names
    if files:
        file_list = ', '.join(files[:15])
        content_parts.append(f"Files shared: {file_list}")

    return '\n'.join(content_parts)


def generate_project_name(space_id: str, space_name: str, messages: List[Dict],
                          files: List[str], use_cache: bool = True) -> Dict:
    """
    Generate a concise project name using GPT analysis.

    Returns:
        {
            'original_name': str,
            'generated_name': str,
            'confidence': float,
            'method': str
        }
    """
    # Check cache first
    cache = load_cache()
    cache_key = f"{space_id}_{len(messages)}"

    if use_cache and cache_key in cache:
        return cache[cache_key]

    # Extract sample content
    sample_content = extract_sample_content(messages, files)

    if not sample_content:
        return {
            'original_name': space_name,
            'generated_name': space_name,
            'confidence': 0.0,
            'method': 'fallback_empty'
        }

    prompt = f"""Analyze this chat group's content and generate a SHORT project name (2-5 words maximum).

Original group name: {space_name}

Sample content:
{sample_content}

Rules:
1. Output ONLY the project name, nothing else
2. Maximum 5 words
3. Be specific and descriptive
4. Use title case
5. No punctuation except necessary hyphens
6. If it's clearly a company/organization name, keep it
7. Focus on the MAIN project or purpose

Examples of good names:
- UCLA Health NICU Analysis
- Vibio Health Startup
- BEAT Consulting
- Amgen Market Research
- Healthcare Business Plan

Output only the project name:"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a project naming assistant. Output only short, concise project names (2-5 words). No explanations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=20
        )

        generated_name = response.choices[0].message.content.strip()

        # Clean up the name
        generated_name = generated_name.strip('"\'')
        generated_name = ' '.join(generated_name.split())  # Normalize whitespace

        # Truncate if too long
        words = generated_name.split()
        if len(words) > 5:
            generated_name = ' '.join(words[:5])

        result = {
            'original_name': space_name,
            'generated_name': generated_name,
            'confidence': 0.85,
            'method': 'gpt'
        }

        # Cache the result
        cache[cache_key] = result
        save_cache(cache)

        return result

    except Exception as e:
        print(f"GPT project naming error: {e}")
        return {
            'original_name': space_name,
            'generated_name': space_name,
            'confidence': 0.0,
            'method': 'error_fallback'
        }


def cluster_projects_from_takeout(takeout_path: Path) -> Dict[str, Dict]:
    """
    Process all Google Chat spaces and generate project names.

    Returns:
        {
            space_id: {
                'original_name': str,
                'generated_name': str,
                'message_count': int,
                'file_count': int,
                'members': List[str],
                'confidence': float
            }
        }
    """
    print("=" * 80)
    print("GPT-BASED PROJECT CLUSTERING")
    print("=" * 80)

    groups_path = takeout_path / "Groups"
    if not groups_path.exists():
        print(f"❌ Groups not found: {groups_path}")
        return {}

    results = {}

    for space_dir in groups_path.iterdir():
        if not space_dir.is_dir():
            continue

        # Skip DMs
        if space_dir.name.startswith("DM "):
            continue

        space_id = space_dir.name

        # Read group info
        group_info_file = space_dir / "group_info.json"
        if not group_info_file.exists():
            continue

        with open(group_info_file, 'r') as f:
            group_info = json.load(f)

        space_name = group_info.get('name', space_dir.name)
        members = [m.get('email', '') for m in group_info.get('members', [])]

        # Read messages
        messages = []
        files = []
        messages_file = space_dir / "messages.json"

        if messages_file.exists():
            with open(messages_file, 'r') as f:
                msg_data = json.load(f)

            for msg in msg_data.get('messages', []):
                text = msg.get('text', '')
                if text and len(text.strip()) > 5:
                    messages.append({
                        'content': text,
                        'sender': msg.get('creator', {}).get('email', '')
                    })

                # Extract attached file names
                for attachment in msg.get('attached_files', []):
                    fname = attachment.get('export_name', '')
                    if fname:
                        files.append(fname)

        if len(messages) < 3:
            # Too few messages, use original name
            results[space_id] = {
                'original_name': space_name,
                'generated_name': space_name,
                'message_count': len(messages),
                'file_count': len(files),
                'members': members,
                'confidence': 0.0,
                'method': 'too_few_messages'
            }
            continue

        # Generate project name with GPT
        print(f"\n📂 Processing: {space_name}")
        print(f"   Messages: {len(messages)}, Files: {len(files)}")

        naming_result = generate_project_name(space_id, space_name, messages, files)

        results[space_id] = {
            'original_name': space_name,
            'generated_name': naming_result['generated_name'],
            'message_count': len(messages),
            'file_count': len(files),
            'members': members,
            'confidence': naming_result['confidence'],
            'method': naming_result['method']
        }

        print(f"   ✓ Generated: {naming_result['generated_name']}")

    return results


def batch_rename_projects(spaces: List[Dict], force_regenerate: bool = False) -> List[Dict]:
    """
    Batch process multiple spaces to generate project names.
    More efficient than individual calls.
    """
    if force_regenerate:
        # Clear cache
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()

    results = []

    for space in spaces:
        space_id = space.get('space_id', '')
        space_name = space.get('space_name', '')
        messages = space.get('messages', [])
        files = space.get('files', [])

        result = generate_project_name(space_id, space_name, messages, files)
        result['space_id'] = space_id
        results.append(result)

    return results


if __name__ == "__main__":
    # Test with actual takeout data
    takeout_path = Path("/Users/rishitjain/Downloads/Takeout/Google Chat")

    if not takeout_path.exists():
        print(f"❌ Takeout not found: {takeout_path}")
    else:
        results = cluster_projects_from_takeout(takeout_path)

        print("\n" + "=" * 80)
        print("PROJECT CLUSTERING RESULTS")
        print("=" * 80)

        print(f"\n📊 Processed {len(results)} spaces\n")

        for space_id, info in results.items():
            original = info['original_name']
            generated = info['generated_name']
            changed = "✓ RENAMED" if original != generated else "  (same)"

            print(f"{changed} {original[:40]:<40} → {generated}")

        # Save results
        output_file = Path('/Users/rishitjain/Downloads/knowledgevault_backend/club_data/project_clusters.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Saved to: {output_file}")
