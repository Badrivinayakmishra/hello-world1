"""
Email Notification Service
Send email notifications for sync completions and important events.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, Dict, List

# Email configuration from environment
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', 'noreply@2ndbrain.ai')
SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', '2nd Brain')


class EmailNotificationService:
    """
    Service for sending email notifications.

    Features:
    - Sync completion notifications
    - Error alerts
    - HTML email templates
    - SMTP with TLS

    Configuration (environment variables):
        SMTP_HOST: SMTP server hostname (default: smtp.gmail.com)
        SMTP_PORT: SMTP server port (default: 587)
        SMTP_USER: SMTP username/email
        SMTP_PASSWORD: SMTP password or app password
        SMTP_FROM_EMAIL: From email address
        SMTP_FROM_NAME: From name

    Example (Gmail):
        SMTP_HOST=smtp.gmail.com
        SMTP_PORT=587
        SMTP_USER=your-email@gmail.com
        SMTP_PASSWORD=your-app-password  # Generate at https://myaccount.google.com/apppasswords
        SMTP_FROM_EMAIL=noreply@yourdomain.com
        SMTP_FROM_NAME="2nd Brain"
    """

    def __init__(self):
        self.enabled = bool(SMTP_USER and SMTP_PASSWORD)

        if not self.enabled:
            print("[EmailService] Email notifications disabled (SMTP not configured)")
        else:
            print(f"[EmailService] Email notifications enabled (SMTP: {SMTP_HOST}:{SMTP_PORT})")

    def send_sync_complete_notification(
        self,
        user_email: str,
        connector_type: str,
        total_items: int,
        processed_items: int,
        failed_items: int,
        duration_seconds: float,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Send notification when sync completes.

        Args:
            user_email: Email address of user
            connector_type: Type of connector (gmail, slack, box, github)
            total_items: Total items found
            processed_items: Successfully processed items
            failed_items: Failed items
            duration_seconds: Sync duration
            error_message: Error message if sync failed

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            print("[EmailService] Skipping notification (not configured)")
            return False

        # Format duration
        if duration_seconds < 60:
            duration_str = f"{duration_seconds:.1f} seconds"
        else:
            minutes = int(duration_seconds / 60)
            seconds = int(duration_seconds % 60)
            duration_str = f"{minutes}m {seconds}s"

        # Determine status
        if error_message:
            status = "Failed"
            status_color = "#DC2626"  # Red
        elif failed_items > 0:
            status = "Completed with errors"
            status_color = "#F59E0B"  # Orange
        else:
            status = "Completed successfully"
            status_color = "#10B981"  # Green

        # Build HTML email
        subject = f"Sync {status}: {connector_type.title()}"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #374151;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px 8px 0 0;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .content {{
            background: #ffffff;
            padding: 30px;
            border: 1px solid #E5E7EB;
            border-top: none;
        }}
        .status {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            color: white;
            background-color: {status_color};
            margin: 10px 0;
        }}
        .stats {{
            background: #F9FAFB;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .stat-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #E5E7EB;
        }}
        .stat-row:last-child {{
            border-bottom: none;
        }}
        .stat-label {{
            color: #6B7280;
            font-weight: 500;
        }}
        .stat-value {{
            color: #111827;
            font-weight: 600;
        }}
        .error {{
            background: #FEF2F2;
            border-left: 4px solid #DC2626;
            padding: 16px;
            border-radius: 4px;
            margin: 20px 0;
            color: #991B1B;
        }}
        .footer {{
            background: #F9FAFB;
            padding: 20px;
            border-radius: 0 0 8px 8px;
            border: 1px solid #E5E7EB;
            border-top: none;
            text-align: center;
            color: #6B7280;
            font-size: 14px;
        }}
        .button {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 12px 24px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧠 2nd Brain Sync Complete</h1>
    </div>
    <div class="content">
        <p>Hello,</p>
        <p>Your <strong>{connector_type.title()}</strong> integration sync has finished.</p>

        <div class="status">{status}</div>

        <div class="stats">
            <div class="stat-row">
                <span class="stat-label">Total Items Found</span>
                <span class="stat-value">{total_items:,}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Successfully Processed</span>
                <span class="stat-value">{processed_items:,}</span>
            </div>
            {f'<div class="stat-row"><span class="stat-label">Failed</span><span class="stat-value" style="color: #DC2626;">{failed_items:,}</span></div>' if failed_items > 0 else ''}
            <div class="stat-row">
                <span class="stat-label">Duration</span>
                <span class="stat-value">{duration_str}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Completed At</span>
                <span class="stat-value">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</span>
            </div>
        </div>

        {f'<div class="error"><strong>Error:</strong> {error_message}</div>' if error_message else ''}

        <p>Your knowledge base has been updated with the latest information from {connector_type.title()}.</p>

        <center>
            <a href="http://localhost:3006/documents" class="button">View Documents</a>
        </center>
    </div>
    <div class="footer">
        <p>This is an automated notification from 2nd Brain.</p>
        <p>You're receiving this because you enabled email notifications for sync completions.</p>
    </div>
</body>
</html>
"""

        text_body = f"""
2nd Brain Sync Complete

Your {connector_type.title()} integration sync has finished.

Status: {status}

Stats:
- Total Items Found: {total_items:,}
- Successfully Processed: {processed_items:,}
{f'- Failed: {failed_items:,}' if failed_items > 0 else ''}
- Duration: {duration_str}
- Completed At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

{f'Error: {error_message}' if error_message else ''}

Your knowledge base has been updated with the latest information from {connector_type.title()}.

View your documents: http://localhost:3006/documents
"""

        return self._send_email(
            to_email=user_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )

    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> bool:
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
            msg['To'] = to_email

            # Attach parts
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Connect and send
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()

            print(f"[EmailService] Sent notification to {to_email}: {subject}")
            return True

        except Exception as e:
            print(f"[EmailService] Failed to send email to {to_email}: {e}")
            import traceback
            traceback.print_exc()
            return False


# Global instance
_email_service = None

def get_email_service() -> EmailNotificationService:
    """Get the global EmailNotificationService instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailNotificationService()
    return _email_service
