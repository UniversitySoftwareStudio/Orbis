from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from .base import BaseRepository
from ..models import User, UserType


class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session):
        super().__init__(session, User)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.get_one_by(email=email)
    
    def get_active_users(self, user_type: Optional[UserType] = None):
        """Get all active users, optionally filtered by type"""
        stmt = select(User).where(User.is_active == True)
        if user_type:
            stmt = stmt.where(User.user_type == user_type)
        return list(self.session.scalars(stmt).all())
    
    def deactivate(self, user_id: int) -> bool:
        """Soft delete - deactivate user"""
        return self.update(user_id, is_active=False) is not None
    
    def resolve_user_role(self, user_id: int) -> Optional[dict]:
        """
        Determine if a User.id maps to Student or Instructor entity.
        Returns dict with 'role' ('student'/'instructor'/None) and entity object.
        Used to toggle frontend interfaces.
        """
        from ..models import Student, Instructor
        
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        # Check if user is a student
        stmt = select(Student).where(Student.user_id == user_id)
        student = self.session.scalars(stmt).first()
        if student:
            return {
                'user_id': user_id,
                'role': 'student',
                'entity_id': student.id,
                'entity': student,
                'user_type': user.user_type.value
            }
        
        # Check if user is an instructor
        stmt = select(Instructor).where(Instructor.user_id == user_id)
        instructor = self.session.scalars(stmt).first()
        if instructor:
            return {
                'user_id': user_id,
                'role': 'instructor',
                'entity_id': instructor.id,
                'entity': instructor,
                'user_type': user.user_type.value
            }
        
        # User exists but has no student/instructor profile
        return {
            'user_id': user_id,
            'role': None,
            'entity_id': None,
            'entity': None,
            'user_type': user.user_type.value
        }
