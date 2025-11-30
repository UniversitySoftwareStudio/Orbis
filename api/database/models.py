from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()
# Default dimension for all-MiniLM-L6-v2 model
# If you change the model, update this value accordingly
EMBEDDING_DIM = 384


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
