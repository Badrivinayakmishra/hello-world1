#!/usr/bin/env python3
"""
Demo SMTP Server for Email Forwarding
Simplified version for localhost demonstration
"""

import asyncio
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope
from email import message_from_bytes
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from connectors.email_forwarding_connector import EmailForwardingConnector
from connectors.base_connector import ConnectorConfig


class DemoEmailHandler:
    """Demo SMTP message handler"""

    def __init__(self):
        print("📧 Demo Email Handler Initialized")

    async def handle_DATA(self, server, session, envelope: Envelope):
        """Handle incoming email"""
        try:
            print(f"\n{'='*60}")
            print(f"📨 RECEIVED EMAIL")
            print(f"{'='*60}")
            print(f"From: {envelope.mail_from}")
            print(f"To: {envelope.rcpt_tos}")
            print(f"Size: {len(envelope.content)} bytes")
            print(f"{'='*60}\n")

            # Get recipient
            recipient = envelope.rcpt_tos[0] if envelope.rcpt_tos else None

            if not recipient:
                print("❌ No recipient found")
                return '550 No valid recipient'

            # Extract tenant ID from email address
            tenant_id = self._extract_tenant_id(recipient)

            if tenant_id:
                print(f"✓ Extracted Tenant ID: {tenant_id}")
            else:
                print(f"⚠️  Using recipient as tenant: {recipient}")
                tenant_id = "demo_tenant"

            # Initialize EmailForwardingConnector
            config = ConnectorConfig(
                connector_type="email_forwarding",
                user_id=tenant_id,
                settings={}
            )

            print(f"✓ Created connector config")

            email_connector = EmailForwardingConnector(config)
            print(f"✓ Initialized EmailForwardingConnector")

            # Parse forwarded email
            raw_email = envelope.content
            document = email_connector.parse_forwarded_email(raw_email)

            if not document:
                print("❌ Failed to parse email (might not be forwarded format)")
                print("\n📧 RAW EMAIL PREVIEW:")
                msg = message_from_bytes(raw_email)
                print(f"Subject: {msg.get('Subject', 'N/A')}")
                print(f"From: {msg.get('From', 'N/A')}")
                print(f"Date: {msg.get('Date', 'N/A')}")
                return '250 Email received but not in forwarded format'

            print(f"\n✅ EMAIL PARSED SUCCESSFULLY!")
            print(f"{'='*60}")
            print(f"📋 PARSED EMAIL DETAILS:")
            print(f"{'='*60}")
            print(f"Title: {document.title}")
            print(f"Author: {document.author}")
            print(f"Source: {document.source}")
            print(f"Document ID: {document.doc_id}")
            print(f"Timestamp: {document.timestamp}")
            print(f"\n📝 METADATA:")
            for key, value in document.metadata.items():
                print(f"  {key}: {value}")

            print(f"\n📄 CONTENT PREVIEW:")
            print(f"{'-'*60}")
            content_lines = document.content.split('\n')[:10]
            for line in content_lines:
                print(line)
            if len(document.content.split('\n')) > 10:
                print("... (truncated)")
            print(f"{'-'*60}")

            print(f"\n✅ EMAIL PROCESSING COMPLETE")
            print(f"{'='*60}\n")

            return '250 Email received and processed successfully'

        except Exception as e:
            print(f"❌ ERROR PROCESSING EMAIL: {e}")
            import traceback
            traceback.print_exc()
            return '451 Error processing email'

    def _extract_tenant_id(self, email_address: str):
        """Extract tenant ID from email address"""
        try:
            local_part = email_address.split('@')[0]
            if local_part.startswith('tenant_'):
                return local_part.replace('tenant_', '')
            return None
        except:
            return None


def main():
    """Run demo SMTP server"""
    host = os.getenv('SMTP_HOST', '0.0.0.0')
    port = int(os.getenv('SMTP_PORT', '2525'))

    handler = DemoEmailHandler()

    print(f"\n{'='*60}")
    print(f"🚀 STARTING DEMO SMTP SERVER")
    print(f"{'='*60}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"{'='*60}\n")

    controller = Controller(
        handler,
        hostname=host,
        port=port,
        ready_timeout=300
    )

    try:
        controller.start()
        print(f"✅ SMTP Server running on {host}:{port}")
        print(f"📬 Ready to receive forwarded emails")
        print(f"\nPress Ctrl+C to stop\n")

        # Keep running
        import time
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n⚠️  Shutting down...")
        controller.stop()
        print("✅ Server stopped\n")


if __name__ == '__main__':
    main()
