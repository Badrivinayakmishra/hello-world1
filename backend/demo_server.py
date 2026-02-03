"""
Demo server for Email Forwarding Integration
Minimal Flask app to demonstrate the frontend UI
"""

import os
import secrets
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# CORS
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://localhost:3006", "*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Mock email forwarding routes
@app.route('/api/integrations/email-forwarding/setup', methods=['POST', 'OPTIONS'])
def setup_email_forwarding():
    if request.method == 'OPTIONS':
        return '', 200

    # Generate a demo forwarding email
    import hashlib
    tenant_id = "demo_user_123"
    tenant_hash = hashlib.sha256(tenant_id.encode()).hexdigest()[:12]
    forwarding_email = f"tenant_{tenant_hash}@inbox.yourdomain.com"

    return jsonify({
        "success": True,
        "forwarding_email": forwarding_email,
        "connector_id": "conn_demo_123",
        "message": "Email forwarding configured successfully"
    })

@app.route('/api/integrations/email-forwarding/info', methods=['GET', 'OPTIONS'])
def get_email_forwarding_info():
    if request.method == 'OPTIONS':
        return '', 200

    import hashlib
    tenant_id = "demo_user_123"
    tenant_hash = hashlib.sha256(tenant_id.encode()).hexdigest()[:12]
    forwarding_email = f"tenant_{tenant_hash}@inbox.yourdomain.com"

    return jsonify({
        "success": True,
        "forwarding_email": forwarding_email,
        "verified": True,
        "last_sync_at": "2025-01-30T12:00:00Z",
        "total_emails_received": 42,
        "connector_id": "conn_demo_123"
    })

@app.route('/api/integrations', methods=['GET', 'OPTIONS'])
def list_integrations():
    if request.method == 'OPTIONS':
        return '', 200

    return jsonify({
        "success": True,
        "integrations": [
            {
                "id": "conn_gmail_demo",
                "type": "gmail",
                "name": "Email Forwarding",
                "status": "connected",
                "last_sync_at": "2025-01-30T12:00:00Z",
                "total_items_synced": 42
            }
        ]
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5003))
    print(f"\n{'='*60}")
    print(f"🚀 Demo Server Starting")
    print(f"{'='*60}")
    print(f"Backend API: http://localhost:{port}")
    print(f"Email Forwarding Routes:")
    print(f"  POST /api/integrations/email-forwarding/setup")
    print(f"  GET  /api/integrations/email-forwarding/info")
    print(f"  GET  /api/integrations")
    print(f"{'='*60}\n")

    app.run(host='0.0.0.0', port=port, debug=False)
