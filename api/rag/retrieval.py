from typing import Any

from sqlalchemy.orm import Session

from rag.sql_intent import execute_sql_intent, normalize_filters
from rag.vector_intent import execute_vector_intent


class RetrievalEngine:
    def __init__(self, embedding_service: Any, repository: Any) -> None:
        self.embedding_service = embedding_service
        self.repository = repository

    def execute_intent(self, session: Session, intent: dict[str, Any], parallel_mode: bool) -> list[Any]:
        tool = str(intent.get("tool", "vector")).lower()
        query = str(intent.get("query", "")).strip()
        filters = normalize_filters(intent.get("filters", {}))

        if tool == "sql":
            docs = execute_sql_intent(self.repository, session, query, filters)
            if docs:
                return docs
            query = query or " ".join(str(value) for value in filters.values() if value)

        return execute_vector_intent(
            self.embedding_service,
            self.repository,
            session,
            query,
            filters,
            parallel_mode,
        )
