from typing import Optional
from sqlalchemy.orm import Session
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
        query = self.session.query(User).filter(User.is_active == True)
        if user_type:
            query = query.filter(User.user_type == user_type)
        return query.all()
    
    def deactivate(self, user_id: int) -> bool:
        """Soft delete - deactivate user"""
        return self.update(user_id, is_active=False) is not None
