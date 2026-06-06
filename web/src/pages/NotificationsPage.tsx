import { useTranslation } from 'react-i18next';
import { Bell } from 'lucide-react';

// Tier B scaffold — unified notifications feed.
// TODO: wire to GET /api/notifications/me (to be added in a follow-up),
// synthesized read-only from assignments + rule assignments + calendar.
export function NotificationsPage() {
  const { t } = useTranslation();
  return (
    <div style={{ padding: 32, maxWidth: 900, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 24, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Bell size={20} strokeWidth={1.8} />
        {t('notifications.title')}
      </h2>
      <p style={{ color: 'var(--text-secondary)' }}>{t('common.comingSoon')}</p>
    </div>
  );
}
