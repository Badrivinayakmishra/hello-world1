# Reset Database & Create Test Users - Quick Start Guide

## What We Created

I've built comprehensive scripts to:
1. **Delete all existing data** from PostgreSQL, Pinecone, and Redis
2. **Create 4 test tenants** (organizations) with different subscription plans
3. **Create 10 test users** with proper tenant isolation
4. **Verify multi-tenant security** - each tenant's data is completely isolated

---

## How to Run (Cloud Deployment - Render)

Since everything is on Render, you'll need to SSH into your backend service to run these scripts.

### **Step 1: Access Render Shell**

1. Go to Render dashboard: https://dashboard.render.com/
2. Click on **"twondbrain-backend-docker"**
3. Click **"Shell"** in the left sidebar
4. You'll get a terminal connected to your backend server

### **Step 2: Run Reset Script**

In the Render shell:

```bash
cd /opt/render/project/src/backend
python scripts/reset_database.py --force
```

This will:
- ✅ Drop all PostgreSQL tables and recreate them
- ✅ Delete all Pinecone vectors (embeddings)
- ✅ Clear Redis cache

### **Step 3: Run Seed Script**

In the same Render shell:

```bash
python scripts/seed_database.py
```

This will:
- ✅ Create 4 tenant organizations
- ✅ Create 10 users across tenants
- ✅ Verify tenant isolation
- ✅ Print login credentials

### **Step 4: Get Login Credentials**

The seed script will output something like:

```
========================================================================
SEED DATA SUMMARY
========================================================================

📁 acme.com
  --------------------------------------------------------------------
  👤 Alice Admin           (admin)
     Email:    admin@acme.com
     Password: admin123
     User ID:  456789ab-cdef-0123-4567-89abcdef0123
     Tenant:   01234567-89ab-cdef-0123-456789abcdef

  👤 Bob User              (member)
     Email:    user@acme.com
     Password: user123
     ...

📁 startup.io
  --------------------------------------------------------------------
  👤 Diana Founder         (admin)
     Email:    founder@startup.io
     Password: founder123
     ...

========================================================================
LOGIN INSTRUCTIONS
========================================================================

RECOMMENDED TEST ACCOUNTS:
  • admin@acme.com / admin123 (Enterprise admin)
  • founder@startup.io / founder123 (Professional admin)
  • test@freetier.org / test123 (Free tier)
```

---

## Test Accounts Created

### **Acme Corporation** (Enterprise Plan - acme.com)
| Email | Password | Role |
|-------|----------|------|
| admin@acme.com | admin123 | Admin |
| user@acme.com | user123 | Member |
| viewer@acme.com | viewer123 | Viewer |
| demo@acme.com | demo123 | Member |

### **Startup Inc** (Professional Plan - startup.io)
| Email | Password | Role |
|-------|----------|------|
| founder@startup.io | founder123 | Admin |
| engineer@startup.io | engineer123 | Member |
| demo@startup.io | demo123 | Member |

### **Small Business LLC** (Starter Plan - smallbiz.com)
| Email | Password | Role |
|-------|----------|------|
| owner@smallbiz.com | owner123 | Admin |
| employee@smallbiz.com | employee123 | Member |

### **Free Tier Co** (Free Plan - freetier.org)
| Email | Password | Role |
|-------|----------|------|
| test@freetier.org | test123 | Admin |

---

## Verify Tenant Isolation

### **Test 1: Login as Acme User**

1. Go to: https://twondbrain-frontend.onrender.com
2. Click **"Login"**
3. Login with: **admin@acme.com** / **admin123**
4. You should be logged in as "Alice Admin" from Acme Corporation
5. Any documents you upload will belong to Acme tenant only

### **Test 2: Login as Startup User**

1. **Logout** from Acme account
2. Login with: **founder@startup.io** / **founder123**
3. You should be logged in as "Diana Founder" from Startup Inc
4. You **cannot see** Acme's documents
5. You **cannot access** Acme's data

### **Test 3: Verify API Isolation**

Try to access another tenant's data via API:

```bash
# Login as Acme admin
curl -X POST https://twondbrain-backend-docker.onrender.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@acme.com", "password": "admin123"}'

# Copy the access_token from response

# Try to list documents (should only see Acme's documents)
curl -X GET https://twondbrain-backend-docker.onrender.com/api/documents \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Should return only documents for Acme tenant
```

---

## What Each Tenant Plan Gets

| Plan | Search/min | Sync/hour | Gap Analysis/day | Features |
|------|------------|-----------|------------------|----------|
| **Free** | 20 | 5 | 5 | Basic features |
| **Starter** | 60 | 10 | 10 | + Classifications |
| **Professional** | 200 | 50 | 50 | + Videos, Slack bot |
| **Enterprise** | 500 | 100 | 100 | + Priority support, SLA |

---

## Troubleshooting

### Can't access Render shell?

**Alternative method using Render's API:**

```bash
# Install Render CLI (one time)
npm install -g @render-com/cli

# Login to Render
render login

# Connect to shell
render shell twondbrain-backend-docker

# Then run the scripts as normal
cd backend
python scripts/reset_database.py --force
python scripts/seed_database.py
```

### Script fails with database connection error?

Check that DATABASE_URL environment variable is set in Render:
1. Go to backend service → Environment
2. Verify `DATABASE_URL` exists and points to your PostgreSQL instance

### Script succeeds but can't login?

Check backend logs:
1. Go to backend service → Logs
2. Look for errors during authentication
3. Verify backend is running (should see "✓ Database initialized")

### Want to add more test users?

Edit `backend/scripts/seed_database.py` and add more users to the `USERS` list:

```python
USERS = [
    # ... existing users ...
    {
        "email": "newuser@acme.com",
        "password": "password123",
        "name": "New User",
        "tenant_domain": "acme.com",
        "role": UserRole.MEMBER,
    },
]
```

Then re-run: `python scripts/seed_database.py --force`

---

## Next Steps After Reset

1. **Login with test accounts** ✅
2. **Connect integrations**:
   - Go to Integrations page
   - Connect Gmail, Slack, or Box
   - Sync some documents
3. **Test classification**:
   - Upload documents
   - Run classification
   - Confirm work vs personal
4. **Test knowledge gaps**:
   - Click "Find Gaps"
   - Review detected gaps
   - Answer some questions
5. **Test RAG search**:
   - Go to Chat
   - Ask questions
   - Verify citations
6. **Test tenant isolation**:
   - Login as different tenants
   - Verify each can only see their own data

---

## Files Created

All scripts are in `backend/scripts/`:

| File | Purpose |
|------|---------|
| `reset_database.py` | Clear all data (PostgreSQL, Pinecone, Redis) |
| `seed_database.py` | Create test tenants and users |
| `reset_and_seed.sh` | Convenience script to run both |
| `README.md` | Full documentation |

---

## Important Notes

⚠️ **DESTRUCTIVE OPERATION**
- The reset script **deletes ALL data**
- This **cannot be undone**
- Only use in development/testing
- **DO NOT** run in production with real customer data

✅ **Safe for Testing**
- These scripts are perfect for development
- Create fresh, clean test environment
- Demonstrate proper multi-tenant architecture
- Include proper security (bcrypt, JWT, isolation)

---

**Created**: 2026-01-30
**Ready to run**: Yes ✅
