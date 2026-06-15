# Slide 7 — Results & Testing 2/2: submission check + safety (Atakan, ~65s)

**Goal:** Land the safety story — it never rejected real work, and the redesign clearly helped.

## Say
- "The submission checker was tested on **32 cases** — 4 assignments, 8 hard tests each."
- "**93.8% accuracy, and recall of 1.000.** That means **it never rejected real work**, which is the safe side to err on in school."
- "The only mistake is approving some half-done drafts — 2 cases — and that's why we plan a 'flag for review' option."
- "Seven of the eight test types are handled perfectly — empty files, broken files, wrong file, wrong extension."
- "Best proof it's real work: the **before-and-after**. Going from a one-step to a two-step checker raised accuracy from 0.781 to 0.938, and injection resistance from 1 of 4 to **4 of 4**."
- "To be clear: that's the injection cases we tested. It's a good sign, not a full promise."

## Show / point at
- Metric card → the table (point out zero real-work rejections) → the 8-test bar → the before/after arrows → injection 4/4.

## Transition out
- "Arda will wrap up what it all means." → hand to Arda.

## If asked
- "Why count half-done drafts as reject?" → "The checker only says approve or reject for now, so a half-done draft counts as reject. A real 'flag' option is future work."
- "32 cases is small — is it solid?" → "Fair, and we say so. It's a careful, repeatable stress test, not a big survey. Treat injection 4/4 as a good sign."
- "What about a smarter attack?" → "No promise it'd hold. That's why splitting orders from data and adding pattern checks are our next steps."

## Don't
- Don't say it's injection-proof. Repeat "the cases we tested."
- Don't skip the appeal path — if it wrongly rejects, the student can flag it and a human checks. Nothing is final.
