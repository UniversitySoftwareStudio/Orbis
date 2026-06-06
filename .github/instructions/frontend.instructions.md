# Frontend — Instructions

Applies to: `web/`

---

## Stack

- **React 19** with TypeScript and Vite
- **react-router-dom** for client-side routing (login + a protected multi-page shell — dashboard, chat, calendar, schedule, courses, assignments, transcript, regulations, profile, catalog, notifications, settings)
- **i18next** + **react-i18next** for internationalization (Turkish and English)
- **lucide-react** for icons
- **react-markdown** for rendering LLM responses (which contain Markdown with headers, bold, links)
- **Plain CSS** in `index.css` using CSS custom properties for theming — no CSS framework

> The developers are familiar with Angular but this project uses React.
> Do not introduce Angular-style patterns (services as classes injected via DI, NgModules, etc.).
> Use React hooks (`useState`, `useEffect`) for state and side effects.

---

## Architecture — Multi-Page with Context Providers

The frontend was originally a single `App.tsx` monolith. It has been refactored into:

```
web/src/
├── App.tsx                    # Thin routing shell (ThemeProvider → AuthProvider → BrowserRouter)
├── main.tsx                   # Entry point (imports i18n.ts for side-effect initialization)
├── i18n.ts                    # i18next setup with TR/EN
├── index.css                  # Global styles using CSS custom properties
├── types.ts                   # Shared types (Message interface)
├── contexts/
│   ├── AuthContext.tsx         # Auth state, login/logout, chat history, token refresh
│   └── ThemeContext.tsx        # Dark/light mode, accent colors, background presets
├── components/
│   └── Sidebar.tsx            # Collapsible nav sidebar (links, theme picker, language toggle, logout)
├── pages/                     # one page = one screen
│   ├── LoginPage.tsx          # Login form
│   ├── DashboardPage.tsx      # Default landing — stats + deadlines + calendar (/api/sis/dashboard)
│   ├── ChatPage.tsx           # RAG chat interface (extracted from old App.tsx)
│   ├── CalendarPage.tsx       # Academic calendar view (/api/sis/calendar)
│   ├── SchedulePage.tsx       # Visual weekly schedule grid (/api/sis/schedule/me)
│   ├── CoursesPage.tsx        # Current enrolled courses (/api/sis/courses/me)
│   ├── AssignmentsPage.tsx    # Assignments + streamed submission check (/api/assignments/*)
│   ├── TranscriptPage.tsx     # Transcript + cumulative GPA (/api/sis/transcript/me)
│   ├── RegulationsPage.tsx    # "My Regulations" rule assignments (/api/regulations/*)
│   ├── ProfilePage.tsx        # Profile + status flags (/api/sis/profile/me)
│   ├── CatalogPage.tsx        # Course catalog browse
│   ├── NotificationsPage.tsx  # Notifications view
│   └── SettingsPage.tsx       # Settings
├── services/
│   └── api.ts                 # HTTP calls (see API Communication section)
└── locales/
    ├── en.json                # English translations
    └── tr.json                # Turkish translations
```

### Routes

All routes except `/login` are inside `ProtectedLayout`, which renders the `Sidebar` alongside the active page. **The default landing is `/dashboard`** (not `/chat`).

| Path | Component | Auth required |
|------|-----------|---------------|
| `/login` | `LoginPage` | No (redirects to `/dashboard` if already authenticated) |
| `/dashboard` | `DashboardPage` | Yes |
| `/chat` | `ChatPage` | Yes |
| `/calendar` | `CalendarPage` | Yes |
| `/schedule` | `SchedulePage` | Yes |
| `/courses` | `CoursesPage` | Yes |
| `/assignments` | `AssignmentsPage` | Yes |
| `/transcript` | `TranscriptPage` | Yes |
| `/regulations` | `RegulationsPage` | Yes |
| `/profile` | `ProfilePage` | Yes |
| `/catalog` | `CatalogPage` | Yes |
| `/notifications` | `NotificationsPage` | Yes |
| `/settings` | `SettingsPage` | Yes |
| `/*` | Redirects to `/dashboard` | Yes |

### Sidebar navigation

`components/Sidebar.tsx` groups links into three sections (note: `/catalog` and `/notifications` have routes but are not in the sidebar nav arrays):
- **Main:** `/dashboard`, `/chat`, `/calendar`
- **Student:** `/schedule`, `/courses`, `/assignments`, `/transcript`, `/regulations`
- **Bottom:** `/profile`, `/settings`

Labels come from i18n keys (`sidebar.*`); icons are from `lucide-react`.

---

## Auth Flow

