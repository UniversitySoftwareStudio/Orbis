from embedding.provider_base import EmbeddingProvider

from sentence_transformers import SentenceTransformer

class LocalProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") -> None:
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()

    def get_dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()