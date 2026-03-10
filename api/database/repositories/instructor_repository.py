from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Instructor
from .base import BaseRepository


class InstructorRepository(BaseRepository[Instructor]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Instructor)

    def get_by_employee_id(self, employee_id: str) -> Instructor | None:
        return self.get_one_by(employee_id=employee_id)

    def get_with_sections(self, instructor_id: int) -> Instructor | None:
        stmt = select(Instructor).options(joinedload(Instructor.sections)).where(Instructor.id == instructor_id)
        return self.session.scalars(stmt).first()

    def get_active_instructors(self) -> list[Instructor]:
        return self.filter_by(is_active=True)

    def check_validity(self, instructor_id: int) -> bool:
        instructor = self.get_by_id(instructor_id)
        return instructor is not None and instructor.is_active

    def get_by_user_id(self, user_id: int) -> Instructor | None:
        return self.get_one_by(user_id=user_id)
