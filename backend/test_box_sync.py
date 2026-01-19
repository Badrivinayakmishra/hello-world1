"""Test Box sync directly with the existing connector"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Check Box SDK
try:
    from box_sdk_gen import BoxClient, BoxOAuth, OAuthConfig, AccessToken
    print("Using new Box SDK (box_sdk_gen)")
    SDK_VERSION = "new"
except ImportError:
    try:
        from boxsdk import OAuth2, Client
        print("Using legacy Box SDK (boxsdk)")
        SDK_VERSION = "legacy"
    except ImportError:
        print("No Box SDK installed!")
        exit(1)

# Get credentials from database
from database.models import SessionLocal, Connector, ConnectorType

db = SessionLocal()
connector = db.query(Connector).filter(
    Connector.connector_type == ConnectorType.BOX
).first()

if not connector:
    print("No Box connector found in database!")
    exit(1)

print(f"Found Box connector: id={connector.id}")
print(f"Access token: {connector.access_token[:30]}..." if connector.access_token else "No access token")
print(f"is_active: {connector.is_active}")
print(f"status: {connector.status}")
print(f"Settings: {connector.settings}")

# Try to connect to Box
if SDK_VERSION == "new":
    config = OAuthConfig(
        client_id=os.getenv("BOX_CLIENT_ID"),
        client_secret=os.getenv("BOX_CLIENT_SECRET"),
    )
    
    token = AccessToken(
        access_token=connector.access_token,
        refresh_token=connector.refresh_token,
        token_type="Bearer"
    )
    
    oauth = BoxOAuth(config, token=token)
    client = BoxClient(auth=oauth)
    
    # Test by getting user info
    print("\nTesting connection...")
    try:
        user = client.users.get_user_me()
        print(f"Connected as: {user.name} ({user.login})")
    except Exception as e:
        print(f"Error getting user: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    
    # List root folder
    print("\nListing root folder (id=0)...")
    try:
        folder = client.folders.get_folder_by_id("0")
        print(f"Root folder name: {folder.name}")
        
        items = client.folders.get_folder_items("0", limit=100)
        print(f"Items response type: {type(items)}")
        print(f"Entries: {items.entries}")
        
        if items.entries:
            print(f"\nFound {len(items.entries)} items:")
            for item in items.entries:
                item_type = item.type if hasattr(item, 'type') else type(item).__name__
                print(f"  - [{item_type}] {item.name} (id: {item.id})")
        else:
            print("No items found in root folder")
    except Exception as e:
        print(f"Error listing folder: {e}")
        import traceback
        traceback.print_exc()

db.close()
