"""
Database repositories for UniChatBot
Provides data access layer for all entities
"""

from .base import BaseRepository
from .user_repository import UserRepository
from .student_repository import StudentRepository
from .instructor_repository import InstructorRepository
from .course_repository import CourseRepository
from .enrollment_repository import EnrollmentRepository
from .section_repository import SectionRepository
from .term_repository import TermRepository
from .assignment_repository import AssignmentRepository
from .document_repository import DocumentRepository

__all__ = [
    'BaseRepository',
    'UserRepository',
    'StudentRepository',
    'InstructorRepository',
    'CourseRepository',
    'EnrollmentRepository',
    'SectionRepository',
    'TermRepository',
    'AssignmentRepository',
    'DocumentRepository',
]
