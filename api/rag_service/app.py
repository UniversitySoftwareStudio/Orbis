from collections.abc import Iterator
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database.session import SessionLocal
from rag.pipeline import RAGService

app = FastAPI(title="UniChatBot RAG Service", version="1.0.0")
rag = RAGService()


class QueryRequest(BaseModel):
    query: str
    limit: int = 5


def _stream(generator: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(generator, media_type="text/event-stream")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/rag/process")
def process(request: QueryRequest) -> StreamingResponse:
    def generate() -> Iterator[str]:
        db = SessionLocal()
        try:
            yield from rag.process_query(request.query, db)
        except Exception as exc:
            yield f"[Error: {exc}]"
        finally:
            db.close()

    return _stream(generate())


@app.post("/rag/search")
def search(request: QueryRequest) -> dict[str, object]:
    db = SessionLocal()
    try:
        results, timings = rag.search_courses(request.query, db, request.limit)
        return {"query": request.query, "results": results, "count": len(results), "timings_ms": timings}
    finally:
        db.close()


@app.post("/rag/ask")
def ask(request: QueryRequest) -> StreamingResponse:
    def generate() -> Iterator[str]:
        db = SessionLocal()
        try:
            stream, courses = rag.stream_answer(request.query, db, request.limit)
            yield f"data: {json.dumps({'type': 'courses', 'query': request.query, 'courses': courses, 'count': len(courses)})}\n\n"
            for chunk in stream:
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            db.close()

    return _stream(generate())
