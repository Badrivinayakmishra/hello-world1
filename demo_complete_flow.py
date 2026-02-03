#!/usr/bin/env python3
"""
Complete Email Forwarding Flow Demonstration
Shows the entire process from email receipt to database storage
"""

import sys
import os
import re
from email.utils import parseaddr, parsedate_to_datetime
import hashlib
from datetime import datetime

# Simple colored output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}")

def print_step(num, text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}📋 STEP {num}: {text}{Colors.END}")
    print(f"{Colors.CYAN}{'-'*70}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_info(label, value):
    print(f"  {Colors.BOLD}{label}:{Colors.END} {value}")


def demo_email_forwarding():
    """Demonstrate the complete email forwarding flow"""

    print_header("📧 EMAIL FORWARDING INTEGRATION - COMPLETE FLOW")

    # STEP 1: User Setup
    print_step(1, "User gets unique forwarding address")
    tenant_id = "abc123"
    tenant_hash = hashlib.sha256(tenant_id.encode()).hexdigest()[:12]
    forwarding_email = f"tenant_{tenant_hash}@inbox.yourdomain.com"

    print_info("Tenant ID", tenant_id)
    print_info("Unique Email", forwarding_email)
    print_success("User copies this address to their Gmail forwarding settings")

    # STEP 2: User forwards email from Gmail
    print_step(2, "User forwards email from Gmail")

    original_email = {
        'from': 'John Doe <john.doe@company.com>',
        'date': 'Wed, Jan 30, 2025 at 2:30 PM',
        'subject': 'Q1 Roadmap and Key Decisions',
        'to': 'Product Team <team@company.com>',
        'body': """Hi team,

I wanted to share the finalized Q1 roadmap and key decisions:

## Completed Projects
1. Email forwarding integration - ✅ DONE
2. SMTP server deployment - ✅ DONE
3. Frontend UI updates - ✅ DONE

## Key Decisions Made
- Using self-hosted SMTP instead of Gmail OAuth API
- Each tenant gets unique forwarding address
- No OAuth required - better privacy for users
- Support for Gmail, Outlook, Yahoo formats

## Technical Architecture
- Backend: Python Flask + aiosmtpd SMTP server
- Frontend: Next.js with email forwarding modal
- Database: PostgreSQL (stores as Documents)
- Deployment: Render (3 services)

## Action Items
@Alice - Set up DNS records
@Bob - Test Gmail forwarding
@Charlie - Monitor SMTP logs

Best regards,
John Doe
VP of Engineering"""
    }

    gmail_forwarded_email = f"""From: alice@gmail.com
To: {forwarding_email}
Subject: Fwd: {original_email['subject']}

Hi there, forwarding this important email.

---------- Forwarded message ---------
From: {original_email['from']}
Date: {original_email['date']}
Subject: {original_email['subject']}
To: {original_email['to']}

{original_email['body']}"""

    print_info("Forwarding User", "alice@gmail.com")
    print_info("Forwarded To", forwarding_email)
    print_info("Original Subject", original_email['subject'])
    print_success("Email sent to SMTP server")

    # STEP 3: SMTP Server receives email
    print_step(3, "SMTP Server receives email")

    print_info("Server", "0.0.0.0:2525 (localhost) or 0.0.0.0:25 (production)")
    print_info("Protocol", "SMTP (aiosmtpd)")
    print_info("Handler", "EmailHandler.handle_DATA()")

    # Extract tenant from email address
    recipient = forwarding_email
    local_part = recipient.split('@')[0]
    extracted_tenant = local_part.replace('tenant_', '') if local_part.startswith('tenant_') else None

    print_info("Recipient", recipient)
    print_info("Extracted Tenant Hash", extracted_tenant or "N/A")
    print_success("Tenant identified from email address")

    # STEP 4: Parse forwarded email
    print_step(4, "Parse forwarded email to extract original")

    # Simulate parsing
    forward_pattern = r'-+\s*Forwarded message\s*-+\s*(.*?)(?:\n\n)'
    match = re.search(forward_pattern, gmail_forwarded_email, re.DOTALL)

    if match:
        header_section = match.group(1)

        # Extract fields
        from_match = re.search(r'From:\s*(.+)', header_section)
        date_match = re.search(r'Date:\s*(.+)', header_section)
        subject_match = re.search(r'Subject:\s*(.+)', header_section)
        to_match = re.search(r'To:\s*(.+)', header_section)

        parsed_from = from_match.group(1).strip() if from_match else None
        parsed_date = date_match.group(1).strip() if date_match else None
        parsed_subject = subject_match.group(1).strip() if subject_match else None
        parsed_to = to_match.group(1).strip() if to_match else None

        # Extract body (everything after headers)
        body_start = match.end()
        parsed_body = gmail_forwarded_email[body_start:].strip()

        print_info("Format Detected", "Gmail forwarding")
        print_info("Original From", parsed_from)
        print_info("Original Subject", parsed_subject)
        print_info("Original Date", parsed_date)
        print_success("Email parsed successfully")

        # STEP 5: Create Document object
        print_step(5, "Create Document object")

        sender_name, sender_email = parseaddr(parsed_from)
        timestamp = datetime.now()

        doc_id = hashlib.sha256(
            f"{sender_email}_{parsed_subject}_{timestamp.isoformat()}".encode()
        ).hexdigest()[:16]

        document_content = f"""Subject: {parsed_subject}
From: {parsed_from}
To: {parsed_to}
Date: {parsed_date}

{parsed_body}"""

        print_info("Document ID", f"email_{doc_id}")
        print_info("Title", parsed_subject)
        print_info("Author", sender_name or sender_email)
        print_info("Source Type", "email_forwarding")
        print_info("Content Length", f"{len(document_content)} characters")
        print_success("Document object created")

        # STEP 6: Save to database
        print_step(6, "Save to PostgreSQL database")

        db_record = {
            'id': f"doc_{doc_id}",
            'tenant_id': tenant_id,
            'connector_id': f"conn_{tenant_id}",
            'external_id': f"email_{doc_id}",
            'source_type': 'email',
            'title': parsed_subject,
            'content': document_content,
            'content_html': None,
            'sender': parsed_from,
            'sender_email': sender_email,
            'doc_metadata': {
                'from': parsed_from,
                'to': parsed_to,
                'date': parsed_date,
                'original_sender': sender_email,
                'sender_name': sender_name,
                'forwarded_to': forwarding_email
            },
            'source_created_at': timestamp,
            'status': 'PENDING',
            'classification': 'UNKNOWN',
            'embedding_generated': False,
            'created_at': datetime.now()
        }

        print(f"{Colors.CYAN}Database Record:{Colors.END}")
        for key, value in db_record.items():
            if key == 'content':
                print(f"  {key}: [{len(value)} chars]")
            elif key == 'doc_metadata':
                print(f"  {key}:")
                for mk, mv in value.items():
                    print(f"    - {mk}: {mv}")
            else:
                print(f"  {key}: {value}")

        print_success("Document saved to 'documents' table")

        # STEP 7: Processing pipeline
        print_step(7, "Background processing pipeline")

        print(f"{Colors.YELLOW}Pipeline stages (async):{Colors.END}")
        print(f"  1️⃣  {Colors.BOLD}Classification Service{Colors.END}")
        print(f"      → Classify as WORK or PERSONAL")
        print(f"      → Update: status=CLASSIFIED, classification=WORK")

        print(f"\n  2️⃣  {Colors.BOLD}Extraction Service{Colors.END}")
        print(f"      → Extract entities: @Alice, @Bob, @Charlie")
        print(f"      → Extract decisions: Using SMTP, No OAuth required")
        print(f"      → Extract action items: Set up DNS, Test forwarding")
        print(f"      → Update: structured_summary={{...}}")

        print(f"\n  3️⃣  {Colors.BOLD}Embedding Service{Colors.END}")
        print(f"      → Generate embeddings with OpenAI")
        print(f"      → Chunk content (512 tokens per chunk)")
        print(f"      → Store vectors in Pinecone")
        print(f"      → Update: embedding_generated=True, embedded_at=now()")

        print(f"\n  4️⃣  {Colors.BOLD}Knowledge Graph Service{Colors.END}")
        print(f"      → Link to project: 'Email Forwarding Integration'")
        print(f"      → Connect to topics: SMTP, OAuth, Privacy")
        print(f"      → Update: project_id='proj_email_forwarding'")

        print_success("Email fully processed and indexed")

        # STEP 8: User can now query
        print_step(8, "Email is searchable in knowledge base")

        example_queries = [
            "What decisions were made about Q1 roadmap?",
            "Who is responsible for setting up DNS?",
            "What's our approach to email integration?",
            "Show me action items from John Doe"
        ]

        print(f"{Colors.YELLOW}Example queries that will retrieve this email:{Colors.END}")
        for i, query in enumerate(example_queries, 1):
            print(f"  {i}. \"{query}\"")

        print_success("Email available for RAG retrieval")

        # Summary
        print_header("✨ FLOW COMPLETE - EMAIL FORWARDING SUCCESS!")

        print(f"""
{Colors.BOLD}Summary of what happened:{Colors.END}

  1. ✅ User got unique forwarding address: {Colors.CYAN}{forwarding_email}{Colors.END}
  2. ✅ User forwarded email from Gmail to this address
  3. ✅ SMTP server received email on port 2525/25
  4. ✅ Parser detected Gmail forwarding format
  5. ✅ Extracted original email from forwarding wrapper
  6. ✅ Created Document object with metadata
  7. ✅ Saved to PostgreSQL database
  8. ✅ Queued for background processing
  9. ✅ Classified, extracted, embedded, and indexed
  10. ✅ Now searchable in knowledge base!

{Colors.BOLD}{Colors.GREEN}🎉 The email forwarding integration is working!{Colors.END}

{Colors.BOLD}Benefits:{Colors.END}
  • {Colors.GREEN}No OAuth required{Colors.END} - No scary permission prompts
  • {Colors.GREEN}User privacy{Colors.END} - Only share what you forward
  • {Colors.GREEN}Works with any email{Colors.END} - Gmail, Outlook, Yahoo, etc.
  • {Colors.GREEN}Selective sharing{Colors.END} - Use Gmail filters for auto-forward
  • {Colors.GREEN}Full control{Colors.END} - Stop forwarding anytime

{Colors.BOLD}Next steps for production:{Colors.END}
  1. Deploy SMTP server to Render
  2. Configure DNS MX record: inbox.yourdomain.com → Render SMTP service
  3. Replace 'inbox.yourdomain.com' with your domain in code
  4. Test with real Gmail forwarding
  5. Monitor email processing metrics
""")

        print(f"{Colors.BOLD}{Colors.HEADER}{'='*70}{Colors.END}\n")


if __name__ == '__main__':
    demo_email_forwarding()
