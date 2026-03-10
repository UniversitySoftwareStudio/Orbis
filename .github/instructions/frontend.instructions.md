# Frontend — Instructions

Applies to: `web/`

---

## Stack

- **React 19** with TypeScript and Vite
- **No UI framework** — plain CSS in `index.css`, inline styles in `App.tsx`
- **No router** — single page, no `react-router-dom`
- **`react-markdown`** for rendering LLM responses (which contain Markdown with headers, bold, links)

> The developers are familiar with Angular but this project uses React.
> Do not introduce Angular-style patterns (services as classes injected via DI, NgModules, etc.).
> Use React hooks (`useState`, `useEffect`) for state and side effects.

---

## Current State

The entire frontend lives in `web/src/App.tsx` — a single component.
It is a minimal working UI, not a polished product. It will be refactored into proper components
and pages as the SIS features are added.

Two views:
1. **Login form** — shown when `token` state is null
2. **Chat interface** — shown when authenticated

---

## Auth Flow

The backend uses httpOnly cookies for JWT. The frontend cannot read these cookies (that's the point).

**The sentinel pattern:**
```typescript
if (res.access_token) {
  setToken(res.access_token);
  localStorage.setItem('token', res.access_token);
} else {
  // Cookie-based session: store a sentinel string to indicate auth state
  setToken('cookie');
  localStorage.setItem('token', 'cookie');
}
```

This is a known workaround. The string `'cookie'` is used purely as a flag meaning "we have an
authenticated session via httpOnly cookie". It is not a real token and is not sent in headers.
All actual auth happens via the cookie, which is sent automatically by the browser (`credentials: 'include'`).

Do not replace this with a real token stored in localStorage — that would be a security regression.

---

## API Communication (`web/src/services/api.ts`)

Two methods:

### `api.post(endpoint, data, token?)`
Standard JSON POST for login and other non-streaming calls.
Always passes `credentials: 'include'` so cookies are sent.

### `api.chatStream(message, token, onChunk)`
Streaming POST to `/api/chat`. Reads the response as a `ReadableStream`.
The backend returns raw text chunks (not SSE `data:` formatted events — see note below).

```typescript
const reader = response.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const chunk = decoder.decode(value, { stream: true });
  onChunk(chunk);
}
```

Each chunk from `onChunk` is appended to the last assistant message in state.

**Note:** The backend `rag/service.py` yields raw text from the LLM (not `data: {...}\n\n` SSE format).
The frontend reads it as a plain stream. The old `/api/regulations/ask` endpoint which used SSE format
has been removed along with `regulation_service.py`.

---

## State Management

All state is in `App.tsx` with `useState`:
- `token` — auth sentinel (`null` = logged out, `'cookie'` or real token = logged in)
- `messages` — array of `{ role: 'user' | 'assistant', content: string }`
- `input` — current text input value
- `isLoading` — whether the assistant is currently streaming

**Streaming message update pattern:**
```typescript
setMessages(prev => {
  const newMsgs = [...prev];
  const lastMsgIndex = newMsgs.length - 1;
  const lastMsg = { ...newMsgs[lastMsgIndex] };  // shallow copy — prevents double-render bug
  if (lastMsg.role === 'assistant') {
    lastMsg.content += chunk;
    newMsgs[lastMsgIndex] = lastMsg;
  }
  return newMsgs;
});
```
The shallow copy of the last message object is intentional — it prevents React from detecting
a mutation on the same object reference, which caused a content duplication bug.

---

## What NOT To Do

- Do not add a state management library (Redux, Zustand, etc.) without discussion — the app is
  simple enough that local state is fine for now
- Do not switch to `axios` — the streaming implementation relies on the native Fetch `ReadableStream` API
- Do not store real JWT tokens in localStorage — keep the httpOnly cookie approach
- Do not install a CSS framework without discussion — keep styles minimal for now