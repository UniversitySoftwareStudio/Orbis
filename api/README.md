# Orbis Backend

This folder contains the backend logic, RAG pipeline, and database management scripts.

## Key Scripts (`api/scripts/`)

* `embed_database.py`: The master script. Wipes the DB, scrapes sources, and generates embeddings.
* `load_data.py`: The loader script. Takes content of inputted jsonl files from `api/data/` and inserts them into the db while chunking them.
* `fix_pdf_language_and_titles.py`: A very specific script intended to fix the language and title issues of pdf dataset files `api/data/bilgi_pdfs_---.json`.

## Development

To run the API locally without Docker (for debugging) run the following inside `api/` folder:

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Run the server:**
    ```bash
    uvicorn main:app --reload
    ```