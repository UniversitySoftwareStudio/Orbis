from fastapi import APIRouter, Depends
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User
from dependencies import get_current_active_user
from services.rag_service import RAGService
import json
import asyncio

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

@router.post("/chat")
async def chat(
    request: ChatRequest, 
    db: Session = Depends(get_db),
    # Keep authentication to protect your API
    current_user: User = Depends(get_current_active_user)
):
    """
    Unified RAG Chat Endpoint.
    The Router Agent (in RAGService) automatically decides if this is:
    1. A Semantic Vector Search
    2. A Metadata SQL Filter (e.g., "List courses in Engineering")
    3. A General Chat
    """
    rag_service = RAGService()
    
    # process_query returns a generator (iterator), which StreamingResponse loves.
    return StreamingResponse(
        rag_service.process_query(request.message, db), 
        media_type="text/event-stream"
    )

@router.get("/search")
async def search_courses(
    q: str, 
    limit: int = 5, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Semantic search for courses with timing information.
    Requires authentication (any UserType: STUDENT, INSTRUCTOR, ADMIN).

    Example: /search?q=programming with recursion&limit=3
    Header: Authorization: Bearer <token>
    """
    rag_service = RAGService()
    results, timings = rag_service.search_courses(q, db, limit)

    return {
        "query": q,
        "results": results,
        "count": len(results),
        "timings_ms": timings,
    }


@router.get("/ask")
async def ask_courses(
    q: str, 
    limit: int = 5, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Stream course recommendations with AI-generated answer in real-time.
    Requires authentication (any UserType: STUDENT, INSTRUCTOR, ADMIN).

    Example: /ask?q=I want to learn about machine learning&limit=3
    Header: Authorization: Bearer <token>
    """
    rag_service = RAGService()
    stream, courses = rag_service.stream_answer(q, db, limit)

    async def generate():
        yield f"data: {json.dumps({'type': 'courses', 'query': q, 'courses': courses, 'count': len(courses)})}\n\n"
        loop = asyncio.get_event_loop()
        for chunk in stream:
            await loop.run_in_executor(None, lambda: None)
            yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
