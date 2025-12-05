"""
Script to migrate all OpenAI API calls to Azure OpenAI.
Run this script to update all Python files in the backend.
"""

import os
import re
from pathlib import Path

# Azure OpenAI configuration to inject
AZURE_CONFIG = '''
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"
'''

def migrate_file(filepath: str) -> bool:
    """Migrate a single file to use Azure OpenAI"""

    # Skip venv directories
    if 'venv' in filepath or 'site-packages' in filepath:
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 1. Replace import statement
        content = re.sub(
            r'from openai import OpenAI',
            'from openai import AzureOpenAI',
            content
        )

        # 2. Add Azure config if AzureOpenAI is now imported
        if 'from openai import AzureOpenAI' in content:
            # Check if config already exists
            if 'AZURE_OPENAI_ENDPOINT' not in content:
                # Add import os if not present
                if 'import os' not in content:
                    content = 'import os\n' + content

                # Add config after imports
                lines = content.split('\n')
                import_end = 0
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        import_end = i

                lines.insert(import_end + 1, AZURE_CONFIG)
                content = '\n'.join(lines)

        # 3. Replace OpenAI client initialization
        content = re.sub(
            r'OpenAI\s*\(\s*api_key\s*=\s*[^\)]+\)',
            '''AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )''',
            content
        )

        # 4. Replace model names with Azure deployment
        content = re.sub(r'model\s*=\s*["\']gpt-4o["\']', 'model=AZURE_CHAT_DEPLOYMENT', content)
        content = re.sub(r'model\s*=\s*["\']gpt-4o-mini["\']', 'model=AZURE_CHAT_DEPLOYMENT', content)
        content = re.sub(r'model\s*=\s*["\']gpt-4["\']', 'model=AZURE_CHAT_DEPLOYMENT', content)
        content = re.sub(r'model\s*=\s*["\']gpt-3.5-turbo["\']', 'model=AZURE_CHAT_DEPLOYMENT', content)

        # Write back if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def main():
    """Migrate all Python files"""
    backend_dir = Path(__file__).parent

    # Find all Python files (excluding venv)
    python_files = []
    for root, dirs, files in os.walk(backend_dir):
        # Skip venv directories
        dirs[:] = [d for d in dirs if 'venv' not in d.lower()]

        for file in files:
            if file.endswith('.py') and file != 'migrate_to_azure.py':
                python_files.append(os.path.join(root, file))

    print(f"Found {len(python_files)} Python files to check")

    migrated = 0
    for filepath in python_files:
        if migrate_file(filepath):
            print(f"✓ Migrated: {filepath}")
            migrated += 1

    print(f"\n✓ Migration complete! {migrated} files updated.")
    print("\nNote: You may need to create an embedding deployment in Azure for embeddings to work.")
    print("The chat completion deployment 'gpt-5-chat' will be used for all LLM calls.")


if __name__ == '__main__':
    main()
