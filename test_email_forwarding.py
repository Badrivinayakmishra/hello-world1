#!/usr/bin/env python3
"""
Test script for email forwarding integration.
Sends a test email to the SMTP server.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

def send_test_email(
    to_address="tenant_abc123@localhost",
    smtp_host="localhost",
    smtp_port=2525
):
    """
    Send a test forwarded email to the SMTP server.

    Args:
        to_address: The unique forwarding address
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port
    """

    # Create a multipart message (simulating Gmail forward)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Fwd: Important Project Update'
    msg['From'] = 'forwarder@gmail.com'
    msg['To'] = to_address

    # Create the body with Gmail forwarding format
    text_body = """
---------- Forwarded message ---------
From: John Doe <john.doe@company.com>
Date: Wed, Jan 30, 2025 at 10:30 AM
Subject: Important Project Update
To: team@company.com

Hi team,

I wanted to give you an update on the Q1 roadmap. We've made significant progress on the following:

1. Email forwarding integration - COMPLETED
2. SMTP server deployment - IN PROGRESS
3. Frontend UI updates - COMPLETED

Key decisions made:
- Using self-hosted SMTP instead of Gmail API
- Each tenant gets unique forwarding address
- No OAuth required

Next steps:
- Deploy to Render
- Set up DNS records
- Test with real email clients

Let me know if you have any questions.

Best regards,
John
"""

    # Attach the text body
    part = MIMEText(text_body, 'plain')
    msg.attach(part)

    try:
        print(f"\n{'='*60}")
        print(f"Sending test email to {to_address}")
        print(f"SMTP Server: {smtp_host}:{smtp_port}")
        print(f"{'='*60}\n")

        # Connect to SMTP server and send
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            # server.set_debuglevel(1)  # Uncomment for verbose output
            server.send_message(msg)

        print(f"✅ Test email sent successfully!")
        print(f"\nCheck the SMTP server logs to verify it was received and processed.\n")

    except Exception as e:
        print(f"❌ Error sending email: {e}")
        sys.exit(1)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Send test email to SMTP server')
    parser.add_argument('--to', default='tenant_abc123@localhost',
                       help='Recipient email address (default: tenant_abc123@localhost)')
    parser.add_argument('--host', default='localhost',
                       help='SMTP server host (default: localhost)')
    parser.add_argument('--port', type=int, default=2525,
                       help='SMTP server port (default: 2525)')

    args = parser.parse_args()

    send_test_email(
        to_address=args.to,
        smtp_host=args.host,
        smtp_port=args.port
    )
