# Data Pipeline — Detailed Instructions

Applies to: `api/scripts/`, `api/ingest/`, `api/data/`, `api/database/models.py` (KnowledgeBase)

---

## Data Sources

All university data comes from two public websites:

| Source | URL | Content |
|--------|-----|---------|
| Course catalog | `ects.bilgi.edu.tr` | Structured course data with ECTS, department, descriptions |
| University website | `bilgi.edu.tr` | Web pages + downloadable PDFs |

---

## The Three Data Types and Their JSONL Schemas

All data is stored as JSONL before ingestion. Each line is one record.

### 1. Courses (`*_courses_data.jsonl`)
```json
{
  "url": "https://ects.bilgi.edu.tr/Course/Detail?catalog_courseId=XXXXX",
  "language": "en",
  "title": "DEPT 101 - Example Course Name",
  "content": "Course description text...",
  "detected_date": "2025-2026",
  "scraped_at": "2026-01-01T12:00:00",
  "type": "course",
  "metadata": {
    "course_code": "DEPT 101",
    "department": "Example Department",
    "ects": "6"
  }
}
```
Courses are stored as **single records** — they are not chunked. The description fits comfortably
within the embedding model's token limit.

### 2. University Web Pages (`*_university_data.jsonl`)
```json
{
  "url": "https://www.bilgi.edu.tr/example/page",
  "language": "tr",
  "title": "Example Page",
  "content": "Full page text...",
  "scraped_at": "2026-01-01T12:00:00",
  "detected_date": null,
  "type": "web_page",
  "metadata": {
    "breadcrumbs": ["Home", "Services"]
  }
}
```

### 3. PDFs (`*_pdfs_important.jsonl`)
```json
{
  "url": "https://www.bilgi.edu.tr/example.pdf",
  "type": "pdf",
  "title": "Example Document",
  "content": "Extracted PDF text...",
  "metadata": { "title": "Example", "page_count": 10 },
  "language": "tr"
}
```

---

## Data Volume and Distribution

Understanding what the data looks like is essential for understanding the RAG system's design.

### Web pages (~12,600 total)
| Category | Count | % | Notes |
|----------|-------|---|-------|
| News & Announcements (`/haber/`) | ~4,160 | 33% | Mostly temporal, low fact value |
| Events (`/etkinlik/`) | ~4,035 | 32% | Past/future events |
| Academic (faculties, courses) | ~2,268 | 18% | High value |
| University Info (rules, admin) | ~1,008 | 8% | Highest value — regulations, policies |
| Student Life | ~630 | 5% | Transport, clubs, support |
| Other | ~507 | 4% | International, research centers |

**Critical insight:** 65% of web data is temporal (News + Events). This is why the RAG router
must avoid returning `/haber/` URLs for factual queries. A user asking "What is the scholarship
policy?" must not get a 2018 news article announcing a policy change.

### PDFs (~1,595 kept after filtering)
| Category | Count | Action |
|----------|-------|--------|
| Regulations, handbooks, Erasmus guides | ~330 | Kept (core knowledge) |
| General info, newsletters, syllabuses | ~900+ | Kept |
| Tenders, construction bids (`/ihaleler/`) | ~315 | Filtered out (noise) |
| Recruitment result lists | ~400 | Filtered out (noise) |
| Faculty CVs/resumes (`/resume/`) | ~335 | Kept separately (`*_resumes.jsonl`) |

---

## The Single KnowledgeBase Table Design

**All content types (courses, web pages, PDFs) live in one table.**

```sql
CREATE TABLE knowledge_base (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url         TEXT NOT NULL,
    title       TEXT,
    content     TEXT,              -- chunk text (or full course description)
    language    VARCHAR(10),       -- 'en' or 'tr'
    type        VARCHAR(50),       -- 'course', 'web_page', 'pdf'
    metadata    JSONB DEFAULT '{}',
    embedding   vector(384),
    search_vector TSVECTOR,        -- GENERATED ALWAYS AS column
    created_at  TIMESTAMP DEFAULT NOW()
);
```

**Why one table?** The retrieval logic treats all content types uniformly — they are all just
"chunks of text about the university". Splitting into separate tables would require UNION queries
in all search operations. The `type` column is used for filtering when needed.

### Indexes
- `hnsw` on `embedding` — fast approximate nearest-neighbor for vector search
- `gin` on `search_vector` — fast full-text search
- `btree` on `type` and `url`

---

## The `search_vector` Column

This is a `GENERATED ALWAYS AS ... STORED` computed column:

```sql
search_vector tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector(
        CASE WHEN language = 'tr' THEN 'turkish'::regconfig ELSE 'english'::regconfig END,
        coalesce(title, '')
    ), 'A') ||
    setweight(to_tsvector(
        CASE WHEN language = 'tr' THEN 'turkish'::regconfig ELSE 'english'::regconfig END,
        coalesce(content, '')
    ), 'B')
) STORED
```

Key points:
- Language stemming switches automatically based on the `language` column
- Title is weighted 'A' (higher priority), content is weighted 'B'
- Because it is `GENERATED ALWAYS`, you cannot insert into this column manually
- Any schema change to `title`, `content`, or `language` columns requires dropping and recreating
  this column — it does not update automatically when you run `ALTER TABLE` on other columns
- The `load_data.py` script drops and recreates this column before ingestion to handle this

---

## The `metadata_` Alias

In `database/models.py`, the JSONB metadata column is defined as:

```python
metadata_ = Column("metadata", JSONB, default={})
```

