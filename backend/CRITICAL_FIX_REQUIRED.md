# CRITICAL SECURITY FIX REQUIRED - IMMEDIATE ACTION

## Issue: Unfiltered Document Query Bypasses Tenant Isolation

**Severity:** CRITICAL  
**File:** `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`  
**Lines:** 1160-1162  
**Risk Level:** Data Breach, Cross-Tenant Access

---

## The Problem

In the document sync/embedding flow, documents are queried twice:

1. **First query (CORRECT - line 1152-1156):**
   ```python
   doc_ids = [db_doc.id for db_doc in db.query(Document).filter(
       Document.tenant_id == tenant_id,      # ✅ Tenant filtered
       Document.connector_id == connector.id,
       Document.embedded_at == None
   ).all()]
   ```

2. **Second query (VULNERABLE - line 1160-1162):**
   ```python
   docs_to_embed = db.query(Document).filter(
       Document.id.in_(doc_ids)  # ⚠️ MISSING TENANT FILTER!
   ).all()
   ```

## Why This Is Critical

The second query retrieves documents using ONLY their IDs, **without verifying tenant ownership**. This means:

1. If the `doc_ids` list is somehow modified or if there's a timing issue, documents from OTHER tenants could be fetched
2. An attacker could potentially craft a request to include document IDs from other tenants
3. Those documents would be processed through the embedding pipeline, exposing their content

## Impact

- Cross-tenant data access
- Confidentiality breach
- Unauthorized access to other organizations' documents
- GDPR/Privacy compliance violation

## The Fix

Add the tenant filter to the second query:

```python
# BEFORE (VULNERABLE):
docs_to_embed = db.query(Document).filter(
    Document.id.in_(doc_ids)
).all()

# AFTER (FIXED):
docs_to_embed = db.query(Document).filter(
    Document.id.in_(doc_ids),
    Document.tenant_id == tenant_id  # ADD THIS LINE
).all()
```

## How to Fix

1. Open `/Users/rishitjain/Downloads/2nd-brain/backend/api/integration_routes.py`
2. Go to line 1160
3. Change the query from:
   ```python
   docs_to_embed = db.query(Document).filter(
       Document.id.in_(doc_ids)
   ).all()
   ```
   
   To:
   ```python
   docs_to_embed = db.query(Document).filter(
       Document.id.in_(doc_ids),
       Document.tenant_id == tenant_id
   ).all()
   ```

4. Test the change
5. Commit and deploy immediately

## Testing the Fix

```python
# Add this test to verify the fix works
def test_embedding_respects_tenant_isolation():
    """Verify that document embedding doesn't access cross-tenant data"""
    # Create two tenants
    tenant1 = create_test_tenant("Org1")
    tenant2 = create_test_tenant("Org2")
    
    # Create documents in each tenant
    doc1 = create_test_document(tenant1, "Doc1")
    doc2 = create_test_document(tenant2, "Doc2")
    
    # Try to embed from tenant1 - should only get doc1
    embedding_service = EmbeddingService()
    result = embedding_service.embed_for_tenant(tenant1.id)
    
    # Verify only doc1 was embedded, not doc2
    assert doc1.id in [doc.id for doc in result['embedded_docs']]
    assert doc2.id not in [doc.id for doc in result['embedded_docs']]
```

## Verification Checklist

- [ ] Fix applied to integration_routes.py line 1160
- [ ] Code tested locally
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Cross-tenant test added
- [ ] Peer reviewed
- [ ] Deployed to production
- [ ] Monitoring enabled for embedding errors

## Related Issues to Address

Also review and fix these related issues found in the security audit:

1. **HIGH:** DocumentChunk model lacks tenant_id field (database/models.py)
2. **HIGH:** GapAnswer model lacks tenant_id field (database/models.py)
3. **MEDIUM:** Inconsistent tenant filtering in knowledge_service.py
4. **MEDIUM:** Soft-deleted document filtering not enforced

See the full report: `TENANT_ISOLATION_SECURITY_REPORT.md`

---

**Timeline:** IMMEDIATE - Deploy within 24 hours  
**Risk if not fixed:** High probability of cross-tenant data breach  
**Testing time:** ~2 hours

Do NOT delay this fix.
