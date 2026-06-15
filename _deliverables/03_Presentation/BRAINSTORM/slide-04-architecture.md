# Slide 4 — System Design / Architecture (Arda, ~65s)

**Goal:** Show it's a real, layered system — four layers, each with real tech. Slide 3 was the data flow; this one is the tech.

## Say
- "Same system, now by **the tech in each layer**. There are four."
- "**Client** — a React web app: the chatbot, dashboard, My Regulations, and submission review. Answers show up word by word as they stream in."
- "**API** — FastAPI in Python, with login/auth. It has the endpoints for chat, rules, and uploads."
- "**Services / AI** — three engines: search (RAG), the rules pipeline, and the submission checker. We can plug in Groq, Gemini, or others."
- "**Data** — one PostgreSQL database holds both the normal tables and the search vectors. It has two indexes: one for meaning-based search, one for keyword search."
- "Using one database for everything keeps it simple and consistent."

## Show / point at
- Point top to bottom through the four layers. Tap the tech label under each box. The request goes down, the answer streams back up.

## Transition out
- "Building this had real challenges — Atakan will cover them." → hand to Atakan.

## If asked
- "Why pgvector and not a separate vector database?" → "One store means one source of truth and no syncing two systems. At 60,000 rows it's fast enough."
- "Why two indexes?" → "One for meaning, one for exact words. You need both — neither alone is enough."
- "Why no chat memory?" → "It keeps each answer precise and avoids clutter. Short memory is on the future list."

## Don't
- Don't read every endpoint. Name two or three.
- Don't repeat the three paths from slide 3. Here it's the tech stack.
