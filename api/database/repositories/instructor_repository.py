from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from .base import BaseRepository
from ..models import Instructor, CourseSection


class InstructorRepository(BaseRepository[Instructor]):
    def __init__(self, session: Session):
        super().__init__(session, Instructor)
    
    def get_by_employee_id(self, employee_id: str) -> Optional[Instructor]:
        """Get instructor by employee ID"""
        return self.get_one_by(employee_id=employee_id)
    
    def get_with_sections(self, instructor_id: int) -> Optional[Instructor]:
        """Get instructor with all sections"""
        return (
            self.session.query(Instructor)
            .options(joinedload(Instructor.sections))
            .filter(Instructor.id == instructor_id)
            .first()
        )
    
    def get_active_instructors(self) -> List[Instructor]:
        """Get all active instructors"""
        return self.filter_by(is_active=True)
