"""
Email Forwarding Service
Receives forwarded emails via IMAP from beatatucla@gmail.com
Parses emails and adds them as documents to the database
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import os
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from database.models import Document, DocumentStatus, utc_now
from parsers.document_parser import DocumentParser


class EmailForwardingService:
    """Service to poll and process forwarded emails"""

    def __init__(self, db: Session, config=None):
        self.db = db
        self.config = config
        self.parser = DocumentParser(config=config)

        # Email credentials from environment
        self.email_address = os.getenv("FORWARD_EMAIL_ADDRESS", "beatatucla@gmail.com")
        self.email_password = os.getenv("FORWARD_EMAIL_PASSWORD")

        if not self.email_password:
            raise ValueError("FORWARD_EMAIL_PASSWORD environment variable not set")

    def connect_imap(self) -> imaplib.IMAP4_SSL:
        """Connect to Gmail IMAP server"""
        try:
            # Connect to Gmail with 10 second timeout
            import socket
            mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=10)
            mail.login(self.email_address, self.email_password)
            print(f"✓ Connected to {self.email_address}")
            return mail
        except socket.timeout:
            raise Exception(f"Connection to Gmail IMAP timed out after 10 seconds")
        except Exception as e:
            raise Exception(f"Failed to connect to IMAP: {str(e)}")

    def fetch_new_emails(self, tenant_id: str, max_emails: int = 50) -> Dict:
        """
        Fetch new unread emails from forwarding inbox

        Args:
            tenant_id: Tenant ID to associate documents with
            max_emails: Maximum number of emails to process

        Returns:
            Dict with processed count and errors
        """
        mail = None
        try:
            mail = self.connect_imap()
            mail.select("INBOX")

            # Search for unread emails
            status, messages = mail.search(None, "UNSEEN")

            if status != "OK":
                return {"success": False, "error": "Failed to search emails"}

            email_ids = messages[0].split()
            total_emails = len(email_ids)

            if total_emails == 0:
                return {
                    "success": True,
                    "processed": 0,
                    "total": 0,
                    "message": "No new emails"
                }

            print(f"\n📧 Found {total_emails} new forwarded emails")

            # Process emails (limit to max_emails)
            processed = 0
            errors = []

            for email_id in email_ids[:max_emails]:
                try:
                    # Fetch email
                    status, msg_data = mail.fetch(email_id, "(RFC822)")

                    if status != "OK":
                        errors.append(f"Failed to fetch email {email_id}")
                        continue

                    # Parse email
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)

                    # Extract metadata
                    doc_data = self._extract_email_data(email_message)

                    # Create document in database
                    self._create_document(tenant_id, doc_data)

                    processed += 1
                    print(f"  ✓ Processed: {doc_data['subject'][:50]}...")

                    # Mark as read
                    mail.store(email_id, '+FLAGS', '\\Seen')

                except Exception as e:
                    error_msg = f"Error processing email {email_id}: {str(e)}"
                    errors.append(error_msg)
                    print(f"  ✗ {error_msg}")

            return {
                "success": True,
                "processed": processed,
                "total": total_emails,
                "errors": errors
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass

    def _extract_email_data(self, email_message) -> Dict:
        """Extract data from email message"""

        # Subject
        subject = self._decode_header(email_message.get("Subject", "No Subject"))

        # From
        from_addr = self._decode_header(email_message.get("From", "Unknown"))

        # Date
        date_str = email_message.get("Date")
        timestamp = None
        if date_str:
            try:
                timestamp = parsedate_to_datetime(date_str)
            except:
                pass

        # Extract body
        body = self._extract_body(email_message)

        # Detect original sender (from forwarded email)
        original_from = self._extract_original_sender(body, from_addr)

        # Create content
        content = f"""Subject: {subject}
From: {original_from}
Forwarded by: {from_addr}
Date: {date_str or 'Unknown'}

{body}"""

        return {
            "subject": subject,
            "sender_email": original_from,
            "forwarded_by": from_addr,
            "content": content,
            "timestamp": timestamp or utc_now(),
            "metadata": {
                "source": "email_forwarding",
                "forwarding_email": self.email_address,
                "original_date": date_str
            }
        }

    def _decode_header(self, header_value: str) -> str:
        """Decode email header"""
        if not header_value:
            return ""

        decoded_parts = decode_header(header_value)
        header_text = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                header_text += part.decode(encoding or "utf-8", errors="ignore")
            else:
                header_text += part

        return header_text

    def _extract_body(self, email_message) -> str:
        """Extract email body (text or HTML)"""
        body = ""

        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()

                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        break
                    except:
                        pass

                elif content_type == "text/html" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        html = payload.decode(charset, errors='ignore')
                        # Simple HTML stripping (better to use proper parser)
                        import re
                        body = re.sub('<[^<]+?>', '', html)
                    except:
                        pass
        else:
            try:
                payload = email_message.get_payload(decode=True)
                if payload:
                    charset = email_message.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='ignore')
            except:
                body = str(email_message.get_payload())

        return body.strip()

    def _extract_original_sender(self, body: str, forwarded_by: str) -> str:
        """
        Try to extract original sender from forwarded email
        Looks for patterns like:
        - From: john@example.com
        - ---------- Forwarded message ---------
        """
        import re

        # Pattern 1: "From: email@domain.com" near top of email
        from_pattern = re.search(r'^From:\s*([^\n<]+(?:<[^>]+>)?)', body, re.MULTILINE | re.IGNORECASE)
        if from_pattern:
            return from_pattern.group(1).strip()

        # Pattern 2: Look for email address in first 500 chars
        email_pattern = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', body[:500])
        if email_pattern:
            found_email = email_pattern.group(1)
            # Make sure it's not the forwarding address
            if found_email.lower() not in forwarded_by.lower():
                return found_email

        # Fallback to forwarded_by
        return forwarded_by

    def _create_document(self, tenant_id: str, doc_data: Dict):
        """Create document in database"""

        # Create document
        document = Document(
            tenant_id=tenant_id,
            external_id=f"email_fwd_{int(datetime.now().timestamp() * 1000)}",
            source_type="email",
            title=doc_data["subject"],
            content=doc_data["content"],
            sender_email=doc_data["sender_email"],
            source_created_at=doc_data["timestamp"],
            doc_metadata=doc_data["metadata"],
            status=DocumentStatus.PENDING
        )

        self.db.add(document)
        self.db.commit()

        print(f"    → Created document: {document.id}")
        return document


def poll_forwarded_emails(tenant_id: str, db: Session, config=None, max_emails: int = 50) -> Dict:
    """
    Convenience function to poll for forwarded emails

    Args:
        tenant_id: Tenant ID
        db: Database session
        config: Configuration object
        max_emails: Max emails to process

    Returns:
        Result dict
    """
    service = EmailForwardingService(db, config)
    return service.fetch_new_emails(tenant_id, max_emails)
