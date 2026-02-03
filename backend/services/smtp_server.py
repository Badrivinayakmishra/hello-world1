"""
SMTP Server for Receiving Forwarded Emails
Listens for incoming emails and processes them into the knowledge base.
"""

import asyncio
import os
from datetime import datetime
from typing import Optional
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP as SMTPProtocol, Envelope, Session
from email import message_from_bytes
from sqlalchemy.orm import Session as DBSession

from database.config import SessionLocal
from database.models import Connector, Document as DBDocument, ConnectorType, DocumentStatus
from connectors.email_forwarding_connector import EmailForwardingConnector
from connectors.base_connector import ConnectorConfig


class EmailHandler:
    """
    SMTP message handler that processes incoming forwarded emails.
    """

    def __init__(self, db_session_factory=None):
        self.db_session_factory = db_session_factory or SessionLocal
        print("📧 Email handler initialized")

    async def handle_DATA(self, server, session, envelope: Envelope):
        """
        Called when email is received via SMTP.

        Args:
            server: SMTP server instance
            session: SMTP session
            envelope: Email envelope containing message data
        """
        try:
            print(f"\n{'='*60}")
            print(f"📨 Received email")
            print(f"From: {envelope.mail_from}")
            print(f"To: {envelope.rcpt_tos}")
            print(f"{'='*60}")

            # Get recipient address (should be tenant_xxx@inbox.yourdomain.com)
            recipient = envelope.rcpt_tos[0] if envelope.rcpt_tos else None

            if not recipient:
                print("❌ No recipient found")
                return '550 No valid recipient'

            # Extract tenant ID from email address
            tenant_id = self._extract_tenant_id(recipient)

            if not tenant_id:
                print(f"❌ Invalid recipient format: {recipient}")
                return '550 Invalid recipient address'

            print(f"✓ Tenant ID: {tenant_id}")

            # Find connector for this tenant
            db = self.db_session_factory()
            try:
                connector = db.query(Connector).filter(
                    Connector.tenant_id == tenant_id,
                    Connector.connector_type == ConnectorType.EMAIL_FORWARDING,
                    Connector.is_active == True
                ).first()

                if not connector:
                    print(f"❌ No email forwarding connector found for tenant {tenant_id}")
                    return '550 Email forwarding not configured for this address'

                print(f"✓ Found connector: {connector.id}")

                # Initialize EmailForwardingConnector
                config = ConnectorConfig(
                    connector_type="email_forwarding",
                    user_id=tenant_id,
                    settings=connector.settings or {}
                )

                email_connector = EmailForwardingConnector(config)

                # Parse forwarded email
                raw_email = envelope.content
                document = email_connector.parse_forwarded_email(raw_email)

                if not document:
                    print("❌ Failed to parse email")
                    return '250 Email received but could not be parsed'

                print(f"✓ Parsed email: {document.title}")

                # Save to database
                db_doc = DBDocument(
                    tenant_id=tenant_id,
                    connector_id=connector.id,
                    external_id=document.doc_id,
                    source_type="email",
                    title=document.title,
                    content=document.content,
                    doc_metadata=document.metadata,
                    sender=document.metadata.get('from'),
                    sender_email=document.metadata.get('original_sender'),
                    source_created_at=document.timestamp,
                    status=DocumentStatus.PENDING,
                    embedding_generated=False
                )

                db.add(db_doc)
                db.commit()

                print(f"✓ Saved to database: {db_doc.id}")

                # Update connector stats
                connector.last_sync_at = datetime.utcnow()
                connector.total_items_synced = (connector.total_items_synced or 0) + 1
                connector.last_sync_status = "success"
                connector.last_sync_items_count = 1
                db.commit()

                print(f"✓ Email processed successfully")
                print(f"{'='*60}\n")

                return '250 Email received and processed'

            finally:
                db.close()

        except Exception as e:
            print(f"❌ Error processing email: {e}")
            import traceback
            traceback.print_exc()
            return '451 Error processing email'

    def _extract_tenant_id(self, email_address: str) -> Optional[str]:
        """
        Extract tenant ID from email address.

        Format: tenant_<hash>@inbox.yourdomain.com
        Returns: The hash portion
        """
        try:
            # Extract local part (before @)
            local_part = email_address.split('@')[0]

            # Extract hash from tenant_<hash>
            if local_part.startswith('tenant_'):
                tenant_hash = local_part.replace('tenant_', '')
                return tenant_hash

            return None

        except:
            return None


class SMTPServer:
    """
    Async SMTP server for receiving forwarded emails.
    """

    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 2525,
        require_auth: bool = False
    ):
        self.host = host
        self.port = port
        self.require_auth = require_auth
        self.controller = None
        self.handler = EmailHandler()

    def start(self):
        """Start the SMTP server"""
        print(f"\n{'='*60}")
        print(f"🚀 Starting SMTP Server")
        print(f"Host: {self.host}")
        print(f"Port: {self.port}")
        print(f"Authentication: {'Enabled' if self.require_auth else 'Disabled'}")
        print(f"{'='*60}\n")

        self.controller = Controller(
            self.handler,
            hostname=self.host,
            port=self.port,
            ready_timeout=300
        )

        self.controller.start()

        print(f"✅ SMTP Server running on {self.host}:{self.port}")
        print(f"📬 Ready to receive forwarded emails\n")

    def stop(self):
        """Stop the SMTP server"""
        if self.controller:
            print("\n🛑 Stopping SMTP Server...")
            self.controller.stop()
            print("✅ SMTP Server stopped\n")


def main():
    """
    Run standalone SMTP server for development/testing.
    """
    # Get configuration from environment
    host = os.getenv('SMTP_HOST', '0.0.0.0')
    port = int(os.getenv('SMTP_PORT', '2525'))

    # Create and start server
    server = SMTPServer(host=host, port=port)

    try:
        server.start()

        # Keep running
        print("Press Ctrl+C to stop the server\n")
        asyncio.get_event_loop().run_forever()

    except KeyboardInterrupt:
        print("\n⚠️  Received interrupt signal")
        server.stop()


if __name__ == '__main__':
    main()
