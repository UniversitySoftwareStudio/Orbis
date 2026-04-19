import os

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

EMBEDDING_URL = (
    os.getenv("EMBEDDING_URL")
    or os.getenv("EMBEDDING_SERVICE_URL")
    or os.getenv("TEI_URL")
    or "http://embedding-lb"
).rstrip("/")

EMBEDDING_MODEL = (os.getenv("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL).strip()
