import os
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, DateTime, 
    Boolean, Numeric, Date, Enum as SQLEnum, Table,
    UniqueConstraint, CheckConstraint, func, TIMESTAMP
)
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector
import enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR

class Base(DeclarativeBase):
    pass

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

class UserType(enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


class EnrollmentStatus(enum.Enum):
    ENROLLED = "enrolled"
    DROPPED = "dropped"
    COMPLETED = "completed"


class SectionStatus(enum.Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TermType(enum.Enum):
    FALL = "fall"
    SPRING = "spring"
    SUMMER = "summer"

course_prerequisites = Table(
    'course_prerequisites',
    Base.metadata,
    Column('course_id', Integer, ForeignKey('courses.id'), primary_key=True),
    Column('prerequisite_id', Integer, ForeignKey('courses.id'), primary_key=True)
)

class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(String(500))
    keywords = Column(Text)
    embedding = Column(Vector(EMBEDDING_DIM))
    
    content = relationship("CourseContent", back_populates="course")
    sections = relationship("CourseSection", back_populates="course")
    prerequisites = relationship(
        "Course",
        secondary=course_prerequisites,
        primaryjoin=id == course_prerequisites.c.course_id,
        secondaryjoin=id == course_prerequisites.c.prerequisite_id,
        backref="prerequisite_for"
    )


class CourseContent(Base):
    __tablename__ = "course_content"
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    week_number = Column(Integer, nullable=False)
    topic = Column(Text, nullable=False)
    
    course = relationship("Course", back_populates="content")


class UniversityDocument(Base):
    __tablename__ = "university_documents"
    
    id = Column(Integer, primary_key=True)
    source_url = Column(String(500), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    raw_content = Column(Text, nullable=False)
    summary = Column(Text)
    keywords = Column(Text)
    keyword_embedding = Column(Vector(EMBEDDING_DIM))
    
    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("university_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM))
    
    document = relationship("UniversityDocument", back_populates="chunks")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    
    user_type = Column(SQLEnum(UserType, validate_strings=True), nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("Student", back_populates="user", uselist=False)
    instructor = relationship("Instructor", back_populates="user", uselist=False)


class Student(Base):
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    student_id = Column(String(20), unique=True, nullable=False, index=True)
    gpa = Column(Numeric(3, 2))
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="student")
    enrollments = relationship("Enrollment", back_populates="student")
    
    __table_args__ = (
        CheckConstraint('gpa >= 0.00 AND gpa <= 4.00', name='check_valid_gpa'),
    )


class Instructor(Base):
    __tablename__ = "instructors"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    employee_id = Column(String(20), unique=True, nullable=False)
    title = Column(String(100))
    office_location = Column(String(100))
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="instructor")
    sections = relationship("CourseSection", back_populates="instructor")


class AcademicTerm(Base):
    __tablename__ = "academic_terms"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    
    term_type = Column(SQLEnum(TermType, validate_strings=True), nullable=False)
    
    year = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    
    sections = relationship("CourseSection", back_populates="term")

    __table_args__ = (
        CheckConstraint('end_date >= start_date', name='check_valid_term_dates'),
    )


class CourseSection(Base):
    __tablename__ = "course_sections"
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    term_id = Column(Integer, ForeignKey("academic_terms.id"), nullable=False)
    instructor_id = Column(Integer, ForeignKey("instructors.id"))
    
    section_number = Column(String(10), nullable=False)
    crn = Column(String(50), unique=True, index=True)
    max_enrollment = Column(Integer, default=30)
    current_enrollment = Column(Integer, default=0)
    
    status = Column(SQLEnum(SectionStatus, validate_strings=True), default=SectionStatus.SCHEDULED)
    
    course = relationship("Course", back_populates="sections")
    term = relationship("AcademicTerm", back_populates="sections")
    instructor = relationship("Instructor", back_populates="sections")
    enrollments = relationship("Enrollment", back_populates="section")
    assignments = relationship("Assignment", back_populates="section")


class Enrollment(Base):
    __tablename__ = "enrollments"
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("course_sections.id"), nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    
    status = Column(SQLEnum(EnrollmentStatus, validate_strings=True), default=EnrollmentStatus.ENROLLED)
    
    final_grade_numeric = Column(Numeric(5, 2))
    final_grade_letter = Column(String(2))
    
    student = relationship("Student", back_populates="enrollments")
    section = relationship("CourseSection", back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint('student_id', 'section_id', name='uq_student_section_enrollment'),
    )


class Assignment(Base):
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("course_sections.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    due_date = Column(DateTime, nullable=False)
    max_points = Column(Numeric(5, 2), nullable=False)
    is_published = Column(Boolean, default=False)
    
    section = relationship("CourseSection", back_populates="assignments")

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    url = Column(Text, nullable=False)
    title = Column(Text)
    content = Column(Text)
    language = Column(String(10))
    type = Column(String(50))

    metadata_ = Column("metadata", JSONB, default={})
    embedding = Column(Vector(EMBEDDING_DIM))

    search_vector = Column(TSVECTOR)

    created_at = Column(TIMESTAMP, server_default=func.now())

    versioned_embeddings = relationship("KnowledgeBaseEmbedding", back_populates="kb_entry")


class EmbeddingModel(Base):
    __tablename__ = "embedding_models"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    dimension = Column(Integer, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    embeddings = relationship("KnowledgeBaseEmbedding", back_populates="model")

    __table_args__ = (
        UniqueConstraint('name', 'version', name='uq_embedding_model_name_version'),
    )


class KnowledgeBaseEmbedding(Base):
    __tablename__ = "knowledge_base_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    kb_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("embedding_models.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = Column(Vector(), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    kb_entry = relationship("KnowledgeBase", back_populates="versioned_embeddings")
    model = relationship("EmbeddingModel", back_populates="embeddings")

    __table_args__ = (
        UniqueConstraint('kb_id', 'model_id', name='uq_kb_model_embedding'),
    )
