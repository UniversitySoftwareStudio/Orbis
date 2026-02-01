from typing import TypeVar, Generic, Type, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete as sql_delete

T = TypeVar('T')

class BaseRepository(Generic[T]):
    """Generic CRUD operations for all models using SQLAlchemy 2.0 style"""
    
    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model
    
    def create(self, **kwargs) -> Optional[T]:
        """Create a new record"""
        try:
            obj = self.model(**kwargs)
            self.session.add(obj)
            self.session.flush()
            self.session.refresh(obj)
            return obj
        except Exception as e:
            self.session.rollback()
            raise e
    
    def get_by_id(self, id: int) -> Optional[T]:
        """Get record by ID"""
        stmt = select(self.model).where(self.model.id == id)
        return self.session.scalars(stmt).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all records with pagination"""
        stmt = select(self.model).offset(skip).limit(limit)
        return list(self.session.scalars(stmt).all())
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        """Update a record"""
        obj = self.get_by_id(id)
        if not obj:
            return None
        
        try:
            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            
            self.session.flush()
            self.session.refresh(obj)
            return obj
        except Exception as e:
            self.session.rollback()
            raise e
    
    def delete(self, id: int) -> bool:
        """Delete a record"""
        obj = self.get_by_id(id)
        if not obj:
            return False
        
        try:
            self.session.delete(obj)
            self.session.flush()
            return True
        except Exception as e:
            self.session.rollback()
            raise e
    
    def count(self) -> int:
        """Count total records"""
        stmt = select(func.count()).select_from(self.model)
        return self.session.scalar(stmt) or 0
    
    def filter_by(self, **kwargs) -> List[T]:
        """Filter records by attributes"""
        stmt = select(self.model).filter_by(**kwargs)
        return list(self.session.scalars(stmt).all())
    
    def get_one_by(self, **kwargs) -> Optional[T]:
        """Get single record by attributes"""
        stmt = select(self.model).filter_by(**kwargs)
        return self.session.scalars(stmt).first()
