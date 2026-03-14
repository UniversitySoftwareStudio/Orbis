import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { LucideIcon } from 'lucide-react';
import {
  MessageSquare,
  CalendarDays,
  CalendarRange,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Palette,
  Globe,
  Sun,
  Moon,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme, ACCENT_PRESETS, BG_PRESETS_DARK, BG_PRESETS_LIGHT } from '../contexts/ThemeContext';

const NAV_ITEMS: Array<{ path: string; icon: LucideIcon; labelKey: string }> = [
  { path: '/chat',     icon: MessageSquare, labelKey: 'sidebar.chat'     },
  { path: '/calendar', icon: CalendarDays,  labelKey: 'sidebar.calendar' },
];

const STUDENT_ITEMS: Array<{ path: string; icon: LucideIcon; labelKey: string }> = [
  { path: '/schedule', icon: CalendarRange, labelKey: 'sidebar.schedule' },
];

const COLLAPSED_KEY = 'orbis_sidebar_collapsed';

export function Sidebar() {
  const { user, logout } = useAuth();
  const { colorScheme, accentId, bgPresetId, toggleColorScheme, setAccent, setBgPreset } = useTheme();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem(COLLAPSED_KEY) === 'true';
  });

  const [themeOpen, setThemeOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const paletteRef = useRef<HTMLButtonElement>(null);

  // Close theme panel when clicking outside
  useEffect(() => {
    if (!themeOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (
        panelRef.current && !panelRef.current.contains(e.target as Node) &&
        paletteRef.current && !paletteRef.current.contains(e.target as Node)
      ) {
        setThemeOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [themeOpen]);

  if (!user) return null;

  const allItems = user.userType === 'student'
    ? [...NAV_ITEMS, ...STUDENT_ITEMS]
    : NAV_ITEMS;

  const toggleCollapsed = () => {
    setCollapsed(prev => {
      const next = !prev;
      localStorage.setItem(COLLAPSED_KEY, String(next));
      return next;
    });
  };

  const toggleLanguage = () => {
    const newLang = i18n.language === 'tr' ? 'en' : 'tr';
    i18n.changeLanguage(newLang);
    localStorage.setItem('orbis_lang', newLang);
  };

  const width = collapsed ? 60 : 220;

  const bgPresets = colorScheme === 'dark' ? BG_PRESETS_DARK : BG_PRESETS_LIGHT;

  return (
    <>
      <nav style={{
        width,
        minWidth: 60,
        height: '100vh',
        backgroundColor: 'var(--sidebar-bg)',
        display: 'flex',
        flexDirection: 'column',
        padding: '20px 0',
        transition: 'width 0.25s ease',
        overflow: 'hidden',
        position: 'relative',
        zIndex: 100,
        flexShrink: 0,
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: collapsed ? 'center' : 'space-between',
          alignItems: 'center',
          padding: '0 16px 24px',
        }}>
          {!collapsed && (
            <span style={{ color: 'var(--sidebar-text)', fontSize: 18, fontWeight: 600 }}>
              {t('sidebar.appName')}
            </span>
          )}
          <button
            onClick={toggleCollapsed}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--sidebar-text)',
              cursor: 'pointer',
              padding: 4,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {collapsed
              ? <ChevronRight size={18} strokeWidth={1.8} />
              : <ChevronLeft  size={18} strokeWidth={1.8} />}
          </button>
        </div>

        {/* Nav items */}
        <div style={{ flex: 1 }}>
          {allItems.map(item => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                onMouseEnter={e => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'var(--accent-subtle)';
                    e.currentTarget.style.color = 'var(--accent)';
                    e.currentTarget.style.transform = 'translateX(3px)';
                  }
                }}
                onMouseLeave={e => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = '#b0b0c0';
                    e.currentTarget.style.transform = 'translateX(0)';
                  }
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  gap: collapsed ? 0 : 10,
                  width: '100%',
                  padding: collapsed ? '12px 0' : '12px 16px',
                  border: 'none',
                  background: isActive ? 'var(--accent-subtle)' : 'transparent',
                  color: isActive ? 'var(--accent)' : '#b0b0c0',
                  fontSize: 14,
                  cursor: 'pointer',
                  textAlign: 'left',
                  borderLeft: isActive ? '3px solid var(--accent)' : '3px solid transparent',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap',
                }}
              >
                <Icon size={18} strokeWidth={1.8} />
                {!collapsed && <span>{t(item.labelKey)}</span>}
              </button>
            );
          })}
        </div>

        {/* Bottom section */}
        <div style={{
          marginTop: 'auto',
          padding: collapsed ? '16px 8px' : '16px',
          borderTop: '1px solid var(--border-color)',
        }}>
          {/* User info */}
          {!collapsed && (
            <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 12, textAlign: 'center' }}>
              {user.firstName} {user.lastName}
            </div>
          )}

          {/* Bottom controls: language, palette, logout */}
          <div style={{
            display: 'flex',
            flexDirection: collapsed ? 'column' : 'row',
            gap: 4,
            alignItems: 'center',
          }}>
            {/* Language toggle */}
            <button
              className="btn btn-ghost"
              onClick={toggleLanguage}
              title={i18n.language === 'tr' ? 'Switch to English' : "Türkçe'ye geç"}
              style={{
                flex: collapsed ? 'unset' : '1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 4,
                padding: '8px 6px',
              }}
            >
              <Globe size={18} strokeWidth={1.8} />
              {!collapsed && <span style={{ fontSize: 12 }}>{i18n.language === 'tr' ? 'EN' : 'TR'}</span>}
            </button>

            {/* Palette button — always icon-only */}
            <button
              ref={paletteRef}
              className="btn btn-ghost"
              onClick={() => setThemeOpen(o => !o)}
              title={t('theme.customize')}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '8px 6px',
                color: themeOpen ? 'var(--accent)' : undefined,
                background: themeOpen ? 'var(--accent-subtle)' : undefined,
              }}
            >
              <Palette size={18} strokeWidth={1.8} />
            </button>

            {/* Logout */}
            <button
              className="btn btn-ghost"
              onClick={() => { logout(); navigate('/login'); }}
              title={t('sidebar.logout')}
              style={{
                flex: collapsed ? 'unset' : '1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 4,
                padding: '8px 6px',
              }}
            >
              <LogOut size={18} strokeWidth={1.8} />
              {!collapsed && <span style={{ fontSize: 12 }}>{t('sidebar.logout')}</span>}
            </button>
          </div>
        </div>
      </nav>

      {/* Floating theme panel */}
      {themeOpen && (
        <div
          ref={panelRef}
          style={{
            position: 'fixed',
            left: collapsed ? 60 : 220,
            bottom: 60,
            width: 280,
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: 12,
            boxShadow: 'var(--shadow)',
            padding: 20,
            zIndex: 1000,
            transition: 'left 0.25s ease',
          }}
        >
          {/* Section 1: Color Scheme */}
          <div style={{ marginBottom: 16 }}>
            <div style={{
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              marginBottom: 10,
            }}>
              {t('theme.colorScheme')}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => { if (colorScheme !== 'light') toggleColorScheme(); }}
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  padding: 10,
                  borderRadius: 8,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: colorScheme === 'light' ? 'var(--accent)' : 'var(--bg-tertiary)',
                  color: colorScheme === 'light' ? 'white' : 'var(--text-secondary)',
                  fontSize: 13,
                  transition: 'all 0.15s ease',
                }}
              >
                <Sun size={16} strokeWidth={1.8} />
                {t('theme.light')}
              </button>
              <button
                onClick={() => { if (colorScheme !== 'dark') toggleColorScheme(); }}
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  padding: 10,
                  borderRadius: 8,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: colorScheme === 'dark' ? 'var(--accent)' : 'var(--bg-tertiary)',
                  color: colorScheme === 'dark' ? 'white' : 'var(--text-secondary)',
                  fontSize: 13,
                  transition: 'all 0.15s ease',
                }}
              >
                <Moon size={16} strokeWidth={1.8} />
                {t('theme.dark')}
              </button>
            </div>
          </div>

          <div style={{ height: 1, backgroundColor: 'var(--border-color)', marginBottom: 16 }} />

          {/* Section 2: Background */}
          <div style={{ marginBottom: 16 }}>
            <div style={{
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              marginBottom: 10,
            }}>
              {t('theme.background')}
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              {bgPresets.map(preset => (
                <div key={preset.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <button
                    onClick={() => setBgPreset(preset.id)}
                    title={preset.label}
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: '50%',
                      backgroundColor: preset.bg,
                      border: '2px solid var(--border-color)',
                      cursor: 'pointer',
                      outline: bgPresetId === preset.id ? '2px solid var(--accent)' : 'none',
                      outlineOffset: 2,
                      transition: 'transform 0.15s ease',
                      padding: 0,
                    }}
                    onMouseEnter={e => { e.currentTarget.style.transform = 'scale(1.15)'; }}
                    onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)'; }}
                  />
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{preset.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ height: 1, backgroundColor: 'var(--border-color)', marginBottom: 16 }} />

          {/* Section 3: Accent Color */}
          <div>
            <div style={{
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              marginBottom: 10,
            }}>
              {t('theme.accentColor')}
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              {ACCENT_PRESETS.map(preset => (
                <div key={preset.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <button
                    onClick={() => setAccent(preset.id)}
                    title={preset.label}
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: '50%',
                      backgroundColor: preset.value,
                      border: 'none',
                      cursor: 'pointer',
                      outline: accentId === preset.id ? '2px solid white' : 'none',
                      outlineOffset: accentId === preset.id ? 2 : 0,
                      transition: 'transform 0.15s ease',
                      padding: 0,
                    }}
                    onMouseEnter={e => { e.currentTarget.style.transform = 'scale(1.15)'; }}
                    onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)'; }}
                  />
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{preset.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
