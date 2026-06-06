# `web/src/components/`

Reusable UI components.

Current core component:

- `Sidebar.tsx`: authenticated app navigation, language toggle, theme controls,
  logout, and student-only nav items.

Keep page-specific layout inside `pages/` unless multiple screens share it.
Prefer lucide-react icons for controls so the UI stays consistent.
