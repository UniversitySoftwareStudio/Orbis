# API

This is the backend. It talks to the frontend.

## What's inside?

```
api/
├── main.py        # The app starts here
└── app/           # Your code goes here
    ├── routes/    # URLs and endpoints (calls services)
    ├── services/  # The smart stuff (AI, logic)
    └── models/    # Data shapes (used by routes & services)
```

## Flow

```
User → routes → services → response
              ↓
           models (validates data)
```

## Run it

```bash
python main.py
```

Goes to: http://localhost:8000

## Ingest data (fast, no embeddings)

Compute preprocessing stats (including TEI max token limits):

```bash
python -m ingest.preprocess_report --tei-url http://localhost:7860
```

Ingest JSONL into Postgres (creates Courses, Documents, Chunks; optional demo SIS data):

```bash
python -m ingest.ingest_db --reset --seed-demo --tei-url http://localhost:7860
```

Notes:
- Your TEI server reports `max_input_length=256` and `auto_truncate=false`, so chunking must be token-safe.
- `--tei-url` makes ingestion use TEI `/tokenize` to build chunks that stay within the model’s input length.

## Backfill embeddings (slow, run later)

Once the DB is filled and TEI/Ollama is stable, backfill pgvector columns:

```bash
python -m ingest.embed_backfill --only all --batch-size 32
```

## Multiple TEI servers (round robin)

If you run more than one TEI container, set `TEI_URLS` (comma-separated) so the API
distributes embedding calls across them in round-robin order:

```bash
TEI_URLS=http://localhost:7860,http://localhost:7861,http://localhost:7862
```

If `TEI_URLS` is not set, the API falls back to `TEI_URL` / `EMBEDDING_SERVICE_URL`.

## How to add stuff

**Add a new endpoint:**
1. Make a file in `app/routes/` (e.g., `user.py`)
2. Copy the pattern from `routes/README.md`
3. Import it in `main.py` and add: `app.include_router(user.router)`

**Add AI logic:**
1. Make a file in `app/services/` (e.g., `rag_service.py`)
2. Write your class/functions
3. Import and use in routes

**Add data model:**
1. Make a file in `app/models/` (e.g., `user.py`)
2. Define Pydantic models
3. Use them in routes for validation

That's it. Build and go!
