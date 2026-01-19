"""Check all connectors in database"""
from database.models import SessionLocal, Connector, ConnectorType

db = SessionLocal()

# Get ALL connectors
connectors = db.query(Connector).all()

print(f"Total connectors: {len(connectors)}")
for c in connectors:
    print(f"\nConnector ID: {c.id}")
    print(f"  Type: {c.connector_type}")
    print(f"  Name: {c.name}")
    print(f"  Status: {c.status}")
    print(f"  is_active: {c.is_active}")
    print(f"  tenant_id: {c.tenant_id}")
    print(f"  access_token: {'Yes' if c.access_token else 'No'}")

db.close()
