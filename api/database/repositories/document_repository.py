from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .base import BaseRepository
from ..models import DocumentChunk, UniversityDocument


class DocumentRepository(BaseRepository[UniversityDocument]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, UniversityDocument)

    def get_by_url(self, url: str) -> UniversityDocument | None:
        return self.get_one_by(source_url=url)

    def search_by_keywords(self, query_vector: list[float], limit: int = 5) -> list[UniversityDocument]:
        stmt = (
            select(UniversityDocument)
            .order_by(UniversityDocument.keyword_embedding.cosine_distance(query_vector))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def search_chunks(self, query_vector: list[float], limit: int = 10) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def get_with_chunks(self, document_id: int) -> UniversityDocument | None:
        stmt = (
            select(UniversityDocument)
            .options(joinedload(UniversityDocument.chunks))
            .where(UniversityDocument.id == document_id)
        )
        return self.session.scalars(stmt).first()
