import os

# ─── RAG Settings ─────────────────────────────────────────────────────────────

# Retrieval
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "30"))
RAG_FINAL_K = int(os.getenv("RAG_FINAL_K", "10"))
RAG_PARALLEL_MODE = os.getenv("RAG_PARALLEL_MODE", "true").lower() in {"1", "true", "yes", "on"}

# Reranker
RAG_RERANK_MODEL = os.getenv("RAG_RERANK_MODEL", "jina-reranker-v2-base-multilingual")

# LLM
RAG_LLM_MAX_TOKENS = int(os.getenv("RAG_LLM_MAX_TOKENS", "1024"))
RAG_STREAM_ENABLED = os.getenv("RAG_STREAM_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

# Context
RAG_MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))
RAG_COMPACT_SQL_THRESHOLD = int(os.getenv("RAG_COMPACT_SQL_THRESHOLD", "5"))
RAG_COMPACT_DOC_THRESHOLD = int(os.getenv("RAG_COMPACT_DOC_THRESHOLD", "40"))
