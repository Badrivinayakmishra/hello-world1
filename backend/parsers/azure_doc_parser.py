"""
Azure Mistral Document AI Parser
Uses Azure's mistral-document-ai-2505 model for document parsing
"""

import os
import base64
from pathlib import Path
from typing import Dict, Optional
import warnings

warnings.filterwarnings('ignore')

try:
    from openai import AzureOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class AzureDocumentParser:
    """Parse documents using Azure Mistral Document AI"""

    def __init__(self, config=None):
        """
        Initialize Azure Document Parser

        Args:
            config: Configuration object with Azure OpenAI settings
        """
        self.config = config
        self.client = None

        if not HAS_OPENAI:
            raise ImportError("openai not installed. Run: pip install openai")

        # Initialize Azure OpenAI client
        self._initialize_client()

        # Supported formats for Azure Document AI
        self.supported_formats = ['.pdf', '.pptx', '.xlsx', '.docx', '.txt', '.html', '.xml', '.png', '.jpg', '.jpeg']

    def _initialize_client(self):
        """Initialize Azure OpenAI client"""
        # Get Azure config from environment or config object
        if self.config:
            api_key = getattr(self.config, 'AZURE_OPENAI_API_KEY', None)
            endpoint = getattr(self.config, 'AZURE_OPENAI_ENDPOINT', None)
            api_version = getattr(self.config, 'AZURE_API_VERSION', None)
        else:
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
            api_version = os.getenv('AZURE_API_VERSION', '2024-12-01-preview')

        if not api_key or not endpoint:
            raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set")

        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        print("✓ Azure Document AI client initialized")

    def can_parse(self, file_path: str) -> bool:
        """Check if file format is supported"""
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_formats

    def parse(self, file_path: str) -> Optional[Dict]:
        """
        Parse a document using Azure Mistral Document AI

        Returns:
            Dict with 'content' and 'metadata' or None if parsing failed
        """
        if not os.path.exists(file_path):
            print(f"  ⚠ File not found: {file_path}")
            return None

        ext = Path(file_path).suffix.lower()
        if ext not in self.supported_formats:
            print(f"  ⚠ Unsupported file format: {ext}")
            return None

        try:
            file_name = Path(file_path).name
            print(f"  📄 Parsing {file_name} with Azure Mistral Document AI...")

            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # For text files, parse directly
            if ext in ['.txt', '.html', '.xml']:
                content = file_content.decode('utf-8', errors='ignore')
                return {
                    'content': content,
                    'raw_content': content,
                    'metadata': {
                        'file_type': ext.lstrip('.'),
                        'file_name': file_name,
                        'total_chars': len(content),
                        'parser': 'azure_document_ai',
                        'model': 'mistral-document-ai-2505'
                    }
                }

            # For binary files (PDF, Office docs, images), use Azure Document AI
            base64_content = base64.b64encode(file_content).decode('utf-8')

            # Call Azure Mistral Document AI
            response = self.client.chat.completions.create(
                model="mistral-document-ai-2505",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a document parser. Extract ALL text content from the document.

For each document, provide:
1. Main text content (preserve structure and formatting)
2. Tables (extract data in markdown table format)
3. Lists (preserve bullet points and numbering)
4. Headers and sections (maintain hierarchy)
5. Important metadata (dates, names, numbers)

Return clean, well-structured text that preserves the document's organization."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Parse this {ext.lstrip('.')} file and extract all content:"
                            },
                            {
                                "type": "document",
                                "document": {
                                    "data": base64_content,
                                    "format": ext.lstrip('.')
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=16000
            )

            # Extract parsed content
            parsed_content = response.choices[0].message.content

            if not parsed_content or len(parsed_content.strip()) < 10:
                print(f"  ⚠ No meaningful content extracted from {file_name}")
                return None

            return {
                'content': parsed_content,
                'raw_content': parsed_content,
                'metadata': {
                    'file_type': ext.lstrip('.'),
                    'file_name': file_name,
                    'total_chars': len(parsed_content),
                    'parser': 'azure_document_ai',
                    'model': 'mistral-document-ai-2505',
                    'tokens_used': response.usage.total_tokens if hasattr(response, 'usage') else None
                }
            }

        except Exception as e:
            print(f"  ✗ Error parsing {Path(file_path).name} with Azure Document AI: {e}")
            import traceback
            traceback.print_exc()
            return None

    def parse_batch(self, file_paths: list) -> Dict[str, Optional[Dict]]:
        """
        Parse multiple documents

        Args:
            file_paths: List of file paths to parse

        Returns:
            Dict mapping file paths to parse results
        """
        results = {}
        for file_path in file_paths:
            results[file_path] = self.parse(file_path)
        return results
