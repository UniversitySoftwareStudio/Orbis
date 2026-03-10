# Update Project Instruction Files

You are updating the AI context/instruction files for this project after a period of development.
Your job is to keep the instruction files accurate without destroying the decisions and reasoning
already documented in them.

---

## Step 1 — Read everything first

Before touching any file, read ALL of the following in full:

- `CLAUDE.md`
- `.github/copilot-instructions.md`
- `.github/instructions/rag-pipeline.instructions.md`
- `.github/instructions/data-pipeline.instructions.md`
- `.github/instructions/sis.instructions.md`
- `.github/instructions/frontend.instructions.md`

Do not skip any of these. Do not skim. The reasoning documented in these files is intentional
and must be preserved unless the code explicitly contradicts it.

---

## Step 2 — Get the diff

Run the following in the terminal to see what changed since the last update:

```bash
git log --oneline -20
```

Then run:

```bash
git diff HEAD~1 HEAD -- api/ web/
```

If you know the approximate date of the last instruction update, you can also run:

```bash
git log --oneline --since="YYYY-MM-DD"
```

to get a list of commits, then diff the range:

```bash
git diff <oldest-commit-hash> HEAD -- api/ web/
```

Read the full diff carefully before proceeding.

---

## Step 3 — Categorize changes

Before making any edits, produce a written summary of what you found, organized into these categories:

**A. New files or modules added**
List them and what they appear to do.

**B. Existing files significantly changed**
List them and describe what changed functionally (not line-by-line).

**C. Things deleted or removed**
List anything removed that is currently documented in the instruction files.

**D. New bugs or incomplete things visible in the diff**
List anything that looks broken, inconsistent, or unfinished.

**E. Things that changed but are already correctly documented**
List things where the instructions are still accurate — these require no update.

**F. Uncertain items**
List anything in the diff you do not understand well enough to document accurately.

Do not proceed to Step 4 until this summary is written out in full.

---

## Step 4 — Update rules (read carefully before touching any file)

### What you MUST preserve

- Every "why we did it this way" explanation must survive unless the code now does something different.
  Changing the implementation does not automatically invalidate the reasoning — check both.
- Every item in "What NOT To Do" sections must survive unless there is explicit evidence in the diff
  that the constraint no longer applies.
- The two-rerank architecture explanation in `rag-pipeline.instructions.md` must not be simplified,
  collapsed, or generalized. If the pipeline changed, rewrite the explanation accurately — do not
  just remove the nuance.
- The `metadata_` alias explanation must survive as long as the alias still exists in `models.py`.
- All "LEGACY" labels on `api/experiments/`, `api/ingest/`, and `docker-compose.yml` must survive
  unless those folders were explicitly removed from the repo.
- The known bugs section must be kept accurate: remove bugs that are confirmed fixed, add new ones
  found in Step 3D. Do not remove a bug entry just because you are unsure — leave it and flag it.

### What you MUST NOT do

- Do not rewrite accurate content just to make it shorter or cleaner.
- Do not remove specific technical details (algorithm names, parameter values, distance metrics,
  threshold numbers like `RERANK_INPUT_CAP = 75`) unless they genuinely changed.
- Do not generalize a specific decision into a vague statement.
  Bad: "The system uses reranking for better results."
  Good: "The pre-expansion rerank identifies the True Top 3 documents before expansion runs."
- Do not add anything you are not confident about. If you are unsure whether something is a
  permanent decision or a temporary state, say so explicitly and mark it with a `> ⚠️ Verify:` note.
- Do not touch `sis.instructions.md` unless there are clear, confirmed SIS changes in the diff.
  The SIS is marked as unstable and under active refactoring — be conservative.
- Do not update the running commands section unless you confirmed the commands actually changed.

### When to update which file

| File | Update when |
|------|------------|
| `copilot-instructions.md` | Stack changes, new folders, new conventions, bugs fixed or introduced, run commands changed |
| `rag-pipeline.instructions.md` | Any change to `rag_service.py` or `rag_repository.py` |
| `data-pipeline.instructions.md` | Any change to `api/scripts/`, `api/data/`, or `KnowledgeBase` schema |
| `sis.instructions.md` | Confirmed SIS model or repository changes only |
| `frontend.instructions.md` | Any change to `web/src/` |
| `CLAUDE.md` | Only if files were added, removed, or renamed — the table of contents must stay accurate |

---

## Step 5 — Make the edits

Edit only the files that need updating based on Step 3 and the rules in Step 4.
For each file you edit, state at the top of your response what you changed and why,
before showing the edit.

If Step 3F (uncertain items) is non-empty, do not guess. Add `> ⚠️ Verify:` callout blocks
in the relevant instruction file for each uncertain item, so a human can review them.

---

## Step 6 — Sanity check

After all edits, re-read each file you modified and confirm:

1. No "why we did it this way" explanations were lost
2. No "What NOT To Do" items were silently removed
3. No specific numbers or thresholds were generalized away
4. The known bugs section reflects the current reality
5. `CLAUDE.md` still accurately describes what files exist and what they cover

If any of these checks fail, fix the issue before finishing.