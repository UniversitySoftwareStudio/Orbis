import requests

from embedding.provider_base import EmbeddingProvider


class TEIProvider(EmbeddingProvider):
    SAFE_CHAR_LIMITS = (500, 420, 340, 280, 220, 180, 140, 100)

    def __init__(self, api_url: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.dimension = 384
        self._validate_connection()

    def _validate_connection(self) -> None:
        response = requests.post(f"{self.api_url}/embed", json={"inputs": "connection test"}, timeout=5)
        response.raise_for_status()
        self.dimension = len(response.json()[0])

    def _embed_with_backoff(self, text: str, timeout: int = 10) -> list[float]:
        value = (text or "").strip()
        if not value:
            raise ValueError("Text cannot be empty")

        last_413: Exception | None = None
        tried: set[str] = set()

        for max_chars in self.SAFE_CHAR_LIMITS:
            candidate = value if len(value) <= max_chars else value[:max_chars]
            if candidate in tried:
                continue
            tried.add(candidate)
            try:
                response = requests.post(f"{self.api_url}/embed", json={"inputs": candidate}, timeout=timeout)
                response.raise_for_status()
                return response.json()[0]
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 413:
                    last_413 = exc
                    continue
                raise

        if last_413 is not None:
            raise RuntimeError(f"TEI kept returning 413 after truncation to {self.SAFE_CHAR_LIMITS[-1]} chars") from last_413
        raise RuntimeError("TEI embedding failed")

    def embed_text(self, text: str) -> list[float]:
        return self._embed_with_backoff(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        cleaned = [(text or "").strip() for text in texts]
        cap = self.SAFE_CHAR_LIMITS[0]
        short = [value if len(value) <= cap else value[:cap] for value in cleaned]

        try:
            response = requests.post(f"{self.api_url}/embed", json={"inputs": short}, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 413:
                return [self._embed_with_backoff(value) for value in cleaned]
            raise

    def get_dimension(self) -> int:
        return self.dimension
