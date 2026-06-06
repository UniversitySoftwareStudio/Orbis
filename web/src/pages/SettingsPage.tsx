import { useTranslation } from 'react-i18next';
import { Settings as SettingsIcon } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

// Tier B scaffold — settings / preferences. Theme + language already live in the
// Sidebar; this page surfaces them in one place. Account actions (change password)
// are deferred until a backend endpoint exists.
export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const { colorScheme, toggleColorScheme } = useTheme();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'tr' ? 'en' : 'tr';
    i18n.changeLanguage(newLang);
    localStorage.setItem('orbis_lang', newLang);
  };

  return (
    <div style={{ padding: 32, maxWidth: 720, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 24, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <SettingsIcon size={20} strokeWidth={1.8} />
        {t('settings.title')}
      </h2>

      <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: 'var(--text-primary)' }}>{t('settings.colorScheme')}</span>
          <button className="btn btn-ghost" onClick={toggleColorScheme}>
            {colorScheme === 'dark' ? t('theme.dark') : t('theme.light')}
          </button>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: 'var(--text-primary)' }}>{t('settings.language')}</span>
          <button className="btn btn-ghost" onClick={toggleLanguage}>
            {i18n.language === 'tr' ? 'Türkçe' : 'English'}
          </button>
        </div>
      </div>
    </div>
  );
}
