from sentence_transformers import SentenceTransformer
from typing import List
import threading

class EmbeddingService:
    """
    Local embedding service using Sentence-Transformers.
    Fast, free, no API needed.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding model.
        
        Models:
        - all-MiniLM-L6-v2: Fast, 384 dimensions (default)
        - all-mpnet-base-v2: Better quality, 768 dimensions
        """
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"✓ Model loaded! Dimension: {self.dimension}")
    
    def embed_text(self, text: str) -> List[float]:
        """Embed single text"""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts (faster)"""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension


# Singleton instance
_embedding_service = None
_embedding_service_lock = threading.Lock()

def get_embedding_service() -> EmbeddingService:
    """Get or create embedding service (thread-safe)"""
    global _embedding_service
    if _embedding_service is None:
        with _embedding_service_lock:
            # Double-check locking pattern
            if _embedding_service is None:
                _embedding_service = EmbeddingService()
    return _embedding_service
