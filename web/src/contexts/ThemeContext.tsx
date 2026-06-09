import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

export const ACCENT_PRESETS = [
  { id: 'blue',   label: 'Ocean',    value: '#4fc3f7' },
  { id: 'purple', label: 'Violet',   value: '#ce93d8' },
  { id: 'green',  label: 'Forest',   value: '#81c784' },
  { id: 'orange', label: 'Sunset',   value: '#ffb74d' },
  { id: 'rose',   label: 'Rose',     value: '#f48fb1' },
];

export const BG_PRESETS_DARK = [
  // Canvas is the darkest layer; cards sit ABOVE it so they lift off the page.
  { id: 'dark-default', label: 'Onyx',     bg: '#0a0a0c', secondary: '#101013', tertiary: '#1a1a1f', card: '#141417' },
  { id: 'dark-slate',   label: 'Slate',    bg: '#0a0c10', secondary: '#101319', tertiary: '#1c2230', card: '#141821' },
  { id: 'dark-warm',    label: 'Espresso', bg: '#0c0a08', secondary: '#14100d', tertiary: '#241d14', card: '#181410' },
  { id: 'dark-forest',  label: 'Forest',   bg: '#08100b', secondary: '#0d1711', tertiary: '#16261c', card: '#111c15' },
];

export const BG_PRESETS_LIGHT = [
  { id: 'light-default', label: 'Cloud',  bg: '#f5f5f5', secondary: '#ffffff', tertiary: '#e8e8e8', card: '#ffffff' },
  { id: 'light-warm',    label: 'Cream',  bg: '#faf6f0', secondary: '#ffffff', tertiary: '#f0e8da', card: '#fffdf8' },
  { id: 'light-cool',    label: 'Frost',  bg: '#f0f4f8', secondary: '#ffffff', tertiary: '#e2eaf2', card: '#ffffff' },
  { id: 'light-gray',    label: 'Ash',    bg: '#ececec', secondary: '#f8f8f8', tertiary: '#dcdcdc', card: '#f8f8f8' },
];

type BgPreset = typeof BG_PRESETS_DARK[number];

function findBgPreset(id: string): BgPreset | undefined {
  return [...BG_PRESETS_DARK, ...BG_PRESETS_LIGHT].find(p => p.id === id);
}

interface ThemeContextType {
  colorScheme: 'dark' | 'light';
  accentId: string;
  accentColor: string;
  bgPresetId: string;
  toggleColorScheme: () => void;
  setAccent: (id: string) => void;
  setBgPreset: (id: string) => void;
}

const ThemeContext = createContext<ThemeContextType | null>(null);

const SCHEME_KEY = 'orbis_scheme';
const ACCENT_KEY = 'orbis_accent';
const BG_PRESET_KEY = 'orbis_bg_preset';

function getAccentValue(id: string): string {
  return ACCENT_PRESETS.find(p => p.id === id)?.value ?? ACCENT_PRESETS[0].value;
}

function applyTheme(scheme: string, accent: string, bgPreset?: BgPreset) {
  const root = document.documentElement;
  const isDark = scheme === 'dark';

  // Light mode (Linear/Notion-style): cooler gray canvas, white cards that lift,
  // a distinct off-white sidebar, and crisp hairline borders.
  root.style.setProperty('--bg-primary',     bgPreset?.bg        ?? (isDark ? '#0a0a0c' : '#f4f5f7'));
  root.style.setProperty('--bg-secondary',   bgPreset?.secondary ?? (isDark ? '#101013' : '#ffffff'));
  root.style.setProperty('--bg-tertiary',    bgPreset?.tertiary  ?? (isDark ? '#1a1a1f' : '#eceef1'));
  root.style.setProperty('--bg-card',        bgPreset?.card      ?? (isDark ? '#141417' : '#ffffff'));
  root.style.setProperty('--border-color',   isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.09)');
  root.style.setProperty('--border-strong',  isDark ? 'rgba(255,255,255,0.14)' : 'rgba(15,23,42,0.16)');
  root.style.setProperty('--text-primary',   isDark ? '#f4f4f6' : '#0f172a');
  root.style.setProperty('--text-secondary', isDark ? '#9b9ba6' : '#5b6472');
  root.style.setProperty('--text-muted',     isDark ? '#5f5f6b' : '#94a0b0');
  root.style.setProperty('--bg-table-header', isDark ? '#16161a' : '#f1f3f6');
  // Sidebar: a distinct surface so it separates from the content area.
  root.style.setProperty('--sidebar-bg',     bgPreset?.secondary ?? (isDark ? '#0d0d10' : '#fbfbfc'));
  root.style.setProperty('--sidebar-text',   isDark ? '#f4f4f6' : '#0f172a');
  root.style.setProperty('--accent',         accent);
  root.style.setProperty('--accent-hover',   accent + 'cc');
  root.style.setProperty('--accent-subtle',  accent + (isDark ? '1f' : '1a'));
  root.style.setProperty('--shadow',         isDark
    ? '0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 28px -8px rgba(0,0,0,0.7)'
    : '0 1px 2px rgba(15,23,42,0.04), 0 4px 12px -2px rgba(15,23,42,0.08), 0 12px 24px -8px rgba(15,23,42,0.06)');
  root.style.setProperty('--shadow-lg',      isDark
    ? '0 1px 0 rgba(255,255,255,0.05) inset, 0 24px 60px -16px rgba(0,0,0,0.85)'
    : '0 2px 4px rgba(15,23,42,0.04), 0 16px 40px -12px rgba(15,23,42,0.18)');
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [colorScheme, setColorScheme] = useState<'dark' | 'light'>(() => {
    const stored = localStorage.getItem(SCHEME_KEY);
    return (stored === 'light' || stored === 'dark') ? stored : 'dark';
  });

  const [accentId, setAccentId] = useState<string>(() => {
    const stored = localStorage.getItem(ACCENT_KEY);
    return ACCENT_PRESETS.some(p => p.id === stored) ? stored! : 'blue';
  });

  const [bgPresetId, setBgPresetId] = useState<string>(() => {
    return localStorage.getItem(BG_PRESET_KEY) ?? '';
  });

  const accentColor = getAccentValue(accentId);

  useEffect(() => {
    const preset = findBgPreset(bgPresetId);
    applyTheme(colorScheme, accentColor, preset);
  }, [colorScheme, accentColor, bgPresetId]);

  const toggleColorScheme = () => {
    setColorScheme(prev => {
      const next = prev === 'dark' ? 'light' : 'dark';
      localStorage.setItem(SCHEME_KEY, next);
      return next;
    });
    // Clear bg preset so defaults apply for the new scheme
    setBgPresetId('');
    localStorage.removeItem(BG_PRESET_KEY);
  };

  const setAccent = (id: string) => {
    if (ACCENT_PRESETS.some(p => p.id === id)) {
      setAccentId(id);
      localStorage.setItem(ACCENT_KEY, id);
    }
  };

  const setBgPreset = (id: string) => {
    const preset = findBgPreset(id);
    if (!preset) return;
    setBgPresetId(id);
    localStorage.setItem(BG_PRESET_KEY, id);
    // Selecting a dark preset switches to dark mode, light preset → light mode
    const presetScheme: 'dark' | 'light' = id.startsWith('dark-') ? 'dark' : 'light';
    if (colorScheme !== presetScheme) {
      setColorScheme(presetScheme);
      localStorage.setItem(SCHEME_KEY, presetScheme);
    }
  };

  return (
    <ThemeContext.Provider value={{ colorScheme, accentId, accentColor, bgPresetId, toggleColorScheme, setAccent, setBgPreset }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextType {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
