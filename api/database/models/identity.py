from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .enums import UserType


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
    profile = relationship("UserProfile", back_populates="user", uselist=False)


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
        CheckConstraint("gpa >= 0.00 AND gpa <= 4.00", name="check_valid_gpa"),
    )


class UserProfile(Base):
    """Enriched user context — works for students, instructors, and admins.

    Populated manually, by scripts, or injected as dummy data.
    The user agent reads this to build a rich context blob before
    reasoning over regulation rules for any user in the system.
    """
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Role-specific identity (students)
    department = Column(String(200))       # e.g. "Computer Engineering"
    faculty = Column(String(200))          # e.g. "Faculty of Engineering"
    program_level = Column(String(50))     # "undergraduate" | "graduate" | "associate"
    academic_year = Column(Integer)        # year in program (students)
    semester_number = Column(Integer)      # cumulative semesters completed
    total_credits_completed = Column(Integer)
    total_credits_enrolled = Column(Integer)

    # Role-specific identity (instructors / staff)
    title = Column(String(100))            # e.g. "Associate Professor", "Registrar"
    office = Column(String(200))           # e.g. "Registrar's Office"
    responsibilities = Column(String(500)) # free-text, e.g. "student advising, thesis review"

    # Status flags (any role)
    is_on_probation = Column(Boolean, default=False)
    has_advisor_hold = Column(Boolean, default=False)
    has_financial_hold = Column(Boolean, default=False)
    is_exchange_student = Column(Boolean, default=False)
    is_double_major = Column(Boolean, default=False)
    is_minor = Column(Boolean, default=False)

    # Free-form injection — anything worth adding to context
    # e.g. {"scholarship": "need-based", "thesis_topic": "...", "internship_status": "completed"}
    extra_context = Column(JSONB, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")


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
