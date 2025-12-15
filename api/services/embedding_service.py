import os
import requests
from typing import List, Optional, Union
import threading
from abc import ABC, abstractmethod

# Configuration
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "tei")  # 'tei' or 'ollama'
TEI_URL = os.getenv("TEI_URL", "http://localhost:7860")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "all-minilm")  # or 'nomic-embed-text'


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        pass


class TEIProvider(EmbeddingProvider):
    """
    HuggingFace Text Embeddings Inference (TEI) Provider.
    """
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.dimension = 384  # Default for all-MiniLM-L6-v2
        self._validate_connection()

    def _validate_connection(self):
        try:
            response = requests.post(
                f"{self.api_url}/embed",
                json={"inputs": "connection test"},
                timeout=5
            )
            response.raise_for_status()
            # TEI doesn't easily return dim in info, assuming default or checking output
            emb = response.json()[0]
            self.dimension = len(emb)
            print(f"✓ Connected to TEI at {self.api_url} (Dim: {self.dimension})")
        except Exception as e:
            raise ConnectionError(f"Could not connect to TEI at {self.api_url}: {e}")

    def embed_text(self, text: str) -> List[float]:
        response = requests.post(
            f"{self.api_url}/embed",
            json={"inputs": text},
            timeout=10
        )
        response.raise_for_status()
        return response.json()[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = requests.post(
            f"{self.api_url}/embed",
            json={"inputs": texts},
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def get_dimension(self) -> int:
        return self.dimension


class OllamaProvider(EmbeddingProvider):
    """
    Ollama Embedding Provider.
    """
    def __init__(self, api_url: str, model: str):
        self.api_url = api_url
        self.model = model
        self.dimension = 384 # Default fallback
        self._validate_connection()

    def _validate_connection(self):
        try:
            # Check if ollama is up
            requests.get(f"{self.api_url}/", timeout=5)
            
            # Check if model is pulled; if not, this might fail or trigger pull
            # We run a quick embed to check model readiness and dimension
            payload = {
                "model": self.model,
                "prompt": "test"
            }
            response = requests.post(
                f"{self.api_url}/api/embeddings",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 404:
                print(f"⚠️  Model '{self.model}' not found in Ollama.")
                print(f"   Run: docker exec -it orbis_ollama ollama pull {self.model}")
                raise ValueError(f"Model {self.model} not found")
                
            response.raise_for_status()
            emb = response.json().get('embedding')
            self.dimension = len(emb)
            print(f"✓ Connected to Ollama at {self.api_url} with model {self.model} (Dim: {self.dimension})")
            
        except requests.exceptions.ConnectionError:
             raise ConnectionError(f"Could not connect to Ollama at {self.api_url}. Is the container running?")
        except Exception as e:
            raise ConnectionError(f"Ollama Error: {e}")

    def embed_text(self, text: str) -> List[float]:
        payload = {
            "model": self.model,
            "prompt": text,
            "options": {"temperature": 0} # Deterministic
        }
        response = requests.post(
            f"{self.api_url}/api/embeddings",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()['embedding']

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # Ollama API currently does not support batching in the /api/embeddings endpoint natively 
        # as efficiently as TEI, so we loop (or use concurrent requests if needed).
        # For simplicity, we loop here.
        embeddings = []
        for text in texts:
            embeddings.append(self.embed_text(text))
        return embeddings

    def get_dimension(self) -> int:
        return self.dimension


class EmbeddingService:
    """
    Main Service class that delegates to the configured provider.
    """
    def __init__(self):
        self.provider: Optional[EmbeddingProvider] = None
        self._initialize_provider()
    
    def _initialize_provider(self):
        if EMBEDDING_PROVIDER == "ollama":
            print(f"🔌 Initializing Embedding Service with Ollama ({OLLAMA_MODEL})...")
            self.provider = OllamaProvider(OLLAMA_URL, OLLAMA_MODEL)
        else:
            print(f"🔌 Initializing Embedding Service with TEI...")
            self.provider = TEIProvider(TEI_URL)

    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        return self.provider.embed_text(text)
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            raise ValueError("Texts list cannot be empty")
        return self.provider.embed_batch(texts)
    
    def get_dimension(self) -> int:
        return self.provider.get_dimension()


# Singleton
_embedding_service: Optional[EmbeddingService] = None
_embedding_service_lock = threading.Lock()

def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        with _embedding_service_lock:
            if _embedding_service is None:
                _embedding_service = EmbeddingService()
    return _embedding_service