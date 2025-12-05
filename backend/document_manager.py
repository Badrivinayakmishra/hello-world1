"""
Document Management System
Handles file uploads, classification, parsing, and deletion
"""

import os
import json
import pickle
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from werkzeug.utils import secure_filename
from openai import AzureOpenAI

# Import parsers
from parsers.llamaparse_parser import LlamaParseDocumentParser as LlamaParseParser

# Import classifier
from classification.work_personal_classifier import WorkPersonalClassifier

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"



class DocumentManager:
    """Manages document lifecycle: upload → parse → classify → store"""

    UPLOAD_FOLDER = Path("club_data/uploads")
    CLASSIFIED_FOLDER = Path("club_data/classified")
    ALLOWED_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'txt', 'ppt', 'pptx',
        'xls', 'xlsx', 'csv', 'html', 'xml', 'md'
    }

    # 4-category classification
    CATEGORIES = {
        'work': 'Work-related documents to keep and process',
        'personal': 'Personal documents that can be deleted',
        'uncertain': 'Unclear classification - needs user review',
        'spam': 'Spam or irrelevant content to delete'
    }

    def __init__(self, api_key: str, llamaparse_key: str):
        """
        Initialize document manager

        Args:
            api_key: OpenAI API key
            llamaparse_key: LlamaParse API key
        """
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )

        # Initialize LlamaParse parser (optional - only needed for document uploads)
        if llamaparse_key:
            try:
                # Create a simple config object for LlamaParseParser
                class ParserConfig:
                    OPENAI_API_KEY = api_key
                    LLAMAPARSE_API_KEY = llamaparse_key
                    LLAMAPARSE_RESULT_TYPE = "markdown"
                    LLAMAPARSE_VERBOSE = False

                self.parser = LlamaParseParser(ParserConfig())
            except Exception as e:
                print(f"⚠️  LlamaParse not initialized: {e}")
                self.parser = None
        else:
            print("ℹ️  LlamaParse not configured (optional - only needed for document uploads)")
            self.parser = None

        self.classifier = WorkPersonalClassifier(api_key, model=AZURE_CHAT_DEPLOYMENT)

        # Create directories
        self.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        self.CLASSIFIED_FOLDER.mkdir(parents=True, exist_ok=True)

        for category in self.CATEGORIES:
            (self.CLASSIFIED_FOLDER / category).mkdir(exist_ok=True)

    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS

    def upload_file(self, file, user_id: str = "default") -> Dict:
        """
        Upload and process a file

        Args:
            file: FileStorage object from Flask request
            user_id: User identifier

        Returns:
            Dict with upload status and document info
        """
        if not file or file.filename == '':
            return {'success': False, 'error': 'No file selected'}

        if not self.allowed_file(file.filename):
            return {
                'success': False,
                'error': f'File type not allowed. Allowed: {", ".join(self.ALLOWED_EXTENSIONS)}'
            }

        try:
            # Save file
            filename = secure_filename(file.filename)
            doc_id = f"{user_id}_{uuid.uuid4().hex[:8]}_{filename}"
            filepath = self.UPLOAD_FOLDER / doc_id
            file.save(str(filepath))

            # Parse with LlamaParse
            print(f"Parsing {filename} with LlamaParse...")
            parsed_data = self.parser.parse(str(filepath))

            if not parsed_data or not parsed_data.get('content'):
                return {
                    'success': False,
                    'error': 'Failed to parse document content'
                }

            # Create document object
            document = {
                'doc_id': doc_id,
                'filename': filename,
                'user_id': user_id,
                'source': 'manual_upload',
                'content': parsed_data['content'],
                'metadata': {
                    **parsed_data.get('metadata', {}),
                    'upload_time': datetime.now().isoformat(),
                    'file_path': str(filepath),
                    'file_size': os.path.getsize(filepath)
                },
                'structured_data': parsed_data.get('structured_data', {}),
                'parsing_status': 'success'
            }

            # Classify document (4 categories)
            print(f"Classifying {filename}...")
            classification = self.classify_document_4way(document)
            document['classification'] = classification

            # Save to classified folder
            category = classification['category']
            classified_file = self.CLASSIFIED_FOLDER / category / f"{doc_id}.json"
            with open(classified_file, 'w', encoding='utf-8') as f:
                json.dump(document, f, indent=2, ensure_ascii=False)

            return {
                'success': True,
                'document': {
                    'doc_id': doc_id,
                    'filename': filename,
                    'category': category,
                    'confidence': classification['confidence'],
                    'size': document['metadata']['file_size'],
                    'needs_review': classification.get('needs_review', False)
                }
            }

        except Exception as e:
            print(f"Error uploading file: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def classify_document_4way(self, document: Dict) -> Dict:
        """
        Classify document into 4 categories: work, personal, uncertain, spam

        Args:
            document: Document dictionary

        Returns:
            Classification result with category and confidence
        """
        content = document.get('content', '')
        title = document.get('filename', document.get('metadata', {}).get('subject', ''))

        # Create enhanced prompt for 4-way classification
        prompt = f"""Classify the following document into ONE of these 4 categories:

1. WORK: Business documents, project materials, client communications, technical content, professional correspondence
2. PERSONAL: Family matters, personal finances, social events, personal shopping, personal travel plans
3. UNCERTAIN: Could be either work or personal, ambiguous content, needs human review
4. SPAM: Advertisements, marketing emails, promotional content, irrelevant junk

Title/Filename: {title}

Content (first 1500 chars):
{content[:1500]}

Provide your response in this JSON format:
{{
    "category": "work" or "personal" or "uncertain" or "spam",
    "confidence": <float between 0.0 and 1.0>,
    "reasoning": "<brief explanation of why this category>",
    "key_indicators": ["<indicator 1>", "<indicator 2>"]
}}

Guidelines:
- If confidence < 0.75, consider using "uncertain"
- Spam is for clear advertising/marketing only
- When in doubt between work/personal, use "uncertain" not "work"
"""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert document classifier. Provide accurate 4-way classifications with confidence scores."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=200
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON response
            if '{' in result_text and '}' in result_text:
                start = result_text.index('{')
                end = result_text.rindex('}') + 1
                json_str = result_text[start:end]
                result = json.loads(json_str)

                category = result.get('category', 'uncertain').lower()
                confidence = float(result.get('confidence', 0.5))
                reasoning = result.get('reasoning', '')
                key_indicators = result.get('key_indicators', [])

                # Determine if needs review
                needs_review = (
                    category == 'uncertain' or
                    confidence < 0.75 or
                    (category in ['personal', 'spam'] and confidence < 0.85)
                )

                return {
                    'category': category,
                    'confidence': confidence,
                    'reasoning': reasoning,
                    'key_indicators': key_indicators,
                    'needs_review': needs_review,
                    'action': self._get_action(category, confidence, needs_review)
                }

        except Exception as e:
            print(f"Classification error: {e}")

        # Fallback
        return {
            'category': 'uncertain',
            'confidence': 0.5,
            'reasoning': 'Classification failed',
            'key_indicators': [],
            'needs_review': True,
            'action': 'review'
        }

    def _get_action(self, category: str, confidence: float, needs_review: bool) -> str:
        """
        Determine action based on classification

        Returns:
            'process' - Add to RAG
            'delete' - Remove from system
            'review' - Show to user for decision
        """
        if needs_review:
            return 'review'

        if category == 'work' and confidence >= 0.75:
            return 'process'
        elif category in ['personal', 'spam'] and confidence >= 0.85:
            return 'delete'
        else:
            return 'review'

    def get_documents_for_review(self, user_id: str = "default") -> List[Dict]:
        """
        Get all documents that need user review

        Args:
            user_id: User identifier

        Returns:
            List of documents needing review
        """
        review_docs = []

        # Check uncertain category
        uncertain_dir = self.CLASSIFIED_FOLDER / 'uncertain'
        if uncertain_dir.exists():
            for doc_file in uncertain_dir.glob(f"{user_id}_*.json"):
                with open(doc_file, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                    review_docs.append(doc)

        # Check documents with needs_review flag
        for category in ['work', 'personal', 'spam']:
            category_dir = self.CLASSIFIED_FOLDER / category
            if category_dir.exists():
                for doc_file in category_dir.glob(f"{user_id}_*.json"):
                    with open(doc_file, 'r', encoding='utf-8') as f:
                        doc = json.load(f)
                        if doc.get('classification', {}).get('needs_review', False):
                            review_docs.append(doc)

        return review_docs

    def user_decision(self, doc_id: str, decision: str, user_id: str = "default") -> Dict:
        """
        Process user's decision on a document

        Args:
            doc_id: Document ID
            decision: 'keep' or 'delete'
            user_id: User identifier

        Returns:
            Result of the action
        """
        if decision not in ['keep', 'delete']:
            return {'success': False, 'error': 'Decision must be "keep" or "delete"'}

        # Find document in classified folders
        doc_path = None
        current_category = None

        for category in self.CATEGORIES:
            potential_path = self.CLASSIFIED_FOLDER / category / f"{doc_id}.json"
            if potential_path.exists():
                doc_path = potential_path
                current_category = category
                break

        if not doc_path:
            return {'success': False, 'error': 'Document not found'}

        # Load document
        with open(doc_path, 'r', encoding='utf-8') as f:
            document = json.load(f)

        if decision == 'delete':
            # Delete classified file
            doc_path.unlink()

            # Delete original upload if exists
            upload_path = Path(document['metadata'].get('file_path', ''))
            if upload_path.exists():
                upload_path.unlink()

            return {
                'success': True,
                'action': 'deleted',
                'doc_id': doc_id
            }

        else:  # keep
            # Move to work category if not already there
            if current_category != 'work':
                # Update classification
                document['classification']['category'] = 'work'
                document['classification']['needs_review'] = False
                document['classification']['user_override'] = True

                # Move file
                new_path = self.CLASSIFIED_FOLDER / 'work' / f"{doc_id}.json"
                with open(new_path, 'w', encoding='utf-8') as f:
                    json.dump(document, f, indent=2, ensure_ascii=False)

                # Delete old location
                doc_path.unlink()

            return {
                'success': True,
                'action': 'kept',
                'doc_id': doc_id,
                'ready_for_processing': True
            }

    def get_documents_ready_for_rag(self, user_id: str = "default") -> List[Dict]:
        """
        Get all work documents ready to be added to RAG

        Args:
            user_id: User identifier

        Returns:
            List of documents ready for RAG processing
        """
        work_docs = []
        work_dir = self.CLASSIFIED_FOLDER / 'work'

        if work_dir.exists():
            for doc_file in work_dir.glob(f"{user_id}_*.json"):
                with open(doc_file, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                    # Only include docs that don't need review
                    if not doc.get('classification', {}).get('needs_review', False):
                        work_docs.append(doc)

        return work_docs

    def get_statistics(self, user_id: str = "default") -> Dict:
        """Get document statistics"""
        stats = {
            'total': 0,
            'by_category': {},
            'needs_review': 0,
            'ready_for_rag': 0
        }

        for category in self.CATEGORIES:
            category_dir = self.CLASSIFIED_FOLDER / category
            if category_dir.exists():
                docs = list(category_dir.glob(f"{user_id}_*.json"))
                stats['by_category'][category] = len(docs)
                stats['total'] += len(docs)

                # Count needs_review
                for doc_file in docs:
                    with open(doc_file, 'r', encoding='utf-8') as f:
                        doc = json.load(f)
                        if doc.get('classification', {}).get('needs_review', False):
                            stats['needs_review'] += 1

        # Ready for RAG = work docs that don't need review
        work_dir = self.CLASSIFIED_FOLDER / 'work'
        if work_dir.exists():
            for doc_file in work_dir.glob(f"{user_id}_*.json"):
                with open(doc_file, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                    if not doc.get('classification', {}).get('needs_review', False):
                        stats['ready_for_rag'] += 1

        return stats
