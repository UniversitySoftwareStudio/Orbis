from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from datetime import datetime, date
from .base import BaseRepository
from ..models import AcademicTerm, TermType


class TermRepository(BaseRepository[AcademicTerm]):
    """Repository for AcademicTerm entity"""
    
    def __init__(self, session: Session):
        super().__init__(session, AcademicTerm)
    
    def get_by_code(self, code: str) -> Optional[AcademicTerm]:
        """Get term by code (e.g., 'FALL2024')"""
        return self.get_one_by(code=code)
    
    def get_active_term(self, current_date: Optional[date] = None) -> Optional[AcademicTerm]:
        """
        Get the currently active term based on date range.
        Returns the term where current_date falls between start_date and end_date.
        """
        if current_date is None:
            current_date = date.today()
        
        stmt = (
            select(AcademicTerm)
            .where(
                and_(
                    AcademicTerm.start_date <= current_date,
                    AcademicTerm.end_date >= current_date,
                    AcademicTerm.is_active == True
                )
            )
        )
        return self.session.scalars(stmt).first()
    
    def get_by_term_and_year(self, term_type: TermType, year: int) -> Optional[AcademicTerm]:
        """Get term by type (FALL/SPRING/SUMMER) and year"""
        stmt = (
            select(AcademicTerm)
            .where(
                and_(
                    AcademicTerm.term_type == term_type,
                    AcademicTerm.year == year
                )
            )
        )
        return self.session.scalars(stmt).first()
    
    def get_upcoming_terms(self, limit: int = 3) -> List[AcademicTerm]:
        """Get upcoming terms ordered by start date"""
        today = date.today()
        stmt = (
            select(AcademicTerm)
            .where(AcademicTerm.start_date >= today)
            .order_by(AcademicTerm.start_date)
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_past_terms(self, limit: int = 5) -> List[AcademicTerm]:
        """Get past terms ordered by most recent first"""
        today = date.today()
        stmt = (
            select(AcademicTerm)
            .where(AcademicTerm.end_date < today)
            .order_by(AcademicTerm.end_date.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
    
    def get_terms_by_year(self, year: int) -> List[AcademicTerm]:
        """Get all terms for a specific year"""
        stmt = (
            select(AcademicTerm)
            .where(AcademicTerm.year == year)
            .order_by(AcademicTerm.start_date)
        )
        return list(self.session.scalars(stmt).all())
    
    def is_term_active(self, term_id: int) -> bool:
        """Check if a term is currently active based on dates"""
        term = self.get_by_id(term_id)
        if not term or not term.is_active:
            return False
        
        today = date.today()
        return term.start_date <= today <= term.end_date
