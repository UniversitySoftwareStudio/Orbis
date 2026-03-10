import os
from rich.console import Console

console = Console()
RAG_DEBUG = os.getenv("RAG_DEBUG", "").lower() in {"1", "true", "yes", "on"}