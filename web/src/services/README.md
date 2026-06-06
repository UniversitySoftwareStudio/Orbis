# `web/src/services/`

Backend API helpers.

- `api.ts`: authenticated `fetch` wrappers for auth, RAG chat, SIS pages,
  assignments, streaming assignment review, rejection flagging, and regulation
  assignment status updates.

Important conventions:

- All authenticated calls use `credentials: 'include'`.
- A `401` clears local user state and redirects to `/login`.
- Streaming assignment review parses Server-Sent Events from
  `/api/assignments/{id}/submit/stream`.
