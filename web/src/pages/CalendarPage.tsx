import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { CalendarDays } from 'lucide-react';
import { api } from '../services/api';
import { PageHeader } from '../components/PageHeader';

interface CalendarEntry {
  id: number;
  title_tr: string;
  title_en?: string;
  entry_type: string;
  start_date: string;
  end_date: string | null;
}

function formatDate(dateStr: string, months: string[]): string {
  const [, m, d] = dateStr.split('-');
  return `${parseInt(d)} ${months[parseInt(m) - 1]}`;
}

function formatRange(start: string, end: string | null, months: string[]): string {
  if (!end || end === start) return formatDate(start, months);
  return `${formatDate(start, months)} – ${formatDate(end, months)}`;
}

// Tinted (not solid) badges so they read on the dark canvas and share one palette.
function getTypeBadgeStyle(entryType: string): { background: string; color: string } {
  const tint = (c: string) => ({ background: `color-mix(in srgb, ${c} 16%, transparent)`, color: c });
  switch (entryType) {
    case 'holiday': return tint('var(--danger)');
    case 'exam_period': return tint('var(--warning)');
    case 'registration':
    case 'add_drop': return tint('var(--info)');
    case 'semester_start':
    case 'semester_end': return tint('var(--success)');
    default: return tint('var(--text-muted)');
  }
}

function getSemester(startDate: string): 'fall' | 'spring' {
  const month = parseInt(startDate.split('-')[1]);
  return (month >= 9 || month <= 1) ? 'fall' : 'spring';
}

export function CalendarPage() {
  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const { t, i18n } = useTranslation();

  useEffect(() => {
    api.getCalendar().then(data => {
      setEntries(data);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{t('calendar.loading')}</div>;
  }

  const fall = entries.filter(e => getSemester(e.start_date) === 'fall');
  const spring = entries.filter(e => getSemester(e.start_date) === 'spring');

  const getEventTitle = (entry: CalendarEntry) => {
    return i18n.language === 'tr' ? entry.title_tr : (entry.title_en ?? entry.title_tr);
  };

  const months = t('calendar.months', { returnObjects: true }) as string[];

  const getEntryTypeLabel = (entryType: string) => {
    const key = `calendar.entryTypes.${entryType}`;
    const translated = t(key);
    return translated === key ? t('calendar.entryTypes.other') : translated;
  };

  const renderTable = (items: CalendarEntry[]) => (
    <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 32, background: 'var(--bg-card)', borderRadius: 8, overflow: 'hidden' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', backgroundColor: 'var(--bg-table-header)' }}>
          <th style={{ padding: '8px 12px', color: 'var(--sidebar-text)' }}>{t('calendar.date')}</th>
          <th style={{ padding: '8px 12px', color: 'var(--sidebar-text)' }}>{t('calendar.event')}</th>
          <th style={{ padding: '8px 12px', color: 'var(--sidebar-text)' }}>{t('calendar.type')}</th>
        </tr>
      </thead>
      <tbody>
        {items.map(entry => {
          const badge = getTypeBadgeStyle(entry.entry_type);
          return (
            <tr
              key={entry.id}
              className="hoverable"
              style={{ borderBottom: '1px solid var(--border-color)' }}
            >
              <td style={{ padding: '10px 12px', whiteSpace: 'nowrap', fontSize: 14, color: 'var(--text-primary)' }}>
                {formatRange(entry.start_date, entry.end_date, months)}
              </td>
              <td style={{ padding: '10px 12px', fontSize: 14, color: 'var(--text-primary)' }}>{getEventTitle(entry)}</td>
              <td style={{ padding: '10px 12px' }}>
                <span style={{
                  display: 'inline-block',
                  padding: '2px 10px',
                  borderRadius: 12,
                  fontSize: 12,
                  fontWeight: 500,
                  background: badge.background,
                  color: badge.color,
                }}>
                  {getEntryTypeLabel(entry.entry_type)}
                </span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );

  return (
    <div style={{ padding: '32px 48px 64px', maxWidth: 1280, margin: '0 auto' }}>
      <PageHeader icon={CalendarDays} eyebrow={t('sidebar.calendar')} title={t('calendar.title')} />

      {entries.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>{t('calendar.empty')}</p>
      ) : (
        <>
          {fall.length > 0 && (
            <>
              <h3 style={{ marginBottom: 12, color: 'var(--accent)' }}>{t('calendar.fall')}</h3>
              {renderTable(fall)}
            </>
          )}
          {spring.length > 0 && (
            <>
              <h3 style={{ marginBottom: 12, color: 'var(--accent)' }}>{t('calendar.spring')}</h3>
              {renderTable(spring)}
            </>
          )}
        </>
      )}
    </div>
  );
}
