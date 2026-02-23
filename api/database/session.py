import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Import Base from models (single source of truth)
from .models import Base

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")

# If a full DATABASE_URL isn't provided, construct it from individual DB_* env vars.
if not DATABASE_URL:
    db_user = os.getenv("DB_USER", "user")
    db_password = os.getenv("DB_PASSWORD", "password")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "orbisdb")
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes the DB tables."""
    try:
        # Enable pgvector extension
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        
        # Create all tables defined in models.py
        Base.metadata.create_all(bind=engine)
        print("✅ Database initialized successfully.")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")


def reset_db():
    """Drop and recreate all tables"""
    Base.metadata.drop_all(bind=engine)
    print("✓ Tables dropped")
    Base.metadata.create_all(bind=engine)
    print("✓ Tables recreated!")


def get_db():
    """Get database session for routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()