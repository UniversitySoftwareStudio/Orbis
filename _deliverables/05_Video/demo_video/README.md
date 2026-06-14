# Orbis auto demo recorder

Drives the real Orbis web app through the three use cases and records a video
for Slide 10: **Ask → Obligation → Submit**.

## What it does

Playwright launches Chromium at 1920×1080, logs in as the seeded demo student,
then records:

1. **Ask** — opens the chat widget, types a question, waits for the streamed
   cited answer.
2. **Obligation** — navigates to *My Regulations*, scrolls through the
   personalized source-backed rules.
3. **Submit** — navigates to *Assignments* (the upload + live SSE review is
   interactive; see note in the script to extend with a file upload).

Output: a silent 1080p `.webm` in `./out/`. Add voiceover/captions after, or
convert to mp4 with the ffmpeg line the script prints.

## Prereqs (must be running BEFORE recording)

```bash
# 1. backend
cd api && ./run.sh                 # http://localhost:8000

# 2. seed the demo student (password: demo1234)
python api/scripts/seed_students.py

# 3. frontend
cd web && npm run dev              # http://localhost:5173
```

## Record

```bash
cd _deliverables/05_Video/demo_video
npm i -D playwright && npx playwright install chromium
node record_demo.mjs
```

Watch it run (non-headless) while you tune timing:

```bash
HEADLESS=false node record_demo.mjs
```

## Tunables (env vars)

| Var | Default | Purpose |
|-----|---------|---------|
| `BASE_URL` | `http://localhost:5173` | frontend URL |
| `EMAIL` | `a.acar@bilgiedu.net` | demo login |
| `PASSWORD` | `demo1234` | demo password |
| `ASK_QUERY` | `How do I apply for Erasmus?` | chatbot question |
| `HEADLESS` | `true` | `false` to watch live |

## Honest limitations

- **Selectors may drift.** Login button / chat input are matched heuristically;
  if the UI changed, run with `HEADLESS=false` and adjust the locators.
- **Silent video.** Playwright records no audio. For the Moodle 1-min deliverable
  you'll add narration/captions in an editor afterward; for the Slide 10 clip,
  silent is usually fine.
- **The submit flow is only shown, not fully driven.** The upload→approve/reject
  SSE stream is interactive; the script stops at the assignments view. Extend it
  with the commented `filechooser` block + a `sample_submission.pdf`, or record
  that one step manually.
- **Timing is hand-tuned** (`beat()` calls). The chat answer wait is 9s; bump it
  if your local LLM is slower.
