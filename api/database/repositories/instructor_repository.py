from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_
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
        stmt = (
            select(Instructor)
            .options(joinedload(Instructor.sections))
            .where(Instructor.id == instructor_id)
        )
        return self.session.scalars(stmt).first()
    
    def get_active_instructors(self) -> List[Instructor]:
        """Get all active instructors"""
        return self.filter_by(is_active=True)
    
    def check_validity(self, instructor_id: int) -> bool:
        """
        Verify Instructor.is_active is True.
        Used before assigning instructor to a new section.
        """
        instructor = self.get_by_id(instructor_id)
        return instructor is not None and instructor.is_active
    
    def get_by_user_id(self, user_id: int) -> Optional[Instructor]:
        """Get instructor by linked user ID"""
        return self.get_one_by(user_id=user_id)
