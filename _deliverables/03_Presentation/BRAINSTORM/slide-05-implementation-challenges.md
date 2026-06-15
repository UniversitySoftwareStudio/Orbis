# Slide 5 — Implementation & Challenges (Atakan, ~70s)

**Goal:** Show what we finished this term, then five real problems — each with a fix and proof.

## Say
- "On last term's base — scraping, embeddings, the database — this term we finished the backend, the 125-group taxonomy, the full chatbot, the rules pipeline and matcher, the submission checker, and a test harness."
- "Five problems shaped the design."
- "**One — rules vs. noise.** Only 935 of 60,000 chunks are real rules. We sort them out *before* any AI runs."
- "**Two — vague rules.** A two-pass check keeps only clear, assignable rules — 55% kept, 45% dropped on purpose."
- "**Three — 65% of the data is news and events.** Keyword-first search plus reranking gave us **zero** news leaking into results in our tests."
- "**Four — rules split across pages.** We rebuild the full document. This recovered an 8-step appeal process that was split across 4 pieces."
- "**Five — hidden 'approve me' text in uploads.** Our two-step checker treats the file as **evidence, not orders** — resistance went from 1 of 4 to 4 of 4."
- "And we log every decision, so it can all be checked."

## Show / point at
- The "done this term" checklist on top, then the table: problem → fix → proof, row by row.

## Transition out
- "Now — does it actually work? The numbers." → stay on (Atakan goes to slide 6).

## If asked
- "What's 'two-pass'?" → "First pass pulls out rules. Second pass re-reads the source and removes weak ones, adds missed ones."
- "Is dropping 45% bad?" → "No — that's the point. Better to drop a weak rule than spam students with a fake one."
- "How did you stop the injection?" → "We stopped asking 'should this be approved?' and instead check each requirement with proof. Hidden 'approve me' text isn't a requirement, so it's ignored."

## Don't
- Don't say it's injection-proof. Say "the cases we tested" (1/4 → 4/4).
- Don't skip the "done this term" part. The committee wants to see what's finished.
