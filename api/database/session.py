import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Import Base from models (single source of truth)
from .models import Base

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/orbisdb"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database with pgvector extension and create all tables"""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    # This will now find all models because Base is imported from models.py
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized")


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
