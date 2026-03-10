import os

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "tei")
TEI_URL = (os.getenv("TEI_URL") or os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:7860")).rstrip("/")
TEI_URLS_RAW = os.getenv("TEI_URLS", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "all-minilm")


def select_tei_url() -> str:
    urls = [entry.strip().rstrip("/") for entry in TEI_URLS_RAW.split(",") if entry.strip()]
    return urls[0] if urls else TEI_URL
