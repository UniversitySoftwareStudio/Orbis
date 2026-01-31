from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from .base import BaseRepository
from ..models import UniversityDocument, DocumentChunk


class DocumentRepository(BaseRepository[UniversityDocument]):
    def __init__(self, session: Session):
        super().__init__(session, UniversityDocument)
    
    def get_by_url(self, url: str) -> Optional[UniversityDocument]:
        """Get document by source URL"""
        return self.get_one_by(source_url=url)
    
    def search_by_keywords(self, query_vector: List[float], limit: int = 5) -> List[UniversityDocument]:
        """Search documents by keyword embedding"""
        return (
            self.session.query(UniversityDocument)
            .order_by(UniversityDocument.keyword_embedding.cosine_distance(query_vector))
            .limit(limit)
            .all()
        )
    
    def search_chunks(self, query_vector: List[float], limit: int = 10) -> List[DocumentChunk]:
        """Search document chunks by embedding"""
        return (
            self.session.query(DocumentChunk)
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(limit)
            .all()
        )
    
    def get_with_chunks(self, document_id: int) -> Optional[UniversityDocument]:
        """Get document with all chunks"""
        return (
            self.session.query(UniversityDocument)
            .options(joinedload(UniversityDocument.chunks))
            .filter(UniversityDocument.id == document_id)
            .first()
        )
