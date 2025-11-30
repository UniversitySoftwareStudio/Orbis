from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.session import get_db
from services.rag_service import get_rag_service

router = APIRouter()


@router.get("/search")
async def search_courses(
    q: str,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """
    Semantic search for courses
    
    Example: /search?q=programming with recursion&limit=3
    """
    rag_service = get_rag_service()
    results = rag_service.search_courses(q, db, limit)
    
    return {
        "query": q,
        "results": results,
        "count": len(results)
    }
