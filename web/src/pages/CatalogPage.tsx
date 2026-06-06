import { useTranslation } from 'react-i18next';
import { Library } from 'lucide-react';

// Tier B scaffold — course catalog / search.
// TODO: wire to GET /api/courses + GET /api/courses/{code} (backend endpoints
// to be added in a follow-up), or reuse the existing GET /api/search semantic
// course search for the search box.
export function CatalogPage() {
  const { t } = useTranslation();
  return (
    <div style={{ padding: 32, maxWidth: 900, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 24, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Library size={20} strokeWidth={1.8} />
        {t('catalog.title')}
      </h2>
      <p style={{ color: 'var(--text-secondary)' }}>{t('common.comingSoon')}</p>
    </div>
  );
}
