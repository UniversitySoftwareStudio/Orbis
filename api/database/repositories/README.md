# Repository Pattern for School System

## Structure

```
database/
  repositories/
    __init__.py              # Central export point
    base.py                  # Base repository with common CRUD
    course_repository.py     # Course-specific operations
    student_repository.py    # Student-specific operations (to be created)
    professor_repository.py  # Professor-specific operations (to be created)
    enrollment_repository.py # Enrollment-specific operations (to be created)
    EXAMPLES.md             # Templates for new repositories
```

## Design Principles

### ✅ One Repository Per Entity
- **Separation of Concerns**: Each repository handles one domain entity
- **Easy Navigation**: Find all Course operations in `course_repository.py`
- **No Merge Conflicts**: Multiple developers can work simultaneously

### ✅ Base Repository Pattern
- Common CRUD operations inherited from `BaseRepository`
- Reduces code duplication
- Consistent API across all repositories

### ✅ Factory Functions
```python
def get_course_repository() -> CourseRepository:
    return CourseRepository()
```
- Makes testing easier (can mock the factory)
- Consistent instantiation pattern
- Future-proof for dependency injection

## Usage Examples

### In Services
```python
from database.repositories import get_course_repository

class RAGService:
    def __init__(self):
        self.course_repo = get_course_repository()
    
    def search_courses(self, query: str, db: Session):
        embedding = self.embedding_service.embed_text(query)
        return self.course_repo.vector_search(db, embedding)
```

### In Routes
```python
from database.repositories import get_course_repository

@router.get("/courses/{course_id}")
def get_course(course_id: int, db: Session = Depends(get_db)):
    repo = get_course_repository()
    return repo.get_by_id(db, course_id)
```

## Adding New Repositories

1. **Create the file**: `database/repositories/student_repository.py`

```python
from typing import List, Optional
from sqlalchemy.orm import Session
from database.models import Student
from database.repositories.base import BaseRepository


class StudentRepository(BaseRepository[Student]):
    def __init__(self):
        super().__init__(Student)
    
    # Add custom methods
    def get_by_student_id(self, db: Session, student_id: str) -> Optional[Student]:
        return db.query(Student).filter(Student.student_id == student_id).first()


def get_student_repository() -> StudentRepository:
    return StudentRepository()
```

2. **Export in `__init__.py`**:
```python
from database.repositories.student_repository import (
    StudentRepository,
    get_student_repository
)

__all__ = [
    "StudentRepository",
    "get_student_repository",
    # ... other repositories
]
```

## When to Create a New Repository

Create a new repository when you:
- Add a new database table/model
- Have a distinct entity with its own operations
- Need specialized queries for that entity

## Anti-Patterns to Avoid

❌ **Don't put all repositories in one file**
```python
# BAD: database/repository.py with 1000+ lines
class CourseRepository: ...
class StudentRepository: ...
class ProfessorRepository: ...
# Hard to maintain!
```

❌ **Don't bypass repositories in services**
```python
# BAD: Direct database queries in services
def search(self, query: str, db: Session):
    return db.query(Course).filter(...).all()  # Wrong!

# GOOD: Use repository
def search(self, query: str, db: Session):
    return self.course_repo.search(db, query)  # Right!
```

❌ **Don't create repositories for join tables without logic**
If a table is just a join table with no custom logic, access it through related repositories.

## Benefits for School System

1. **Scalability**: Easy to add Students, Professors, Assignments, Grades, etc.
2. **Testability**: Mock individual repositories in unit tests
3. **Maintainability**: Each file has clear responsibility
4. **Team Work**: No conflicts when multiple people add features
5. **Code Reuse**: BaseRepository eliminates boilerplate

## Current Status

✅ Implemented:
- `CourseRepository` - Vector search, CRUD operations

🚧 To Implement (examples in EXAMPLES.md):
- `StudentRepository` - Student management
- `ProfessorRepository` - Professor management
- `EnrollmentRepository` - Student-course relationships
- `AssignmentRepository` - Assignment management
- `GradeRepository` - Grade management
