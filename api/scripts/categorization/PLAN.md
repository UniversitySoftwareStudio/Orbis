# URL-Space Categorization — Plan

## What we are doing

Assign a `category` label to every row in `knowledge_base` without inspecting 60k rows one by one.

## Core insight

- Many rows share the same URL (same page, multiple chunks). Distinct URLs ≈ 5–15k.
- URL path **is** the semantic signal. `/tr/akademik/fakülte/staj/` and `/en/academic/faculty/internship/` should land near each other in embedding space.
- Embed the URL path strings (not the content) with a **multilingual model** → cluster the URL space → label each cluster → write back to all rows with that URL.

---

## Pipeline (3 scripts, run in order)

### Step 1 — `embed_urls.py`
- Query `SELECT DISTINCT url FROM knowledge_base` → ~5–15k distinct URLs
- Strip the domain, keep the path only
- Batch-embed path strings via TEI behind a single endpoint/LB (strict batch/concurrency limits)
- Output: `url_embeddings.json`
  ```json
  [
    { "url": "https://...", "path": "/tr/akademik/staj/bilgi", "embedding": [0.12, ...] }
  ]
  ```

### Step 2 — `cluster_urls.py`
- Load `url_embeddings.json`
- UMAP → reduce to 10 dims → HDBSCAN cluster
- Output: `url_clusters.json`
  ```json
  [
    { "url": "https://...", "path": "/tr/akademik/staj/bilgi", "cluster_id": 4 }
  ]
  ```
- Also saves `cluster_samples.json` — 10 sample URLs per cluster for human inspection

### Step 3 — `apply_categories.py`
- Takes a `cluster_labels.json` (human-authored, mapping cluster_id → category string)
- Generates and runs `UPDATE knowledge_base SET category = X WHERE url = Y`
- Reports counts per category
- Unclustered/noise cluster (-1) stays NULL — handled separately

---

## Category vocabulary (initial)

| category | signal URLs contain |
|---|---|
| `regulation` | yonetmelik, yonerge, mevzuat |
| `internship` | staj, internship |
| `scholarship` | burs, scholarship |
| `erasmus` | erasmus |
| `exchange` | ikili-degisim, bilateral-exchange |
| `thesis` | tez, lisansustu, graduate |
| `financial` | mali, harc, odeme, tuition, fees |
| `tenders` | ihaleler, ihale |
| `faculty_profile` | kadro, staff (→ archive, not a category) |
| `news` | haber, etkinlik (→ likely archive) |

---

## Resource constraints

- TEI instances are expensive → hard limits:
  - `BATCH_SIZE = 32` (URL paths are short — this is safe)
  - `MAX_WORKERS = 2` (2 concurrent TEI requests max)
  - Configurable via env: `CATEGORIZE_BATCH_SIZE`, `CATEGORIZE_MAX_WORKERS`

## DB contract

- `category` column must exist on `knowledge_base` before Step 3
- Migration: `ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS category VARCHAR(50);`

## Model

- Must be multilingual (handles Turkish and English slug tokens in the same space)
- Same TEI infrastructure already in production (`TEI_URLS` env var)
- Model choice is the operator's responsibility — script just calls the configured TEI endpoint
