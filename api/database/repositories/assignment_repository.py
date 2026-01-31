from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from .base import BaseRepository
from ..models import Assignment


class AssignmentRepository(BaseRepository[Assignment]):
    def __init__(self, session: Session):
        super().__init__(session, Assignment)
    
    def get_by_section(self, section_id: int, published_only: bool = True) -> List[Assignment]:
        """Get all assignments for a section"""
        query = self.session.query(Assignment).filter(Assignment.section_id == section_id)
        if published_only:
            query = query.filter(Assignment.is_published == True)
        return query.all()
    
    def get_upcoming(self, section_id: int, days: int = 7) -> List[Assignment]:
        """Get upcoming assignments within N days"""
        from datetime import timedelta
        cutoff = datetime.utcnow() + timedelta(days=days)
        
        return (
            self.session.query(Assignment)
            .filter(
                Assignment.section_id == section_id,
                Assignment.is_published == True,
                Assignment.due_date <= cutoff,
                Assignment.due_date >= datetime.utcnow()
            )
            .order_by(Assignment.due_date)
            .all()
        )
    
    def publish(self, assignment_id: int) -> Optional[Assignment]:
        """Publish an assignment"""
        return self.update(assignment_id, is_published=True)
