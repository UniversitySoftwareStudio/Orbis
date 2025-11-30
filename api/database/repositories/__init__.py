"""
Repository layer for database access.

Each repository handles data access for a specific entity.
Import repositories from here for clean imports throughout the app.

Example:
    from database.repositories import get_course_repository
    
    course_repo = get_course_repository()
    courses = course_repo.get_all(db)
"""

from database.repositories.base import BaseRepository
from database.repositories.course_repository import (
    CourseRepository,
    get_course_repository
)

# As you add more repositories, export them here:
# from database.repositories.student_repository import StudentRepository, get_student_repository
# from database.repositories.professor_repository import ProfessorRepository, get_professor_repository
# from database.repositories.enrollment_repository import EnrollmentRepository, get_enrollment_repository

__all__ = [
    "BaseRepository",
    "CourseRepository",
    "get_course_repository",
    # Add new repositories to __all__ as you create them
]
