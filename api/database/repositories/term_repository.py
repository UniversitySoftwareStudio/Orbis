from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .base import BaseRepository
from ..models import AcademicTerm, TermType


class TermRepository(BaseRepository[AcademicTerm]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AcademicTerm)

    def get_by_code(self, code: str) -> AcademicTerm | None:
        return self.get_one_by(code=code)

    def get_active_term(self, current_date: date | None = None) -> AcademicTerm | None:
        target_date = current_date or date.today()
        stmt = select(AcademicTerm).where(
            AcademicTerm.start_date <= target_date,
            AcademicTerm.end_date >= target_date,
            AcademicTerm.is_active.is_(True),
        )
        return self.session.scalars(stmt).first()

    def get_by_term_and_year(self, term_type: TermType, year: int) -> AcademicTerm | None:
        stmt = select(AcademicTerm).where(AcademicTerm.term_type == term_type, AcademicTerm.year == year)
        return self.session.scalars(stmt).first()

    def get_upcoming_terms(self, limit: int = 3) -> list[AcademicTerm]:
        stmt = (
            select(AcademicTerm)
            .where(AcademicTerm.start_date >= date.today())
            .order_by(AcademicTerm.start_date)
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def get_past_terms(self, limit: int = 5) -> list[AcademicTerm]:
        stmt = (
            select(AcademicTerm)
            .where(AcademicTerm.end_date < date.today())
            .order_by(AcademicTerm.end_date.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def get_terms_by_year(self, year: int) -> list[AcademicTerm]:
        stmt = select(AcademicTerm).where(AcademicTerm.year == year).order_by(AcademicTerm.start_date)
        return list(self.session.scalars(stmt).all())

    def is_term_active(self, term_id: int) -> bool:
        term = self.get_by_id(term_id)
        if term is None or not term.is_active:
            return False
        today = date.today()
        return term.start_date <= today <= term.end_date
