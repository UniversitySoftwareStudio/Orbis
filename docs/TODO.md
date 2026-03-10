
---

## 10) TODO — Data Cleanup & Classification (2026-03-10)

### Archive noise rows
- [ ] Move `/kadro/` and `/staff/` URLs (~6,071 rows) to `knowledge_base_archived`, delete from `knowledge_base` — these are faculty profile pages, pure noise
- [ ] Identify other noise branches to archive (investigation in progress)

### Investigate remaining URL branches
- [ ] `akademik` level-4 sub-pages — what's useful vs noise beyond faculty profiles?
- [ ] `media/uploads/` filenames — map keyword patterns (`yonetmelik`, `staj`, `burs`, `tez`, etc.)
- [ ] `upload/` branch — what's in here?
- [ ] `universite/` branch — what's useful?
- [ ] `haber/` and `etkinlik/` — confirm all noise, archive?

### Classification
- [ ] Add `category` column to `knowledge_base`
- [ ] Write URL-rule classifier for regulatory subset (no embeddings — pure string matching)
- [ ] Target categories: `regulation`, `internship`, `scholarship`, `erasmus`, `exchange`, `thesis`, `financial`, `tenders`

### Embedding versioning
- [ ] Run migration to create `embedding_models` and `knowledge_base_embeddings` tables in DB
- [ ] Backfill existing `knowledge_base.embedding` vectors into `knowledge_base_embeddings` with legacy model registered
- [ ] Add HNSW index on `knowledge_base.embedding` (currently no ANN index — full seq scan on every query)