**Why the underscore?** SQLAlchemy's `DeclarativeBase` uses `metadata` as an internal attribute
on all model classes. Naming the column `metadata` without aliasing would shadow SQLAlchemy's
internal object and cause subtle bugs. The actual PostgreSQL column is still named `metadata`
(via the string argument to `Column`).

**Always access it as `doc.metadata_` in Python code.**
When reading from it safely (in case of legacy data), use:
```python
meta = getattr(doc, "metadata_", getattr(doc, "metadata", {})) or {}
```
This pattern appears throughout `rag_service.py` and `rag_repository.py`.

---

## Language Detection Algorithm

A custom "Stopword Race" algorithm is used — not a library, not character counting.

**Why not character counting (ş, ğ, ö, etc.)?**
Turkish-specific characters appear in English documents that reference local addresses and names
(e.g., "Santral Campus", "Halıcıoğlu"). Character counting produces false positives for Turkish.

**The Stopword Race:**
```python
en_stops = {'the', 'and', 'to', 'of', 'in', 'is', 'for', ...}
tr_stops = {'ve', 'bir', 'bu', 'ile', 'için', 'olarak', ...}

# Count how many words in the text match each list
# Title is weighted 3x relative to content
# Turkish also gets bonus points per Turkish character found
# If Turkish score > (English score * 1.2) and Turkish score > 2 → 'tr', else 'en'
```

This lives in `api/scripts/fix_pdf_language_and_titles.py`.

---

## Title Cleaning Rules

PDF documents often have garbage titles from the PDF metadata field. Cleaning rules:

1. **Empty title** → extract from URL (decode `%20`, strip extension, capitalize)
2. **Generic/banned titles** ("Microsoft Word", "PowerPoint Presentation", "Untitled", "Adsız") → replace with URL-derived title
3. **Title longer than 200 chars or 25 words** → replace with URL-derived title
4. **Hash code removal** — only if the title has more than one word:
   - `"Yönerge 5V3Vrrc"` → `"Yönerge"` (trailing alphanumeric token removed)
   - `"Binder2"` → `"Binder2"` (single-word title, no removal — "2" alone isn't a hash)
5. **Metadata sync** — after cleaning, `metadata['title']` must always match the `title` column.
   This is called "split-brain prevention". If they differ, retrieval context is inconsistent.

---

## Chunking Strategy

Web pages and PDFs are chunked before ingestion. Courses are not chunked.

- **Chunk size:** 150 words (hard-capped at 150 to stay within the embedding model's 256 token limit)
- **Overlap:** 30 words between chunks
- **Chunk index stored in metadata:** `metadata['chunk_index']` and `metadata['total_chunks']`

The same URL can produce multiple rows in `knowledge_base`, one per chunk.
The `get_by_url()` method in `rag_repository.py` fetches all chunks for a URL to reconstruct
the full document during the Smart Context Expansion step.

---

## Active Data Scripts (in `api/scripts/`)

These are the three scripts that make up the current data pipeline.
The `api/ingest/` folder is a legacy pipeline from an earlier prototype — do not use it.

| Script | Purpose | When to run |
|--------|---------|-------------|
| `fix_pdf_language_and_titles.py` | Cleans PDF titles, detects language, syncs `metadata['title']` | Before `load_data.py`, on raw JSONL files |
| `load_data.py` | Reads JSONL files and inserts chunked records into `knowledge_base` with `embedding = NULL` | After fixing metadata |
| `embed_database.py` | Generates vectors for all rows where `embedding IS NULL`, commits in batches | After `load_data.py` |

Run order: `fix_pdf_language_and_titles.py` → `load_data.py` → `embed_database.py`

The scraping scripts that produced the JSONL files originally are not in this repository.

**Embedding text format** (from `scripts/embed_database.py`):
```
{title}
Category/Path: {breadcrumbs joined with ' > '}   ← for web pages
Course Code: {course_code}                         ← for courses
{content}
```
The title and metadata context are prepended to help the embedding model understand the document's
category before reading the content.

---

## PDF Filtering (What Was Excluded and Why)

Two categories were removed to prevent retrieval noise:

**Tenders (`/ihaleler/`):**
Construction bids and technical specs contain legalistic language ("Article 5", "Obligations",
"Deadlines") that overlaps with regulation documents. They would surface in searches for exam rules.
Excluded by URL pattern and keywords: "teklif mektubu", "teminat mektubu", "teknik şartname".

**Recruitment result lists:**
Lists of candidate names and scores contain many proper nouns and numbers, poisoning the
vector space for faculty or policy searches.
Excluded by keywords: "sonuç listesi", "değerlendirme sonucu", "ön değerlendirme".

**Hard inclusion overrides (Erasmus protection):**
Any document containing "erasmus", "exchange", "staj", "handbook", "yönerge" is always kept,
even if other keywords would trigger exclusion. An "Erasmus Application Result" must not be
accidentally filtered by the "result list" rule.

---

## What NOT To Do

- **Do not manually insert into `search_vector`** — it is a GENERATED ALWAYS column
- **Do not change chunk size without re-running the full embed pipeline** — existing chunks in the DB
  will be inconsistent with new chunks if the size changes
- **Do not rename the `metadata` column in PostgreSQL** — it would break the `metadata_` alias mapping
- **Do not ingest `bilgi_pdfs_irrelevant.jsonl` or `bilgi_pdfs_resumes.jsonl`** — these are kept
  as reference files but intentionally excluded from the DB. Only `bilgi_pdfs_important.jsonl` is ingested
- **Do not use cosine distance for vector search on the current model** — L2 distance is what the
  current production query uses and what the system has been tuned around