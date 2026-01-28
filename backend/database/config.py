"""
Database Configuration
Supports both PostgreSQL (production) and SQLite (development)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration
DATABASE_TYPE = os.getenv("DATABASE_TYPE", "sqlite")  # 'sqlite' or 'postgresql'

# SQLite configuration (default for development)
SQLITE_DB_PATH = Path(__file__).parent.parent / "data" / "secondbrain.db"

# PostgreSQL configuration (for production)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "secondbrain")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.urandom(32).hex())
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24 * 7  # 7 days in seconds
JWT_REFRESH_TOKEN_EXPIRES = 60 * 60 * 24 * 30  # 30 days in seconds

# Password hashing configuration
BCRYPT_ROUNDS = 12  # Work factor for bcrypt


def get_database_url() -> str:
    """Get the database URL based on configuration"""
    # First check for DATABASE_URL (used by Render and other platforms)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    # Otherwise construct from individual variables
    if DATABASE_TYPE == "postgresql":
        return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    else:
        # SQLite
        SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{SQLITE_DB_PATH}"
