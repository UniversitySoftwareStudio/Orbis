# `rag_service/`

Standalone RAG microservice shell.

## Modules
- `app.py`: FastAPI app + RAG endpoints.
- `Dockerfile`: container runtime.
- `requirements.txt`: dependency input.

## Flow
```mermaid
flowchart TD
  A[HTTP /rag/*] --> B[app.py]
  B --> C[rag.service.RAGService]
  C --> D[database session]
  C --> E[embedding domain]
  C --> F[rag retrieval domain]
```

## Relevance
- deploy boundary for RAG as a separate service.
- keeps same models/session layer as monolith.
