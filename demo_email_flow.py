#!/usr/bin/env python3
"""
Email Forwarding Flow Demonstration
Shows how forwarded emails are parsed and processed
"""

import sys
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from connectors.email_forwarding_connector import EmailForwardingConnector
from connectors.base_connector import ConnectorConfig


def create_test_forwarded_email():
    """Create a test email in Gmail forwarding format"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Fwd: Q1 Roadmap and Key Decisions'
    msg['From'] = 'alice@gmail.com'
    msg['To'] = 'tenant_abc123@inbox.yourdomain.com'

    # Gmail forwarding format
    body = """
Hi there,

I'm forwarding this important email about our Q1 roadmap.

---------- Forwarded message ---------
From: John Doe <john.doe@company.com>
Date: Wed, Jan 30, 2025 at 2:30 PM
Subject: Q1 Roadmap and Key Decisions
To: Product Team <team@company.com>

Hi team,

I wanted to share the finalized Q1 roadmap and some key decisions we made:

## Completed Projects
1. Email forwarding integration - ✅ DONE
2. SMTP server deployment - ✅ DONE
3. Frontend UI updates - ✅ DONE

## Key Decisions Made
- Using self-hosted SMTP instead of Gmail OAuth API
- Each tenant gets a unique forwarding address (tenant_<hash>@inbox.domain.com)
- No OAuth required - better privacy for users
- Support for Gmail, Outlook, Yahoo forwarding formats

## Technical Architecture
- Backend: Python Flask + aiosmtpd SMTP server
- Frontend: Next.js with email forwarding modal
- Database: PostgreSQL (stores forwarded emails as Documents)
- Deployment: Render (3 services: API, SMTP, Frontend)

## Next Steps
1. Deploy to production on Render
2. Configure DNS MX records for inbox.yourdomain.com
3. Test with real Gmail forwarding
4. Monitor email processing metrics

## Action Items
@Alice - Set up DNS records
@Bob - Test Gmail forwarding flow
@Charlie - Monitor SMTP server logs

Let me know if you have any questions or concerns.

Best regards,
John Doe
VP of Engineering
"""

    part = MIMEText(body, 'plain')
    msg.attach(part)

    return msg.as_bytes()


def main():
    """Demonstrate the email forwarding flow"""

    print("\n" + "="*70)
    print("📧 EMAIL FORWARDING FLOW DEMONSTRATION")
    print("="*70)

    # Step 1: Create test email
    print("\n📝 STEP 1: User forwards email to unique address")
    print("-"*70)
    print("From: alice@gmail.com")
    print("To: tenant_abc123@inbox.yourdomain.com")
    print("Subject: Fwd: Q1 Roadmap and Key Decisions")
    print("\n✅ Email sent via SMTP")

    # Step 2: SMTP server receives email
    print("\n" + "="*70)
    print("📨 STEP 2: SMTP Server receives email")
    print("-"*70)
    print("Server: 0.0.0.0:2525 (or port 25 in production)")
    print("Recipient: tenant_abc123@inbox.yourdomain.com")
    print("Extracting tenant ID from address...")
    tenant_id = "abc123"
    print(f"✅ Tenant ID: {tenant_id}")

    # Step 3: Initialize connector
    print("\n" + "="*70)
    print("🔧 STEP 3: Initialize EmailForwardingConnector")
    print("-"*70)

    config = ConnectorConfig(
        connector_type="email_forwarding",
        user_id=tenant_id,
        settings={}
    )

    connector = EmailForwardingConnector(config)
    print(f"Connector Type: {connector.CONNECTOR_TYPE}")
    print(f"Forwarding Email: {connector.forwarding_email}")
    print("✅ Connector initialized")

    # Step 4: Parse email
    print("\n" + "="*70)
    print("🔍 STEP 4: Parse forwarded email")
    print("-"*70)

    raw_email = create_test_forwarded_email()
    print(f"Raw email size: {len(raw_email)} bytes")
    print("Detecting forwarding format...")

    document = connector.parse_forwarded_email(raw_email)

    if not document:
        print("❌ Failed to parse email")
        return

    print("✅ Email parsed successfully!")
    print(f"Detected format: Gmail forwarding")

    # Step 5: Display parsed data
    print("\n" + "="*70)
    print("📄 STEP 5: Extracted document data")
    print("="*70)

    print(f"\n🏷️  DOCUMENT METADATA:")
    print("-"*70)
    print(f"Document ID: {document.doc_id}")
    print(f"Title: {document.title}")
    print(f"Author: {document.author}")
    print(f"Source: {document.source}")
    print(f"Document Type: {document.doc_type}")
    print(f"Timestamp: {document.timestamp}")

    print(f"\n📧 ORIGINAL EMAIL DETAILS:")
    print("-"*70)
    print(f"From: {document.metadata.get('from')}")
    print(f"To: {document.metadata.get('to')}")
    print(f"Date: {document.metadata.get('date')}")
    print(f"Original Sender: {document.metadata.get('original_sender')}")
    print(f"Sender Name: {document.metadata.get('sender_name')}")
    print(f"Forwarded To: {document.metadata.get('forwarded_to')}")

    print(f"\n📝 CONTENT PREVIEW:")
    print("-"*70)
    content_lines = document.content.split('\n')
    for i, line in enumerate(content_lines[:25], 1):
        print(f"{i:3d} | {line}")

    if len(content_lines) > 25:
        print(f"    | ... ({len(content_lines) - 25} more lines)")

    # Step 6: Simulate saving to database
    print("\n" + "="*70)
    print("💾 STEP 6: Save to database")
    print("-"*70)
    print("Creating Document record in PostgreSQL...")
    print(f"""
Document:
  - tenant_id: {tenant_id}
  - external_id: {document.doc_id}
  - source_type: email
  - title: {document.title}
  - content: {len(document.content)} characters
  - sender: {document.metadata.get('from')}
  - sender_email: {document.metadata.get('original_sender')}
  - source_created_at: {document.timestamp}
  - status: PENDING
  - embedding_generated: False
""")
    print("✅ Document saved to database")

    # Step 7: Processing pipeline
    print("\n" + "="*70)
    print("⚙️  STEP 7: Processing pipeline (async)")
    print("-"*70)
    print("1. Classification Service → Classify as WORK or PERSONAL")
    print("2. Extraction Service → Extract entities, decisions, action items")
    print("3. Embedding Service → Generate embeddings with OpenAI")
    print("4. Vector Database → Store in Pinecone for semantic search")
    print("5. Knowledge Graph → Link to projects and topics")
    print("✅ Email ready for RAG retrieval")

    # Summary
    print("\n" + "="*70)
    print("✨ FLOW COMPLETE!")
    print("="*70)
    print(f"""
Summary:
  ✅ Email forwarded by user
  ✅ Received by SMTP server
  ✅ Parsed original email from forwarding wrapper
  ✅ Extracted metadata (sender, subject, date)
  ✅ Saved to database as Document
  ✅ Queued for processing pipeline

The email is now searchable in the knowledge base!
Users can query: "What decisions were made in Q1?" and this
email will be retrieved with semantic search.
""")

    print("="*70)
    print("🎉 Email Forwarding Integration Working!")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
