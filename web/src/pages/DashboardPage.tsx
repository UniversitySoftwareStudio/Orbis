import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  GraduationCap,
  BookOpen,
  ClipboardList,
  ShieldAlert,
  CalendarDays,
} from 'lucide-react';
import { api } from '../services/api';

interface Deadline {
  title: string;
  due_date: string;
  kind: string;
}

interface CalendarItem {
  title: string;
  start_date: string;
  entry_type: string;
}

interface DashboardData {
  first_name: string;
  is_student: boolean;
  stats: {
    gpa: number | null;
    total_credits_completed: number | null;
    total_credits_enrolled: number | null;
    enrolled_course_count: number;
    pending_assignment_count: number;
    active_regulation_count: number;
  };
  upcoming_deadlines: Deadline[];
  upcoming_calendar: CalendarItem[];
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card" style={{ padding: 18, flex: '1 1 140px', minWidth: 140 }}>
      <div style={{ fontSize: 28, fontWeight: 600, color: 'var(--accent)' }}>{value}</div>
      <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>{label}</div>
    </div>
  );
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const { t } = useTranslation();
  const navigate = useNavigate();

  useEffect(() => {
    api.getDashboard().then(d => {
      setData(d);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{t('dashboard.loading')}</div>;
  }
  if (!data) {
    return <div style={{ padding: 40, color: 'var(--text-secondary)' }}>{t('dashboard.empty')}</div>;
  }

  const quickLinks: Array<{ path: string; icon: typeof BookOpen; label: string }> = [
    { path: '/courses', icon: BookOpen, label: t('dashboard.links.courses') },
    { path: '/transcript', icon: GraduationCap, label: t('dashboard.links.transcript') },
    { path: '/assignments', icon: ClipboardList, label: t('dashboard.links.assignments') },
    { path: '/regulations', icon: ShieldAlert, label: t('dashboard.links.regulations') },
  ];

  return (
    <div style={{ padding: 32, maxWidth: 900, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 8, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <LayoutDashboard size={20} strokeWidth={1.8} />
        {t('dashboard.greeting', { name: data.first_name })}
      </h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>{t('dashboard.subtitle')}</p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 28 }}>
        <StatCard label={t('dashboard.stats.gpa')} value={data.stats.gpa ?? '—'} />
        <StatCard label={t('dashboard.stats.creditsCompleted')} value={data.stats.total_credits_completed ?? '—'} />
        <StatCard label={t('dashboard.stats.courses')} value={data.stats.enrolled_course_count} />
        <StatCard label={t('dashboard.stats.assignments')} value={data.stats.pending_assignment_count} />
        <StatCard label={t('dashboard.stats.regulations')} value={data.stats.active_regulation_count} />
      </div>

      <h3 style={{ marginBottom: 12, color: 'var(--accent)' }}>{t('dashboard.deadlines')}</h3>
      {data.upcoming_deadlines.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>{t('dashboard.noDeadlines')}</p>
      ) : (
        <div className="card" style={{ padding: 16, marginBottom: 28 }}>
          {data.upcoming_deadlines.map((d, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', padding: '8px 0',
              borderBottom: i < data.upcoming_deadlines.length - 1 ? '1px solid var(--border-color)' : 'none',
            }}>
              <span style={{ color: 'var(--text-primary)' }}>{d.title}</span>
              <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                {new Date(d.due_date).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}

      <h3 style={{ marginBottom: 12, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <CalendarDays size={16} strokeWidth={1.8} />
        {t('dashboard.calendar')}
      </h3>
      {data.upcoming_calendar.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>{t('dashboard.noCalendar')}</p>
      ) : (
        <div className="card" style={{ padding: 16, marginBottom: 28 }}>
          {data.upcoming_calendar.map((c, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', padding: '8px 0',
              borderBottom: i < data.upcoming_calendar.length - 1 ? '1px solid var(--border-color)' : 'none',
            }}>
              <span style={{ color: 'var(--text-primary)' }}>{c.title}</span>
              <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                {new Date(c.start_date).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}

      <h3 style={{ marginBottom: 12, color: 'var(--accent)' }}>{t('dashboard.quickLinks')}</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        {quickLinks.map(link => {
          const Icon = link.icon;
          return (
            <button
              key={link.path}
              className="btn"
              onClick={() => navigate(link.path)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '12px 18px',
                background: 'var(--bg-card)', color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
              }}
            >
              <Icon size={18} strokeWidth={1.8} />
              {link.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
