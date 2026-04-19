from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    TIMESTAMP,
    Table,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .base import Base, EMBEDDING_DIM
from .enums import EnrollmentStatus, SectionStatus, TermType


course_prerequisites = Table(
    "course_prerequisites",
    Base.metadata,
    Column("course_id", Integer, ForeignKey("courses.id"), primary_key=True),
    Column("prerequisite_id", Integer, ForeignKey("courses.id"), primary_key=True),
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
        backref="prerequisite_for",
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
        CheckConstraint("end_date >= start_date", name="check_valid_term_dates"),
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
    section_type = Column(String(10), nullable=False, default="LECTURE", server_default="LECTURE")
    parent_section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=True)
    instructor_name = Column(String(200), nullable=True)
    status = Column(SQLEnum(SectionStatus, validate_strings=True), default=SectionStatus.SCHEDULED)

    course = relationship("Course", back_populates="sections")
    term = relationship("AcademicTerm", back_populates="sections")
    instructor = relationship("Instructor", back_populates="sections")
    enrollments = relationship("Enrollment", back_populates="section")
    assignments = relationship("Assignment", back_populates="section")
    parent_section = relationship("CourseSection", remote_side="CourseSection.id", foreign_keys=[parent_section_id])
    lab_sections = relationship("CourseSection", back_populates="parent_section", foreign_keys="CourseSection.parent_section_id")
    schedules = relationship("SectionSchedule", back_populates="section", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("section_type IN ('LECTURE', 'LAB')", name="check_section_type"),
    )


class SectionSchedule(Base):
    __tablename__ = "section_schedules"

    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(String(3), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    location = Column(String(150), nullable=True)
    is_online = Column(Boolean, nullable=False, default=False, server_default="false")

    section = relationship("CourseSection", back_populates="schedules")

    __table_args__ = (
        CheckConstraint("day_of_week IN ('MON','TUE','WED','THU','FRI')", name="check_day_of_week"),
    )


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
        UniqueConstraint("student_id", "section_id", name="uq_student_section_enrollment"),
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


class AcademicCalendarEntry(Base):
    __tablename__ = "academic_calendar_entries"

    id = Column(Integer, primary_key=True)
    title_tr = Column(String(300), nullable=False)
    title_en = Column(String(300), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    entry_type = Column(String(50), nullable=False)
    applies_to = Column(String(30), nullable=False, default="undergraduate", server_default="undergraduate")
    academic_year = Column(String(10), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
