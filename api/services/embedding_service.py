import os
import threading
from typing import List, Optional
from abc import ABC, abstractmethod

# Configuration
# We default to 'local' now so it matches your script
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local") 
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

class LocalProvider(EmbeddingProvider):
    """
    Runs sentence-transformers locally in Python (CPU/GPU).
    Matches your embed_database.py script exactly.
    """
    def __init__(self, model_name: str):
        print(f"🔌 Loading Local Embedding Model: {model_name}...")
        from sentence_transformers import SentenceTransformer
        # This will load from your D:\hf_cache folder instantly
        self.client = SentenceTransformer(model_name)
        print("✓ Local Model Loaded.")

    def embed_text(self, text: str) -> List[float]:
        # encode returns a numpy array, we need a list
        return self.client.encode(text).tolist()

class EmbeddingService:
    def __init__(self):
        self.provider = None
        self._initialize_provider()
    
    def _initialize_provider(self):
        if EMBEDDING_PROVIDER == "local":
            self.provider = LocalProvider(MODEL_NAME)
        # We can add Docker/Ollama back later if you want to switch!
        else:
            raise ValueError(f"Unknown provider: {EMBEDDING_PROVIDER}")

    def embed_text(self, text: str) -> List[float]:
        return self.provider.embed_text(text)

# Singleton Pattern
_embedding_service: Optional[EmbeddingService] = None
_embedding_service_lock = threading.Lock()

def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        with _embedding_service_lock:
            if _embedding_service is None:
                _embedding_service = EmbeddingService()
    return _embedding_service