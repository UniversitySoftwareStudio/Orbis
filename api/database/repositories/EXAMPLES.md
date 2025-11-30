# Example templates for future repositories in your school system

"""
# student_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from database.models import Student
from database.repositories.base import BaseRepository


class StudentRepository(BaseRepository[Student]):
    def __init__(self):
        super().__init__(Student)
    
    def get_by_student_id(self, db: Session, student_id: str) -> Optional[Student]:
        return db.query(Student).filter(Student.student_id == student_id).first()
    
    def search_by_name(self, db: Session, name: str) -> List[Student]:
        return db.query(Student).filter(Student.name.ilike(f"%{name}%")).all()
    
    def get_enrolled_in_course(self, db: Session, course_id: int) -> List[Student]:
        # Join with enrollments
        pass


def get_student_repository() -> StudentRepository:
    return StudentRepository()
"""

"""
# professor_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from database.models import Professor
from database.repositories.base import BaseRepository


class ProfessorRepository(BaseRepository[Professor]):
    def __init__(self):
        super().__init__(Professor)
    
    def get_by_email(self, db: Session, email: str) -> Optional[Professor]:
        return db.query(Professor).filter(Professor.email == email).first()
    
    def get_teaching_courses(self, db: Session, professor_id: int) -> List:
        # Return courses taught by this professor
        pass


def get_professor_repository() -> ProfessorRepository:
    return ProfessorRepository()
"""

"""
# enrollment_repository.py
from typing import List
from sqlalchemy.orm import Session
from database.models import Enrollment
from database.repositories.base import BaseRepository


class EnrollmentRepository(BaseRepository[Enrollment]):
    def __init__(self):
        super().__init__(Enrollment)
    
    def enroll_student(self, db: Session, student_id: int, course_id: int) -> Enrollment:
        enrollment = Enrollment(student_id=student_id, course_id=course_id)
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment
    
    def get_student_courses(self, db: Session, student_id: int) -> List:
        return db.query(Enrollment).filter(Enrollment.student_id == student_id).all()


def get_enrollment_repository() -> EnrollmentRepository:
    return EnrollmentRepository()
"""
