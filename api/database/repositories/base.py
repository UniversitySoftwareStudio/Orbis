from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, session: Session, model: type[T]) -> None:
        self.session = session
        self.model = model

    def create(self, **kwargs: Any) -> T:
        try:
            obj = self.model(**kwargs)
            self.session.add(obj)
            self.session.flush()
            self.session.refresh(obj)
            return obj
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def get_by_id(self, id: int) -> T | None:
        return self.session.scalars(select(self.model).where(self.model.id == id)).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        return list(self.session.scalars(select(self.model).offset(skip).limit(limit)).all())

    def update(self, id: int, **kwargs: Any) -> T | None:
        obj = self.get_by_id(id)
        if obj is None:
            return None

        try:
            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            self.session.flush()
            self.session.refresh(obj)
            return obj
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def delete(self, id: int) -> bool:
        obj = self.get_by_id(id)
        if obj is None:
            return False

        try:
            self.session.delete(obj)
            self.session.flush()
            return True
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(self.model)) or 0

    def filter_by(self, **kwargs: Any) -> list[T]:
        return list(self.session.scalars(select(self.model).filter_by(**kwargs)).all())

    def get_one_by(self, **kwargs: Any) -> T | None:
        return self.session.scalars(select(self.model).filter_by(**kwargs)).first()
