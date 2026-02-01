from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from datetime import datetime
from .base import BaseRepository
from ..models import Assignment


class AssignmentRepository(BaseRepository[Assignment]):
    def __init__(self, session: Session):
        super().__init__(session, Assignment)
    
    def get_by_section(self, section_id: int, published_only: bool = True) -> List[Assignment]:
        """Get all assignments for a section"""
        stmt = select(Assignment).where(Assignment.section_id == section_id)
        if published_only:
            stmt = stmt.where(Assignment.is_published == True)
        return list(self.session.scalars(stmt).all())
    
    def get_upcoming(self, section_id: int, days: int = 7) -> List[Assignment]:
        """Get upcoming assignments within N days"""
        from datetime import timedelta
        cutoff = datetime.utcnow() + timedelta(days=days)
        
        stmt = (
            select(Assignment)
            .where(
                Assignment.section_id == section_id,
                Assignment.is_published == True,
                Assignment.due_date <= cutoff,
                Assignment.due_date >= datetime.utcnow()
            )
            .order_by(Assignment.due_date)
        )
        return list(self.session.scalars(stmt).all())
    
    def publish(self, assignment_id: int) -> Optional[Assignment]:
        """Publish an assignment (toggle is_published to True)"""
        return self.update(assignment_id, is_published=True)
    
    def unpublish(self, assignment_id: int) -> Optional[Assignment]:
        """Unpublish an assignment"""
        return self.update(assignment_id, is_published=False)
    
    def get_pending_assignments(self, student_id: int) -> List[Assignment]:
        """
        Get all pending (not yet due) published assignments for a student.
        Queries across all sections the student is currently enrolled in.
        """
        from ..models import Enrollment, EnrollmentStatus
        
        now = datetime.utcnow()
        
        stmt = (
            select(Assignment)
            .join(Enrollment, Enrollment.section_id == Assignment.section_id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
                Assignment.is_published == True,
                Assignment.due_date > now
            )
            .order_by(Assignment.due_date)
        )
        
        return list(self.session.scalars(stmt).all())
    
    def validate_submission_window(self, assignment_id: int) -> dict:
        """
        Validate if assignment submission is still open.
        Strict comparison of current time vs due_date.
        
        Returns:
            dict with 'open' bool, 'due_date', and 'message'
        """
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return {'open': False, 'due_date': None, 'message': 'Assignment not found'}
        
        now = datetime.utcnow()
        is_open = now <= assignment.due_date
        
        return {
            'open': is_open,
            'due_date': assignment.due_date,
            'message': 'Submission window open' if is_open else 'Submission deadline has passed'
        }
    
    def get_assignment_rubric(self, assignment_id: int) -> Optional[dict]:
        """
        Get assignment requirements for display.
        Returns description and max_points (the rubric).
        """
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return None
        
        return {
            'id': assignment.id,
            'title': assignment.title,
            'description': assignment.description,
            'max_points': float(assignment.max_points),
            'due_date': assignment.due_date,
            'is_published': assignment.is_published
        }
    
    def get_overdue_assignments(self, section_id: int) -> List[Assignment]:
        """Get published assignments that are past due date"""
        now = datetime.utcnow()
        
        stmt = (
            select(Assignment)
            .where(
                Assignment.section_id == section_id,
                Assignment.is_published == True,
                Assignment.due_date < now
            )
            .order_by(Assignment.due_date.desc())
        )
        return list(self.session.scalars(stmt).all())
