# Orbis Frontend

React + Vite + TypeScript frontend for the Orbis student experience.

## Active Screens

- `/dashboard`: SIS summary, active regulation count, deadlines, calendar.
- `/chat`: streaming RAG assistant.
- `/calendar`: academic calendar.
- `/schedule`: current student's weekly schedule.
- `/courses`: enrolled course cards.
- `/assignments`: pending assignments, file upload, live submission-agent
  reasoning, rejection flagging.
- `/transcript`: transcript projection.
- `/regulations`: active regulation assignments with status updates.
- `/profile`: authenticated user's academic profile.
- `/settings`: local UI settings.

## Structure

```text
web/
  src/
    App.tsx              protected route shell
    components/          shared UI such as Sidebar
    contexts/            auth, theme, i18n state
    pages/               full screen views
    services/api.ts      backend calls and SSE readers
    locales/             English/Turkish strings
```

## Run

```bash
npm install
npm run dev
```

Default URL: `http://localhost:5173`

The frontend expects the backend at `http://localhost:8000/api`. Auth is
cookie-based (`credentials: include`), so both frontend and backend need to run
on the allowed local origins from `api/main.py`.

## Notes For Documentation And Demo

- The assignment page stores the latest local review snapshot in
  `localStorage` for UI continuity, while the backend persists the authoritative
  submission row.
- Submission review is streamed over `/api/assignments/{id}/submit/stream`.
- Regulation assignments are read from `/api/regulations/me`; the UI does not
  trigger the historical rule-assignment pipeline.
