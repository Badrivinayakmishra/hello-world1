"""
Email Forwarding Connector
Receives forwarded emails via SMTP and processes them into the knowledge base.
No OAuth required - users simply forward emails to their unique address.
"""

import re
import email
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Any
from email.utils import parsedate_to_datetime, parseaddr
from bs4 import BeautifulSoup

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document


class EmailForwardingConnector(BaseConnector):
    """
    Email Forwarding connector for receiving forwarded emails.

    Instead of OAuth, each user gets a unique email address:
    - Format: tenant_<tenant_id>@inbox.yourdomain.com
    - Users forward emails to this address
    - Backend receives via SMTP and parses original email

    Extracts:
    - Original sender (from forwarded email headers)
    - Original subject
    - Original body (cleaned from forwarding wrapper)
    - Original timestamp
    - Attachments metadata (optional)
    """

    CONNECTOR_TYPE = "email_forwarding"
    REQUIRED_CREDENTIALS = []  # No OAuth tokens needed
    OPTIONAL_SETTINGS = {
        "forwarding_email": None,  # Auto-generated: tenant_<id>@inbox.domain.com
        "verified": False,  # Email address verified
        "auto_parse": True,  # Automatically parse forwarded emails
        "include_attachments": False,  # Extract attachment metadata
        "filter_spam": True  # Filter spam emails
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.forwarding_email = self._generate_forwarding_email()

    def _generate_forwarding_email(self) -> str:
        """
        Generate unique forwarding email address for this tenant.
        Format: tenant_<tenant_id>@inbox.yourdomain.com
        """
        tenant_id = self.config.user_id  # In multi-tenant, this is tenant_id
        # Create short hash for URL-friendly email
        short_hash = hashlib.sha256(tenant_id.encode()).hexdigest()[:12]
        return f"tenant_{short_hash}@inbox.yourdomain.com"

    async def connect(self) -> bool:
        """
        'Connect' for email forwarding just validates the configuration.
        No actual connection needed since we receive emails passively.
        """
        try:
            self.status = ConnectorStatus.CONNECTING

            # Validate forwarding email
            if not self.forwarding_email:
                self._set_error("Forwarding email not configured")
                return False

            # Store forwarding email in settings
            self.config.settings["forwarding_email"] = self.forwarding_email

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            return True

        except Exception as e:
            self._set_error(f"Connection error: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect (no-op for email forwarding)"""
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        """Test if forwarding email is valid"""
        return self.status == ConnectorStatus.CONNECTED and bool(self.forwarding_email)

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Sync is handled by SMTP server receiving emails in real-time.
        This method is called when manually triggering sync.
        Returns empty list since emails are processed on arrival.
        """
        self.status = ConnectorStatus.SYNCING

        # In real implementation, could query database for recently
        # received emails and return them
        documents = []

        self.sync_stats = {
            "documents_synced": len(documents),
            "sync_time": datetime.now().isoformat(),
            "message": "Email forwarding processes emails in real-time"
        }

        self.status = ConnectorStatus.CONNECTED
        return documents

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get specific document by ID (from database)"""
        # Would query database for document
        return None

    def parse_forwarded_email(self, raw_email: bytes) -> Optional[Document]:
        """
        Parse forwarded email to extract original email content.

        Handles forwarding formats from:
        - Gmail
        - Outlook
        - Yahoo
        - Generic email clients

        Args:
            raw_email: Raw email bytes received via SMTP

        Returns:
            Document object with extracted content
        """
        try:
            # Parse email message
            msg = email.message_from_bytes(raw_email)

            # Extract forwarding envelope
            forwarded_to = self._extract_forwarded_to(msg)

            # Verify this email was forwarded to our address
            if not self._is_for_us(forwarded_to):
                return None

            # Detect forwarding format
            forwarding_format = self._detect_forwarding_format(msg)

            # Extract original email based on format
            if forwarding_format == "gmail":
                original = self._parse_gmail_forward(msg)
            elif forwarding_format == "outlook":
                original = self._parse_outlook_forward(msg)
            else:
                original = self._parse_generic_forward(msg)

            if not original:
                return None

            # Create Document object
            doc = self._create_document_from_parsed(original)
            return doc

        except Exception as e:
            print(f"Error parsing forwarded email: {e}")
            return None

    def _extract_forwarded_to(self, msg: email.message.Message) -> str:
        """Extract the address this email was forwarded to"""
        # Check To, Cc, Delivered-To headers
        for header in ['Delivered-To', 'To', 'Cc']:
            value = msg.get(header, '')
            if 'inbox.yourdomain.com' in value:
                return value
        return ''

    def _is_for_us(self, forwarded_to: str) -> bool:
        """Check if email was forwarded to our domain"""
        return 'inbox.yourdomain.com' in forwarded_to and \
               self.forwarding_email.split('@')[0] in forwarded_to

    def _detect_forwarding_format(self, msg: email.message.Message) -> str:
        """Detect which email client forwarded this email"""
        # Check headers
        mailer = msg.get('X-Mailer', '').lower()
        received = msg.get('Received', '').lower()

        if 'gmail' in mailer or 'gmail' in received:
            return 'gmail'
        elif 'outlook' in mailer or 'microsoft' in received:
            return 'outlook'
        else:
            return 'generic'

    def _parse_gmail_forward(self, msg: email.message.Message) -> Optional[Dict]:
        """
        Parse Gmail forwarded email format.

        Gmail forwards look like:
        ---------- Forwarded message ---------
        From: Original Sender <sender@example.com>
        Date: Wed, Jan 29, 2025 at 10:30 AM
        Subject: Original Subject
        To: recipient@example.com

        [Original email body]
        """
        body = self._get_email_body(msg)

        # Look for Gmail forward marker
        forward_pattern = r'-+\s*Forwarded message\s*-+\s*(.*?)(?:\n\n|\r\n\r\n)'
        match = re.search(forward_pattern, body, re.DOTALL | re.IGNORECASE)

        if match:
            # Extract headers from forwarded section
            header_section = match.group(1)

            # Extract original fields
            original_from = self._extract_field(header_section, r'From:\s*(.+)')
            original_date = self._extract_field(header_section, r'Date:\s*(.+)')
            original_subject = self._extract_field(header_section, r'Subject:\s*(.+)')
            original_to = self._extract_field(header_section, r'To:\s*(.+)')

            # Extract body (everything after the headers)
            body_start = match.end()
            original_body = body[body_start:].strip()

            return {
                'from': original_from,
                'date': original_date,
                'subject': original_subject,
                'to': original_to,
                'body': original_body
            }

        return None

    def _parse_outlook_forward(self, msg: email.message.Message) -> Optional[Dict]:
        """
        Parse Outlook forwarded email format.

        Outlook forwards look like:
        ________________________________
        From: Original Sender
        Sent: Wednesday, January 29, 2025 10:30 AM
        To: recipient@example.com
        Subject: Original Subject

        [Original email body]
        """
        body = self._get_email_body(msg)

        # Look for Outlook forward marker (underscores)
        forward_pattern = r'_{20,}\s*(.*?)(?:\n\n|\r\n\r\n)'
        match = re.search(forward_pattern, body, re.DOTALL)

        if match:
            header_section = match.group(1)

            original_from = self._extract_field(header_section, r'From:\s*(.+)')
            original_date = self._extract_field(header_section, r'Sent:\s*(.+)')
            original_subject = self._extract_field(header_section, r'Subject:\s*(.+)')
            original_to = self._extract_field(header_section, r'To:\s*(.+)')

            body_start = match.end()
            original_body = body[body_start:].strip()

            return {
                'from': original_from,
                'date': original_date,
                'subject': original_subject,
                'to': original_to,
                'body': original_body
            }

        return None

    def _parse_generic_forward(self, msg: email.message.Message) -> Optional[Dict]:
        """
        Parse generic forwarded email (fallback).
        Tries to extract what it can from headers.
        """
        # For generic forwards, use the envelope headers
        return {
            'from': msg.get('From', 'Unknown'),
            'date': msg.get('Date', ''),
            'subject': self._extract_original_subject(msg.get('Subject', '')),
            'to': msg.get('To', ''),
            'body': self._get_email_body(msg)
        }

    def _extract_original_subject(self, subject: str) -> str:
        """Extract original subject from forwarded subject"""
        # Remove Fwd:, FW:, etc.
        subject = re.sub(r'^(Fwd?|FW):\s*', '', subject, flags=re.IGNORECASE)
        return subject.strip()

    def _get_email_body(self, msg: email.message.Message) -> str:
        """Extract email body (text or HTML)"""
        body = ""

        if msg.is_multipart():
            # Get text parts
            for part in msg.walk():
                content_type = part.get_content_type()

                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode('utf-8', errors='ignore')
                            break
                    except:
                        pass

                elif content_type == "text/html" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            html = payload.decode('utf-8', errors='ignore')
                            # Convert HTML to text
                            soup = BeautifulSoup(html, 'html.parser')
                            body = soup.get_text(separator='\n', strip=True)
                    except:
                        pass
        else:
            # Single part
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
            except:
                body = str(msg.get_payload())

        return body.strip()

    def _extract_field(self, text: str, pattern: str) -> str:
        """Extract field using regex pattern"""
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ''

    def _create_document_from_parsed(self, parsed: Dict) -> Document:
        """Create Document object from parsed email data"""
        # Parse sender
        sender_name, sender_email = parseaddr(parsed.get('from', ''))

        # Parse date
        try:
            if parsed.get('date'):
                timestamp = parsedate_to_datetime(parsed['date'])
            else:
                timestamp = datetime.now()
        except:
            timestamp = datetime.now()

        # Generate unique document ID
        subject = parsed.get('subject', '(No Subject)')
        doc_id = hashlib.sha256(
            f"{sender_email}_{subject}_{timestamp.isoformat()}".encode()
        ).hexdigest()[:16]

        # Format content
        content = f"""Subject: {subject}
From: {parsed.get('from', 'Unknown')}
To: {parsed.get('to', 'Unknown')}
Date: {parsed.get('date', '')}

{parsed.get('body', '')}"""

        return Document(
            doc_id=f"email_{doc_id}",
            source="email_forwarding",
            content=content,
            title=subject,
            metadata={
                "from": parsed.get('from'),
                "to": parsed.get('to'),
                "date": parsed.get('date'),
                "original_sender": sender_email,
                "sender_name": sender_name,
                "forwarded_to": self.forwarding_email
            },
            timestamp=timestamp,
            author=sender_name or sender_email,
            doc_type="email"
        )
