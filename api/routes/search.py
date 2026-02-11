from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.session import get_db
from database.models import User
from dependencies import get_current_active_user
from services.rag_service import RAGService

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