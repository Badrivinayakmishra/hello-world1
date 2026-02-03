# Email Forwarding Integration Guide

## Overview

This implementation replaces Gmail OAuth with an email forwarding system. Users simply forward emails to a unique address instead of granting full inbox access.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   EMAIL FORWARDING FLOW                      │
└─────────────────────────────────────────────────────────────┘

1. User clicks "Connect" on Email Forwarding integration
2. Backend generates unique forwarding address:
   → tenant_<hash>@inbox.yourdomain.com
3. User forwards emails from Gmail/Outlook/Yahoo to this address
4. SMTP server receives email on port 25
5. Email is parsed to extract:
   → Original sender
   → Original subject
   → Original body
   → Original timestamp
6. Email saved to database as Document
7. Processed by classification, extraction, embedding pipelines
```

## Components

### Backend Components

#### 1. **EmailForwardingConnector** (`backend/connectors/email_forwarding_connector.py`)
- Parses forwarded emails from Gmail, Outlook, Yahoo
- Extracts original email from forwarding wrapper
- Creates Document objects
- No OAuth required

#### 2. **SMTP Server** (`backend/services/smtp_server.py`)
- Receives incoming emails on port 25 (or 2525 for testing)
- Async using aiosmtpd
- Routes emails to EmailForwardingConnector
- Saves to database automatically

#### 3. **API Routes** (`backend/api/integration_routes.py`)
- `POST /api/integrations/email-forwarding/setup` - Get unique address
- `GET /api/integrations/email-forwarding/info` - Get forwarding info
- `POST /api/integrations/email-forwarding/verify` - Mark as verified

### Frontend Components

#### 4. **Integration UI** (`frontend/components/integrations/Integrations.tsx`)
- "Email Forwarding" integration card
- EmailForwardingModal shows unique address
- Setup instructions with copy button
- No OAuth flow

### Database

#### 5. **Connector Model**
```sql
connector_type = EMAIL_FORWARDING
settings = {
  "forwarding_email": "tenant_abc123@inbox.yourdomain.com",
  "verified": false,
  "auto_parse": true,
  "include_attachments": false,
  "filter_spam": true
}
```

## Setup Instructions

### 1. Update Environment Variables

Add to `.env`:
```bash
# Email Forwarding
SMTP_HOST=0.0.0.0
SMTP_PORT=25  # Use 2525 for local testing
```

### 2. Run SMTP Server

**Local Development:**
```bash
cd backend
python services/smtp_server.py
```

**Production (Render):**
The SMTP server runs as a separate service defined in `render.yaml`

### 3. Configure Domain DNS (Production)

For `inbox.yourdomain.com`:

**MX Record:**
```
Type: MX
Host: inbox.yourdomain.com
Value: <render-smtp-service-url>
Priority: 10
```

**A Record (alternative):**
```
Type: A
Host: inbox.yourdomain.com
Value: <render-smtp-service-ip>
```

### 4. Test Locally

1. Start SMTP server:
```bash
python backend/services/smtp_server.py
```

2. Send test email using Python:
```python
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Test email body")
msg['Subject'] = 'Test Email'
msg['From'] = 'test@example.com'
msg['To'] = 'tenant_abc123@localhost'

with smtplib.SMTP('localhost', 2525) as server:
    server.send_message(msg)
```

## User Flow

### For Gmail Users

1. **Get Forwarding Address**
   - Click "Connect" on Email Forwarding integration
   - Copy unique address: `tenant_abc123@inbox.yourdomain.com`

2. **Set Up Gmail Forwarding**
   - Open Gmail → Settings → Forwarding and POP/IMAP
   - Click "Add a forwarding address"
   - Paste unique address
   - Click verification link in email

3. **Create Filter (Optional)**
   - Gmail → Settings → Filters and Blocked Addresses
   - Create new filter:
     - From: `@company.com` (work emails only)
     - Forward to: `tenant_abc123@inbox.yourdomain.com`

4. **Forward Emails**
   - Either manually forward important emails
   - Or use auto-forward with filters

### For Outlook Users

1. Get unique forwarding address
2. Outlook → Settings → Mail → Forwarding
3. Enable forwarding to unique address
4. Create rules for selective forwarding

## Email Parsing

The connector handles multiple forwarding formats:

### Gmail Format
```
---------- Forwarded message ---------
From: Original Sender <sender@example.com>
Date: Wed, Jan 29, 2025 at 10:30 AM
Subject: Original Subject
To: recipient@example.com

