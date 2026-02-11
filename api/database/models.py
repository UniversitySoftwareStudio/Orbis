import enum
from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, func
# Import Enum explicitly as SQLEnum to avoid confusion with Python's enum
from sqlalchemy import Enum as SQLEnum 
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    pass

# Define the Enum exactly as it exists in the DB
class UserType(str, enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    
    # FIX: Explicitly define this as a Postgres Enum named 'usertype'
    # This aligns Python with the existing Database schema.
    user_type = Column(SQLEnum(UserType, name="usertype"), nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    url = Column(Text, nullable=False)
    title = Column(Text)
    content = Column(Text)
    language = Column(String(10))
    type = Column(String(50))
    
    metadata_ = Column("metadata", JSONB, default={})
    embedding = Column(Vector(384))
    
    created_at = Column(TIMESTAMP, server_default=func.now())