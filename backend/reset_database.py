#!/usr/bin/env python3
"""
Database Reset Script for Render Deployment
CAUTION: This will DELETE ALL DATA and recreate the database from scratch
"""

import sys
from database.models import Base, engine, SessionLocal, init_database, drop_database
from database.models import Tenant, User, TenantPlan, UserRole
from services.auth_service import AuthService
from datetime import datetime, timezone
import secrets

def reset_database():
    """Drop all tables and recreate from models"""

    print("🗑️  Dropping all tables...")
    try:
        drop_database()
    except Exception as e:
        print(f"Note: {e}")

    print("📦 Creating fresh database schema...")
    init_database()

    print("✅ Database reset complete!")

def create_test_user():
    """Create a test user for verification"""

    print("\n👤 Creating test user...")

    db = SessionLocal()
    try:
        # Create test tenant
        tenant = Tenant(
            id=secrets.token_hex(16),
            name="Test Organization",
            slug="test-org",
            plan=TenantPlan.FREE,
            created_at=datetime.now(timezone.utc)
        )
        db.add(tenant)
        db.flush()

        # Create test user
        auth_service = AuthService(db)

        from services.auth_service import SignupData

        signup_data = SignupData(
            email="test@test.com",
            password="Test123!",
            full_name="Test User",
            organization_name="Test Organization"
        )

        result = auth_service.signup(signup_data, "127.0.0.1", "CLI")

        if result.success:
            print(f"✅ Test user created:")
            print(f"   Email: test@test.com")
            print(f"   Password: Test123!")
            print(f"   Tenant: {tenant.slug}")
        else:
            print(f"❌ Failed to create test user: {result.error}")

    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    print("=" * 60)
    print("DATABASE RESET SCRIPT")
    print("=" * 60)
    print("\n⚠️  WARNING: This will DELETE ALL DATA")
    print("\nThis script will:")
    print("  1. Drop all existing tables")
    print("  2. Recreate schema from models")
    print("  3. Create a test user")
    print("\n" + "=" * 60)

    confirm = input("\nType 'RESET' to confirm: ")

    if confirm != 'RESET':
        print("\n❌ Aborted. No changes made.")
        sys.exit(0)

    try:
        reset_database()
        create_test_user()

        print("\n" + "=" * 60)
        print("✅ ALL DONE!")
        print("=" * 60)
        print("\nYou can now login with:")
        print("  Email: test@test.com")
        print("  Password: Test123!")

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
