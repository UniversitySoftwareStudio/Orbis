# `routes/`

HTTP entrypoints only. Keep route files thin.

## Modules
- `auth.py`: register/login/me/refresh.
- `logout.py`: logout endpoint (cookie invalidation).
- `search.py`: chat/search/ask endpoints.

## Flow
```mermaid
flowchart TD
  A[HTTP request] --> B[routes/*.py]
  B --> C[services/*.py]
  C --> D[database/* or rag/*]
  C --> E[response/SSE]
```

## Rule
- Validate request/identity in routes.
- Put business logic in `services/`.
