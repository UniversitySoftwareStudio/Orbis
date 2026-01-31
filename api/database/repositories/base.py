from typing import TypeVar, Generic, Type, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

T = TypeVar('T')

class BaseRepository(Generic[T]):
    """Generic CRUD operations for all models"""
    
    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model
    
    def create(self, **kwargs) -> T:
        """Create a new record"""
        obj = self.model(**kwargs)
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj
    
    def get_by_id(self, id: int) -> Optional[T]:
        """Get record by ID"""
        return self.session.query(self.model).filter(self.model.id == id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all records with pagination"""
        return self.session.query(self.model).offset(skip).limit(limit).all()
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        """Update a record"""
        obj = self.get_by_id(id)
        if not obj:
            return None
        
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        
        self.session.commit()
        self.session.refresh(obj)
        return obj
    
    def delete(self, id: int) -> bool:
        """Delete a record"""
        obj = self.get_by_id(id)
        if not obj:
            return False
        
        self.session.delete(obj)
        self.session.commit()
        return True
    
    def count(self) -> int:
        """Count total records"""
        return self.session.query(func.count(self.model.id)).scalar()
    
    def filter_by(self, **kwargs) -> List[T]:
        """Filter records by attributes"""
        return self.session.query(self.model).filter_by(**kwargs).all()
    
    def get_one_by(self, **kwargs) -> Optional[T]:
        """Get single record by attributes"""
        return self.session.query(self.model).filter_by(**kwargs).first()
