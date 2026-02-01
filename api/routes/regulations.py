from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User
from dependencies import get_current_active_user, require_instructor
from services.regulation_service import RegulationService
from pydantic import BaseModel

router = APIRouter()

class ChunkRequest(BaseModel):
    document_id: int
    chunk_size: int = 500
    overlap: int = 50

@router.post("/regulations/chunk")
def chunk_document(
    request: ChunkRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_instructor)
):
    """
    Triggers chunking for a specific document.
    Requires INSTRUCTOR or ADMIN role.
    Header: Authorization: Bearer <token>
    """
    service = RegulationService(db)
    try:
        count = service.chunk_document(request.document_id, request.chunk_size, request.overlap)
        return {"message": f"Successfully created {count} chunks for document {request.document_id}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/regulations/ask")
def ask_regulation(
    q: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Ask a question about university regulations.
    Returns a streaming response (Server-Sent Events).
    Requires authentication (any UserType: STUDENT, INSTRUCTOR, ADMIN).
    Header: Authorization: Bearer <token>
    """
    service = RegulationService(db)
    
    return StreamingResponse(
        service.answer_question(q),
        media_type="text/event-stream"
    )


