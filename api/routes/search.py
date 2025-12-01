from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database.session import get_db
from services.rag_service import RAGService
import json
import asyncio

router = APIRouter()


@router.get("/search")
async def search_courses(q: str, limit: int = 5, db: Session = Depends(get_db)):
    """
    Semantic search for courses with timing information

    Example: /search?q=programming with recursion&limit=3
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
async def ask_courses(q: str, limit: int = 5, db: Session = Depends(get_db)):
    """
    Stream course recommendations with AI-generated answer in real-time

    Example: /ask?q=I want to learn about machine learning&limit=3
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
