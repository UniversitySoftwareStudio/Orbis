from typing import List, Dict, Iterator
from sqlalchemy.orm import Session
from database.models import UniversityDocument, DocumentChunk
from services.embedding_service import get_embedding_service
from services.llm_service import LLMService

class RegulationService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()
        self.llm_service = LLMService()

    def chunk_document(self, document_id: int, chunk_size: int = 200, overlap: int = 20):
        """
        Splits a document into chunks and saves them to the database.
        
        Args:
            document_id: ID of the document to chunk
            chunk_size: Number of words per chunk (Default 200, approx 256 tokens)
            overlap: Number of overlapping words (Default 20)
        """
        document = self.db.query(UniversityDocument).filter(UniversityDocument.id == document_id).first()
        if not document:
            raise ValueError("Document not found")

        # Simple text splitting
        text = document.raw_content
        words = text.split()
        chunks = []
        
        # Cap at 150 words to prevent 413 errors from embedding service
        # all-MiniLM-L6-v2 can handle ~256 tokens, but 150 words is safer
        if chunk_size > 150:
            print(f" Capping chunk_size from {chunk_size} to 150 to prevent embedding errors")
            chunk_size = 150
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i : i + chunk_size]
            chunk_text = " ".join(chunk_words)
            chunks.append(chunk_text)

        # Delete existing chunks for this document to avoid duplicates if re-running
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        
        # Create and embed chunks
        success_count = 0
        for i, chunk_text in enumerate(chunks):
            try:
                embedding = self.embedding_service.embed_text(chunk_text)
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=i,
                    content=chunk_text,
                    embedding=embedding
                )
                self.db.add(chunk)
                success_count += 1
            except Exception as e:
                print(f"Error embedding chunk {i}: {e}")
                # Continue to next chunk instead of failing completely
                continue
        
        self.db.commit()
        return success_count


    def search_regulations(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Searches for relevant regulation chunks.
        """
        query_embedding = self.embedding_service.embed_text(query)
        
        # Search chunks using pgvector
        chunks = self.db.query(DocumentChunk).order_by(
            DocumentChunk.embedding.cosine_distance(query_embedding)
        ).limit(limit).all()
        
        results = []
        for chunk in chunks:
            results.append({
                "content": chunk.content,
                "document_title": chunk.document.title,
                "source_url": chunk.document.source_url,
                "score": 0.0 # TODO: Calculate score if needed, or just rely on order
            })
        return results

    def answer_question(self, query: str) -> Iterator[str]:
        """
        Retrieves relevant regulations and streams an answer as Server-Sent Events (SSE).
        """
        import json
        
        # 1. Retrieve
        relevant_chunks = self.search_regulations(query, limit=5)
        
        # Emit metadata event
        metadata = {
            "type": "metadata",
            "query": query,
            "retrieved_chunks": relevant_chunks
        }
        yield f"data: {json.dumps(metadata)}\n\n"
        
        if not relevant_chunks:
            msg = {"type": "content", "delta": "I couldn't find any specific regulations matching your query."}
            yield f"data: {json.dumps(msg)}\n\n"
            return

        # 2. Format Context
        context_text = "\n\n".join([
            f"Source: {chunk['document_title']}\nContent: {chunk['content']}"
            for chunk in relevant_chunks
        ])

        # 3. Generate Answer
        prompt = (
            f"You are a university regulation expert. A student asked: '{query}'\n\n"
            f"Based strictly on the following official regulations, answer the question:\n\n"
            f"{context_text}\n\n"
            f"If the answer is not in the text, say so. Cite the source document title when possible."
        )
        
        # Use LLM service to stream
        try:
            # Delegate to LLMService which handles fallback logic
            response_stream = self.llm_service.generate_response(prompt)
            for chunk in response_stream:
                msg = {"type": "content", "delta": chunk}
                yield f"data: {json.dumps(msg)}\n\n"
        except Exception as e:
            print(f"Generation failed: {e}")
            import traceback
            traceback.print_exc()
            error_msg = {"type": "error", "message": f"Sorry, I encountered an error generating the answer: {str(e)}"}
            yield f"data: {json.dumps(error_msg)}\n\n"




