"""
Step 1: Fetch distinct URLs, embed their paths, write url_embeddings.json.

Env:
  DATABASE_URL  — postgres connection string
  TEI_URL       — single TEI endpoint (default http://localhost:7861)
  BATCH_SIZE    — default 4
"""

import json
import os
import time
from urllib.parse import urlparse

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

OUTPUT = os.path.join(os.path.dirname(__file__), "url_embeddings.json")
TEI_URL = os.getenv("TEI_URL", "http://localhost:7861").rstrip("/")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 4))


def fetch_distinct_urls():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT url FROM knowledge_base WHERE url IS NOT NULL AND url <> ''")
    rows = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def url_to_path(url: str) -> str:
    path = urlparse(url).path.rstrip("/") or "/"
    return path.replace("-", " ").replace("_", " ")


def embed_batch(paths: list[str], retries: int = 5) -> list[list[float]]:
    for attempt in range(retries):
        try:
            r = requests.post(f"{TEI_URL}/embed", json={"inputs": paths}, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            print(f"\n  retry {attempt+1} after error ({e}) — waiting {wait}s")
            time.sleep(wait)


def main():
    urls = fetch_distinct_urls()
    batches = [urls[i:i + BATCH_SIZE] for i in range(0, len(urls), BATCH_SIZE)]
    print(f"{len(urls)} distinct URLs → {len(batches)} batches of {BATCH_SIZE} → {TEI_URL}")

    results = []
    for i, batch_urls in enumerate(batches):
        batch_paths = [url_to_path(u) for u in batch_urls]
        embeddings = embed_batch(batch_paths)
        for url, path, emb in zip(batch_urls, batch_paths, embeddings):
            results.append({"url": url, "path": path, "embedding": emb})
        print(f"  {i+1}/{len(batches)}", end="\r")

    print(f"\nWriting {len(results)} entries to {OUTPUT}")
    with open(OUTPUT, "w") as f:
        json.dump(results, f)
    print("Done.")


if __name__ == "__main__":
    main()
