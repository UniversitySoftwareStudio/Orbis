import os
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()
# Read dimension from ENV, defaulting to 384 (MiniLM)
# If you switch models in .env, you must also update this or reset your DB!
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))


class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(String(500))
    keywords = Column(Text)  # Keywords describing the course
    embedding = Column(Vector(EMBEDDING_DIM))  # Dynamic dimension based on model
    
    content = relationship("CourseContent", back_populates="course") # Relationship


class CourseContent(Base):
    __tablename__ = "course_content"
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    week_number = Column(Integer, nullable=False)
    topic = Column(Text, nullable=False)
    
    course = relationship("Course", back_populates="content")


class UniversityDocument(Base):
    """
    Represents a raw, unchunked document scraped from a university resource.
    This serves as the 'Ground Truth' corpus for chunking experiments.
    """
    __tablename__ = "university_documents"
    
    id = Column(Integer, primary_key=True)
    source_url = Column(String(500), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    
    # The full, raw text content (potentially 20+ pages)
    # We store this intact to allow for different chunking strategies later
    raw_content = Column(Text, nullable=False)
    
    # High-level metadata describing the document's purpose
    summary = Column(Text)   # "What is it all about"
    keywords = Column(Text)  # Searchable tags
    
    # 2. Summary Embedding: Best for "Where are the rules about probation?"
    keyword_embedding = Column(Vector(EMBEDDING_DIM))
    
    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentChunk(Base):
    """
    Represents a specific section of a UniversityDocument.
    Used for fine-grained retrieval.
    """
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("university_documents.id"), nullable=False)
    
    chunk_index = Column(Integer, nullable=False)  # Order within document
    content = Column(Text, nullable=False)         # The actual text of the chunk
    embedding = Column(Vector(EMBEDDING_DIM))      # Vector representation of this chunk
    
    document = relationship("UniversityDocument", back_populates="chunks")