[Original email body]
```

### Outlook Format
```
________________________________
From: Original Sender
Sent: Wednesday, January 29, 2025 10:30 AM
To: recipient@example.com
Subject: Original Subject

[Original email body]
```

### Generic Format
Falls back to envelope headers if no specific format detected.

## Security

### Address Generation
- Each tenant gets a unique address
- SHA256 hash of tenant_id (12 chars)
- Format: `tenant_<hash>@inbox.yourdomain.com`

### Validation
- SMTP server validates recipient matches tenant
- Only processes emails for valid tenants
- Ignores spam based on settings

### Privacy
- Users control what they forward
- No access to full inbox
- Can revoke at any time (stop forwarding)

## Monitoring

### Check Email Stats

```bash
# View connector status
GET /api/integrations/email-forwarding/info

# Response
{
  "forwarding_email": "tenant_abc123@inbox.yourdomain.com",
  "verified": true,
  "last_sync_at": "2025-01-30T10:00:00Z",
  "total_emails_received": 42
}
```

### SMTP Server Logs

```
📨 Received email
From: user@gmail.com
To: tenant_abc123@inbox.yourdomain.com
✓ Tenant ID: abc123
✓ Found connector: connector_id_123
✓ Parsed email: Important Project Update
✓ Saved to database: doc_id_456
✓ Email processed successfully
```

## Deployment

### Render Configuration

`render.yaml` includes:
1. **Backend API** - Flask app on port 5003
2. **SMTP Server** - Email receiver on port 25
3. **Frontend** - Next.js on port 3000
4. **Database** - PostgreSQL

All services share the same database.

### DNS Setup Required

1. Purchase domain (e.g., `yourdomain.com`)
2. Add subdomain `inbox.yourdomain.com`
3. Point MX record to Render SMTP service
4. Update code:
   - Replace `inbox.yourdomain.com` with your domain
   - In `email_forwarding_connector.py` line 52

### Cost Estimate

- **Render Free Tier**: 3 services (Backend, SMTP, Frontend)
- **Database**: Free PostgreSQL
- **Domain**: ~$12/year
- **Total**: ~$12/year

## Testing

### Unit Tests

```python
# Test email parsing
def test_parse_gmail_forward():
    connector = EmailForwardingConnector(config)
    raw_email = b"---------- Forwarded message ---------..."
    doc = connector.parse_forwarded_email(raw_email)
    assert doc.title == "Original Subject"
    assert doc.metadata["original_sender"] == "sender@example.com"
```

### Integration Tests

```bash
# Send test email via SMTP
python -m smtpd -n -c DebuggingServer localhost:2525

# Forward test email
# Verify it appears in database
```

## Troubleshooting

### Email Not Received

1. Check SMTP server logs
2. Verify DNS MX record
3. Test with local SMTP server
4. Check spam filters

### Parsing Errors

1. View raw email in logs
2. Check forwarding format
3. Add custom parser for your email client
4. Fallback to generic parser

### Database Connection

1. Check DATABASE_URL env var
2. Verify PostgreSQL is running
3. Test connection manually

## Migration from Gmail OAuth

If you have existing Gmail OAuth integration:

1. Export existing email data
2. Disable Gmail OAuth connector
3. Enable Email Forwarding connector
4. Users set up forwarding in Gmail
5. New emails come via forwarding
6. Old emails remain in database

## Future Enhancements

- [ ] Attachment extraction
- [ ] Thread grouping
- [ ] Spam filtering with AI
- [ ] Email templates for verification
- [ ] Webhook notifications
- [ ] Analytics dashboard
- [ ] Multiple forwarding addresses per tenant

## Support

For issues or questions:
1. Check logs: `python services/smtp_server.py`
2. Verify DNS: `nslookup inbox.yourdomain.com`
3. Test locally: Use port 2525
4. Review docs: This guide

---

**Benefits Over OAuth:**
✅ No Gmail API quotas
✅ Users control what's shared
✅ Works with any email provider
✅ No OAuth consent screen
✅ Selective forwarding with filters
✅ Revocable instantly (stop forwarding)

**Trade-offs:**
❌ Requires manual setup (forwarding)
❌ Only gets forwarded emails (not entire inbox)
❌ Requires domain + DNS setup
❌ Users must actively forward emails
