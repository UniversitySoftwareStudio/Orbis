# database/

Database layer. PostgreSQL models and connections.

## Structure

```
database/
├── models.py      # SQLAlchemy models (courses, etc.)
├── session.py     # Database connection & session
└── README.md
```

## Files

**`models.py`** - Database tables
- Course models
- Future: User models, Vector embeddings

**`session.py`** - Connection management
- `init_db()` - Create tables
- `get_db()` - Get database session

## Usage

**Initialize tables:**
```bash
python database/session.py
```

**Use in routes:**
```python
from database.session import get_db
from database.models import Course

# In your route
def get_courses(db = Depends(get_db)):
    return db.query(Course).all()
```

Clean separation: database logic stays here.
