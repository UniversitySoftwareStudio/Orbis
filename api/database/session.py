import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database.models import Base
import os

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/orbisdb"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()  # Important: Create Extension requires a commit

    Base.metadata.create_all(bind=engine)


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


if __name__ == "__main__":
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()  # Important: Create Extension requires a commit
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_db()
    else:
        init_db()
