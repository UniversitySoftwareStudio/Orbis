# `embedding/`

Embedding domain split by provider and lifecycle.

## Modules
- `runtime.py`: compatibility exports.
- `service.py`: provider selection + singleton access.
- `config.py`: env configuration parsing.
- `provider_base.py`: provider interface.
- `tei_provider.py`: TEI implementation.
- `ollama_provider.py`: Ollama implementation.
- `providers.py`: provider export surface.

## Flow
```mermaid
flowchart TD
  A[get_embedding_service] --> B[service.py]
  B --> C[config.py]
  B --> D[provider_base.py]
  B --> E[tei_provider.py]
  B --> F[ollama_provider.py]
```

## Relevance
- `service.py` is the single entrypoint used by app code.
- provider files isolate infra-specific logic.
- `runtime.py` preserves old import paths.
