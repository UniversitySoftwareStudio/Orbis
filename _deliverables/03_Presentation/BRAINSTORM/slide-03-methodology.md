# Slide 3 — Methodology / Approach (Arda, ~70s)

**Goal:** Show the three paths (Pull / Push / Review) and how the data flows into them. This is the big map slide — walk it left to right.

## Say
- "Orbis works in **three ways**."
- "**Pull** — the student asks a question, and we answer from official sources, with links."
- "**Push** — we pull obligations out of the rules and send them to the student *before* they ask."
- "**Review** — when a student turns in work, we check it against what the assignment asked for."
- "All three run on one data path: **80 official web pages → about 60,000 text chunks → 125 topic groups → 935 rule chunks → 178 obligations → 176 assignments**."
- "The main trick: before any AI runs, we sort rules from noise. So the rule engine never sees news or ads — only real rules."
- "Tools: MiniLM for embeddings and a Jina reranker for search; a two-pass AI for pulling rules; a two-step AI for checking submissions. All stored in PostgreSQL."
- "We built it step by step — build a part, test it, improve it. I did the scraping and the chatbot; Atakan did the rules pipeline, matching, and the submission checker."

## Show / point at
- Follow the arrow left to right: collect data → clean it → sort rules from noise → one database → the three paths → student.

## Transition out
- "That's the data flow. Now the tech behind it." → stay on (Arda goes to slide 4).

## If asked
- "Why use entropy on URLs?" → "It's a cheap way to tell real folders from junk auto-made pages, before we do the heavier sorting."
- "Why sort rules out first?" → "If you mix rules with news and forum text, both search and rule-pulling get worse. Sorting first keeps them clean."

## Don't
- Don't read the six numbers like a list. Say them as a journey: → → →.
- Don't dive deep into any one tool here. That's slides 4–5.
- Watch the clock — this slide is full, 70s goes fast.
