#!/usr/bin/env python3
"""
Test email parser to debug parsing issues
"""

import sys
import os
from email.mime.text import MIMEText

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from connectors.email_forwarding_connector import EmailForwardingConnector
from connectors.base_connector import ConnectorConfig


# Create test email in Gmail forwarding format
raw_email_text = """From: alice@gmail.com
To: tenant_abc123@inbox.yourdomain.com
Subject: Fwd: Q1 Roadmap and Key Decisions
Content-Type: text/plain; charset="UTF-8"

Hi there,

I'm forwarding this important email about our Q1 roadmap.

---------- Forwarded message ---------
From: John Doe <john.doe@company.com>
Date: Wed, Jan 30, 2025 at 2:30 PM
Subject: Q1 Roadmap and Key Decisions
To: Product Team <team@company.com>

Hi team,

This is the original email content about Q1 roadmap.

Key decisions:
- Using self-hosted SMTP instead of Gmail OAuth
- Each tenant gets unique forwarding address
- No OAuth required

Best regards,
John
"""

print("Testing Email Parser...")
print("="*70)

# Convert to bytes
raw_email = raw_email_text.encode('utf-8')

# Create connector
config = ConnectorConfig(
    connector_type="email_forwarding",
    user_id="test_tenant",
    settings={}
)

connector = EmailForwardingConnector(config)

# Test parsing
print("\n🔍 Parsing email...")
document = connector.parse_forwarded_email(raw_email)

if document:
    print("✅ SUCCESS! Email parsed")
    print(f"\nTitle: {document.title}")
    print(f"Author: {document.author}")
    print(f"From: {document.metadata.get('from')}")
    print(f"Date: {document.metadata.get('date')}")
    print(f"\nContent:\n{'-'*70}")
    print(document.content[:500])
else:
    print("❌ FAILED to parse email")
    print("\nLet me try parsing as generic format...")

    import email
    msg = email.message_from_bytes(raw_email)
    print(f"Subject: {msg.get('Subject')}")
    print(f"From: {msg.get('From')}")
    print(f"To: {msg.get('To')}")
