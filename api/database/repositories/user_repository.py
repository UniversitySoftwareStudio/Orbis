from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Instructor, Student, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalars(select(User).where(User.email == email)).first()

    def create(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def resolve_user_role(self, user_id: int) -> dict[str, Any] | None:
        user = self.session.scalars(select(User).where(User.id == user_id)).first()
        if user is None:
            return None

        student = self.session.scalars(select(Student).where(Student.user_id == user_id)).first()
        if student is not None:
            return {"role": "student", "entity_id": student.id, "user_type": user.user_type.value}

        instructor = self.session.scalars(select(Instructor).where(Instructor.user_id == user_id)).first()
        if instructor is not None:
            return {"role": "instructor", "entity_id": instructor.id, "user_type": user.user_type.value}

        return {"role": None, "entity_id": None, "user_type": user.user_type.value}
