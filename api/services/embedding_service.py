import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
import threading
from abc import ABC, abstractmethod

# Configuration
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "tei")  # 'tei' or 'ollama'
TEI_URL = os.getenv("TEI_URL") or os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:7860")
TEI_URLS_RAW = os.getenv("TEI_URLS", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "all-minilm")  # or 'nomic-embed-text'


def _parse_tei_urls() -> List[str]:
    """Read TEI endpoints from TEI_URLS (comma-separated) or fallback to TEI_URL."""
    urls = [u.strip().rstrip("/") for u in TEI_URLS_RAW.split(",") if u.strip()]
    if not urls:
        return [TEI_URL.rstrip("/")]

    deduped: List[str] = []
    seen = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


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
    SAFE_CHAR_LIMITS = (500, 420, 340, 280, 220, 180, 140, 100)

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

    def _embed_single_with_backoff(self, text: str, timeout: int = 10) -> List[float]:
        """
        Retry with progressively shorter text when TEI rejects by token limit (413).
        """
        normalized = (text or "").strip()
        if not normalized:
            raise ValueError("Text cannot be empty")

        last_413: Optional[Exception] = None
        seen = set()
        for max_chars in self.SAFE_CHAR_LIMITS:
            candidate = normalized if len(normalized) <= max_chars else normalized[:max_chars]
            if candidate in seen:
                continue
            seen.add(candidate)

            try:
                response = requests.post(
                    f"{self.api_url}/embed",
                    json={"inputs": candidate},
                    timeout=timeout
                )
                response.raise_for_status()
                return response.json()[0]
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 413:
                    last_413 = e
                    continue
                raise

        if last_413 is not None:
            raise RuntimeError(
                f"TEI kept returning 413 even after truncating to {self.SAFE_CHAR_LIMITS[-1]} chars"
            ) from last_413
        raise RuntimeError("TEI embedding failed for unknown reason")

    def embed_text(self, text: str) -> List[float]:
        return self._embed_single_with_backoff(text, timeout=10)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        cleaned_texts = [(t or "").strip() for t in texts]
        max_chars = self.SAFE_CHAR_LIMITS[0]
        truncated_texts = [t if len(t) <= max_chars else t[:max_chars] for t in cleaned_texts]

        try:
            response = requests.post(
                f"{self.api_url}/embed",
                json={"inputs": truncated_texts},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 413:
                # Fall back to one-at-a-time with progressive token-safe truncation.
                return [self._embed_single_with_backoff(t, timeout=10) for t in cleaned_texts]
            raise

    def get_dimension(self) -> int:
        return self.dimension


class RoundRobinTEIProvider(EmbeddingProvider):
    """
    Uses multiple TEI endpoints and distributes calls round-robin with failover.
    """
    def __init__(self, api_urls: List[str]):
        if not api_urls:
            raise ValueError("At least one TEI URL is required")

        self.providers: List[TEIProvider] = []
        self._rr_lock = threading.Lock()
        self._rr_index = 0

        errors = []
        for api_url in api_urls:
            try:
                self.providers.append(TEIProvider(api_url))
            except Exception as e:
                errors.append(f"{api_url} -> {e}")
                print(f"⚠️  Skipping TEI endpoint {api_url}: {e}")

        if not self.providers:
            joined = "; ".join(errors) if errors else "no endpoints configured"
            raise ConnectionError(f"Could not connect to any TEI endpoint: {joined}")

        dims = {p.get_dimension() for p in self.providers}
        if len(dims) != 1:
            raise ValueError(f"TEI endpoints have mismatched embedding dimensions: {sorted(dims)}")
        self.dimension = next(iter(dims))

        urls = ", ".join(p.api_url for p in self.providers)
        print(f"✓ Round-robin TEI enabled across {len(self.providers)} endpoint(s): {urls}")

    def _next_start_index(self) -> int:
        with self._rr_lock:
            idx = self._rr_index
            self._rr_index = (self._rr_index + 1) % len(self.providers)
            return idx

    def _providers_in_order(self) -> List[TEIProvider]:
        start = self._next_start_index()
        return [
            self.providers[(start + offset) % len(self.providers)]
            for offset in range(len(self.providers))
        ]

    def embed_text(self, text: str) -> List[float]:
        errors = []
        for provider in self._providers_in_order():
            try:
                return provider.embed_text(text)
            except Exception as e:
                errors.append(f"{provider.api_url} -> {e}")
        raise RuntimeError(f"All TEI endpoints failed for embed_text: {'; '.join(errors)}")

    def _embed_bucket_with_failover(
        self,
        texts: List[str],
        provider_order: List[TEIProvider],
    ) -> List[List[float]]:
        errors = []
        for provider in provider_order:
            try:
                return provider.embed_batch(texts)
            except Exception as e:
                errors.append(f"{provider.api_url} -> {e}")
        raise RuntimeError(f"All TEI endpoints failed for bucket: {'; '.join(errors)}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if len(self.providers) == 1:
            return self.providers[0].embed_batch(texts)

        providers = self._providers_in_order()
        provider_count = len(providers)
        buckets: List[List[tuple[int, str]]] = [[] for _ in range(provider_count)]

        # Split one batch across TEI servers so requests run in parallel.
        for idx, text in enumerate(texts):
            buckets[idx % provider_count].append((idx, text))

        ordered_results: List[Optional[List[float]]] = [None] * len(texts)
        errors = []

        with ThreadPoolExecutor(max_workers=provider_count) as executor:
            future_to_bucket: dict = {}
            for bucket_idx, bucket in enumerate(buckets):
                if not bucket:
                    continue

                bucket_texts = [text for _, text in bucket]
                primary = providers[bucket_idx]
                fallback = providers[bucket_idx + 1 :] + providers[:bucket_idx]
                provider_order = [primary] + fallback
                future = executor.submit(
                    self._embed_bucket_with_failover,
                    bucket_texts,
                    provider_order,
                )
                future_to_bucket[future] = bucket

            for future in as_completed(future_to_bucket):
                bucket = future_to_bucket[future]
                try:
                    bucket_embeddings = future.result()
                    if len(bucket_embeddings) != len(bucket):
                        raise RuntimeError(
                            f"Bucket size mismatch: expected {len(bucket)}, got {len(bucket_embeddings)}"
                        )
                    for (original_idx, _), emb in zip(bucket, bucket_embeddings):
                        ordered_results[original_idx] = emb
                except Exception as e:
                    errors.append(str(e))

        if errors:
            raise RuntimeError(f"Parallel TEI embed_batch failed: {'; '.join(errors)}")

        if any(emb is None for emb in ordered_results):
            raise RuntimeError("Parallel TEI embed_batch produced incomplete results")

        return [emb for emb in ordered_results if emb is not None]

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
        elif EMBEDDING_PROVIDER == "tei":
            tei_urls = _parse_tei_urls()
            print(f"🔌 Initializing Embedding Service with TEI ({len(tei_urls)} endpoint(s))...")
            self.provider = RoundRobinTEIProvider(tei_urls)
        else:
            raise ValueError(f"Unknown embedding provider: {EMBEDDING_PROVIDER}")

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
