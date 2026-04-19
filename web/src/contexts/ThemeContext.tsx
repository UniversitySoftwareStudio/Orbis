import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

export const ACCENT_PRESETS = [
  { id: 'blue',   label: 'Ocean',    value: '#4fc3f7' },
  { id: 'purple', label: 'Violet',   value: '#ce93d8' },
  { id: 'green',  label: 'Forest',   value: '#81c784' },
  { id: 'orange', label: 'Sunset',   value: '#ffb74d' },
  { id: 'rose',   label: 'Rose',     value: '#f48fb1' },
];

export const BG_PRESETS_DARK = [
  { id: 'dark-default', label: 'Midnight', bg: '#0f0f1a', secondary: '#1a1a2e', tertiary: '#16213e', card: '#1e2a45' },
  { id: 'dark-slate',   label: 'Slate',    bg: '#0d1117', secondary: '#161b22', tertiary: '#21262d', card: '#1c2128' },
  { id: 'dark-warm',    label: 'Espresso', bg: '#1a1208', secondary: '#2d2010', tertiary: '#3d2e18', card: '#2a1f0e' },
  { id: 'dark-forest',  label: 'Forest',   bg: '#0a1a0f', secondary: '#122318', tertiary: '#1a3022', card: '#162b1e' },
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

  root.style.setProperty('--bg-primary',     bgPreset?.bg        ?? (isDark ? '#0f0f1a' : '#f5f5f5'));
  root.style.setProperty('--bg-secondary',   bgPreset?.secondary ?? (isDark ? '#1a1a2e' : '#ffffff'));
  root.style.setProperty('--bg-tertiary',    bgPreset?.tertiary  ?? (isDark ? '#16213e' : '#e8e8e8'));
  root.style.setProperty('--bg-card',        bgPreset?.card      ?? (isDark ? '#1e2a45' : '#ffffff'));
  root.style.setProperty('--border-color',   isDark ? '#2d3561' : '#d0d0d0');
  root.style.setProperty('--text-primary',   isDark ? '#e8e8f0' : '#1a1a2e');
  root.style.setProperty('--text-secondary', isDark ? '#a0a0b8' : '#555555');
  root.style.setProperty('--text-muted',     isDark ? '#606080' : '#888888');
  root.style.setProperty('--bg-table-header', '#1a1a2e');
  root.style.setProperty('--sidebar-bg',     '#1a1a2e');
  root.style.setProperty('--sidebar-text',   '#e8e8f0');
  root.style.setProperty('--accent',         accent);
  root.style.setProperty('--accent-hover',   accent + 'cc');
  root.style.setProperty('--accent-subtle',  accent + '22');
  root.style.setProperty('--shadow',         isDark
    ? '0 4px 20px rgba(0,0,0,0.4)'
    : '0 4px 20px rgba(0,0,0,0.12)');
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
