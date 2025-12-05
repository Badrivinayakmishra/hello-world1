"""
LlamaParse Document Parser with GPT-4o-mini Processing
Parses all document types using LlamaParse and processes with GPT-4o-mini
"""

import os
from pathlib import Path
from typing import Dict, Optional, List
import warnings

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"

warnings.filterwarnings('ignore')

try:
    from llama_parse import LlamaParse
    HAS_LLAMAPARSE = True
except ImportError:
    HAS_LLAMAPARSE = False

try:
    from openai import AzureOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class LlamaParseDocumentParser:
    """Parse documents using LlamaParse and process with GPT-4o-mini"""

    def __init__(self, config):
        """
        Initialize LlamaParse parser

        Args:
            config: Configuration object with API keys and settings
        """
        self.config = config
        self.parser = None
        self.openai_client = None

        if not HAS_LLAMAPARSE:
            raise ImportError("llama-parse not installed. Run: pip install llama-parse")

        if not HAS_OPENAI:
            raise ImportError("openai not installed. Run: pip install openai")

        # Initialize LlamaParse
        self._initialize_parser()

        # Initialize OpenAI client
        self._initialize_openai()

        self.supported_formats = ['.pdf', '.pptx', '.xlsx', '.docx', '.txt', '.html', '.xml']

    def _initialize_parser(self):
        """Initialize LlamaParse parser"""
        api_key = self.config.LLAMAPARSE_API_KEY
        if not api_key:
            raise ValueError("LLAMAPARSE_API_KEY not set in config")

        self.parser = LlamaParse(
            api_key=api_key,
            result_type=self.config.LLAMAPARSE_RESULT_TYPE,
            verbose=self.config.LLAMAPARSE_VERBOSE
        )
        print("✓ LlamaParse initialized")

    def _initialize_openai(self):
        """Initialize OpenAI client"""
        api_key = self.config.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in config")

        self.openai_client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
        print("✓ OpenAI client initialized")

    def can_parse(self, file_path: str) -> bool:
        """Check if file format is supported"""
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_formats

    def parse(self, file_path: str) -> Optional[Dict]:
        """
        Parse a document using LlamaParse and process with GPT-4o-mini

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
            # Parse with LlamaParse
            documents = self.parser.load_data(file_path)

            if not documents:
                print(f"  ⚠ No content extracted from {Path(file_path).name}")
                return None

            # Combine all document texts
            raw_content = '\n\n'.join(doc.text for doc in documents)

            # Process with GPT-4o-mini to extract structured information
            processed_content = self._process_with_llm(raw_content, file_path)

            return {
                'content': processed_content,
                'raw_content': raw_content,
                'metadata': {
                    'file_type': ext.lstrip('.'),
                    'file_name': Path(file_path).name,
                    'num_documents': len(documents),
                    'total_chars': len(raw_content),
                    'processed_chars': len(processed_content),
                    'parser': 'llamaparse',
                    'llm_processor': self.config.LLM_MODEL
                }
            }

        except Exception as e:
            print(f"  ✗ Error parsing {Path(file_path).name}: {e}")
            return None

    def _process_with_llm(self, content: str, file_path: str) -> str:
        """
        Process parsed content with GPT-4o-mini to extract key information

        Args:
            content: Raw parsed content from LlamaParse
            file_path: Path to the original file

        Returns:
            Processed and structured content
        """
        try:
            file_name = Path(file_path).name
            file_type = Path(file_path).suffix.lstrip('.')

            # Create prompt for GPT-4o-mini
            prompt = f"""You are a document analyzer. Extract and structure the key information from this {file_type} document: "{file_name}".

Document Content:
{content[:8000]}  # Limit to avoid token limits

Please provide:
1. A concise summary (2-3 sentences)
2. Main topics and themes
3. Key entities (people, organizations, projects)
4. Important dates and deadlines (if any)
5. Action items or decisions (if any)

Format your response in a clear, structured way that preserves all important information."""

            # Call GPT-4o-mini
            response = self.openai_client.chat.completions.create(
                model=self.config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert document analyzer that extracts and structures key information from documents."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )

            processed_text = response.choices[0].message.content

            # Combine original content with processed insights
            final_content = f"""DOCUMENT: {file_name}

STRUCTURED ANALYSIS:
{processed_text}

---

FULL CONTENT:
{content}"""

            return final_content

        except Exception as e:
            print(f"  ⚠ LLM processing failed: {e}")
            # Return original content if processing fails
            return content

    def parse_batch(self, file_paths: List[str]) -> Dict[str, Optional[Dict]]:
        """
        Parse multiple documents

        Args:
            file_paths: List of file paths to parse

        Returns:
            Dictionary mapping file paths to parsed results
        """
        results = {}

        for file_path in file_paths:
            print(f"\n📄 Parsing: {Path(file_path).name}")
            result = self.parse(file_path)
            results[file_path] = result

            if result:
                print(f"  ✓ Success: {result['metadata']['processed_chars']:,} chars")
            else:
                print(f"  ✗ Failed to parse")

        return results


if __name__ == "__main__":
    from config.config import Config

    # Test the parser
    parser = LlamaParseDocumentParser(Config)
    print(f"Supported formats: {parser.supported_formats}")

    # Test with a sample file
    test_file = "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAn7sv4eE/File-Timeline - BEAT Healthcare Consulting.pptx"

    if os.path.exists(test_file):
        result = parser.parse(test_file)
        if result:
            print(f"\n✓ Extracted {len(result['content'])} characters")
            print(f"\nPreview:")
            print("="*80)
            print(result['content'][:500])
            print("="*80)
    else:
        print(f"Test file not found: {test_file}")
