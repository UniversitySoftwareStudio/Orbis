import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import User
from database.session import get_db
from dependencies import get_current_active_user
from services.rag_service import RAGService

router = APIRouter()
logger = get_logger(__name__)
rag: RAGService | None = None


def _get_rag() -> RAGService:
    global rag
    if rag is None:
        logger.info("Initializing RAG service")
        rag = RAGService()
    return rag


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    return StreamingResponse(
        _get_rag().process_query(request.message, db),
        media_type="text/event-stream",
    )


@router.get("/search")
async def search_courses(
    q: str,
    limit: int = 5,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> dict[str, object]:
    results, timings = _get_rag().search_courses(q, db, limit)
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
    _current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    stream, courses = _get_rag().stream_answer(q, db, limit)

    async def generate() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'courses', 'query': q, 'courses': courses, 'count': len(courses)})}\n\n"
        for chunk in stream:
            yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