The backend uses httpOnly cookies for JWT. The frontend cannot read these cookies (that's the point).

**The sentinel pattern (preserved from original):**
```typescript
// In LoginPage.tsx
token: res.access_token || 'cookie'
```

The string `'cookie'` is used as a flag meaning "we have an authenticated session via httpOnly cookie".
It is not a real token and is not sent in headers. All actual auth happens via the cookie, which is
sent automatically by the browser (`credentials: 'include'`).

Do not replace this with a real token stored in localStorage — that would be a security regression.

### AuthContext (`contexts/AuthContext.tsx`)

Auth state is managed via React Context, replacing the old `useState` in `App.tsx`:

- **`AuthUser` object** — stores `token` (sentinel), `userType`, `firstName`, `lastName`, `email`
- **Persisted to localStorage** as `orbis_user` (JSON object, not just a token string)
- **Legacy migration** — one-time migration from the old `token` localStorage key to the new format
- **Background token refresh** — a `setInterval` every 20 minutes calls `POST /api/auth/refresh` to keep the httpOnly cookie alive. On 401 response, the user is logged out automatically.
- **Chat history** — `chatHistory` state lives in AuthContext so it persists across page navigations (but not across browser refreshes)

### Global 401 handling

`api.ts` has a `handleUnauthorized()` helper that clears `orbis_user` from localStorage and redirects to `/login` on any 401 response. This is called from all API methods.

---

## Theming (`contexts/ThemeContext.tsx`)

A full theming system via CSS custom properties:
- **Dark/light mode** (affects `--bg-primary`, `--text-primary`, etc.)
- **Accent colors** (blue, green, purple, orange, coral)
- **Background presets** (solid, gradient, mesh)
- All theme values are applied to `document.documentElement.style` as CSS variables
- Theme preference is persisted to localStorage

---

## Internationalization (i18n)

- **i18next** initialized in `i18n.ts` with Turkish (`tr`) and English (`en`) resources
- Translation files in `web/src/locales/en.json` and `web/src/locales/tr.json`
- Language can be toggled from the `Sidebar` component
- Persisted to localStorage via i18next's `lng` detection

---

## API Communication (`web/src/services/api.ts`)

A single `api` object. All calls pass `credentials: 'include'` (httpOnly cookie auth) and route 401s
through `handleUnauthorized()` (clears `orbis_user`, redirects to `/login`). A shared `getJson()`
helper backs the simple GETs.

| Method | Verb · Endpoint | Notes |
|--------|-----------------|-------|
| `post(endpoint, data, token?)` | POST | Generic JSON POST (login, etc.) |
| `chatStream(message, token, onChunk)` | POST `/chat` | **Raw text** stream (not SSE) — see below |
| `getCalendar(academicYear?, appliesTo?)` | GET `/sis/calendar` | Academic calendar entries |
| `getMySchedule()` | GET `/sis/schedule/me` | Weekly schedule |
| `getDashboard()` | GET `/sis/dashboard` | Dashboard aggregate |
| `getProfile()` | GET `/sis/profile/me` | Profile + status flags |
| `getTranscript()` | GET `/sis/transcript/me` | Transcript + GPA |
| `getMyCourses()` | GET `/sis/courses/me` | Enrolled courses |
| `getMyAssignments()` | GET `/assignments/me` | Assignment list |
| `submitAssignment(id, file)` | POST `/assignments/{id}/submit` | Non-streaming submission check |
| `submitAssignmentStream(id, file, onEvent)` | POST `/assignments/{id}/submit/stream` | **SSE** — agent reasoning steps |
| `flagSubmissionRejection(submissionId, reason)` | POST `/assignments/submissions/{id}/flag` | Flag a rejection |
| `getMyRegulations()` | GET `/regulations/me` | Per-user rule assignments |
| `updateRegulationStatus(id, status)` | PATCH `/regulations/assignments/{id}` | Mark actioned/dismissed/active |

### Two different streaming formats — don't confuse them

- **`chatStream` reads raw text.** The backend `rag/service.py` yields plain LLM text chunks
  (not `data: {...}\n\n` SSE frames). Decode and append each chunk directly.
- **`submitAssignmentStream` reads SSE.** The submission endpoint emits proper
  `event: <type>\ndata: <json>\n\n` frames. `api.ts` buffers on the `\n\n` separator, parses
  `event:` / `data:` lines, and calls `onEvent(type, parsedData)` per frame.

```typescript
// chatStream — raw text
const reader = response.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  onChunk(decoder.decode(value, { stream: true }));
}
```

**Note:** the old `/api/regulations/ask` SSE endpoint was removed along with `regulation_service.py`.
The current `/api/regulations/*` routes are plain JSON (assignment listing + status update), unrelated
to the old streaming endpoint.

---

## Streaming Message Update Pattern (in ChatPage.tsx)

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

- Do not store real JWT tokens in localStorage — keep the httpOnly cookie approach
- Do not switch to `axios` — the streaming implementation relies on the native Fetch `ReadableStream` API
- Do not install a CSS framework without discussion — keep styles minimal with CSS custom properties
- Do not use Angular patterns in the frontend — use React hooks and context
