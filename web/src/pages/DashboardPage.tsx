import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  GraduationCap,
  BookOpen,
  ClipboardList,
  ShieldAlert,
  CalendarDays,
  ArrowUpRight,
  Search,
  BellRing,
  FileCheck2,
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

// Compact secondary stat — small, dense, sits in the bento sidebar.
function MiniStat({ label, value, icon: Icon }: { label: string; value: string | number; icon: typeof BookOpen }) {
  return (
    <div className="card card-hover" style={{
      padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 13, cursor: 'default',
    }}>
      <div style={{
        width: 38, height: 38, borderRadius: 10, flexShrink: 0,
        background: 'var(--accent-subtle)', color: 'var(--accent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={18} strokeWidth={1.9} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', lineHeight: 1.1, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
        <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</div>
      </div>
    </div>
  );
}

// The hero element: one of Orbis's three core paths (Pull / Push / Review),
// color-coded to the project schema. This is what the demo must read instantly.
function PathCard({ accent, icon: Icon, tag, title, desc, metric, onClick }: {
  accent: string; icon: typeof BookOpen; tag: string; title: string; desc: string; metric: string; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="card card-hover"
      style={{
        position: 'relative', overflow: 'hidden', cursor: 'pointer', textAlign: 'left',
        padding: '22px 22px 20px', display: 'flex', flexDirection: 'column', gap: 0,
        background: `linear-gradient(165deg, color-mix(in srgb, ${accent} 14%, var(--bg-card)), var(--bg-card) 55%)`,
        border: `1px solid color-mix(in srgb, ${accent} 30%, var(--border-color))`,
        minHeight: 168,
      }}
    >
      {/* glow */}
      <div style={{ position: 'absolute', top: -50, right: -50, width: 150, height: 150, borderRadius: '50%', background: `radial-gradient(circle, color-mix(in srgb, ${accent} 35%, transparent), transparent 70%)`, pointerEvents: 'none' }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative' }}>
        <div style={{ width: 42, height: 42, borderRadius: 12, background: accent, color: '#0a0a0c', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: `0 6px 18px -4px ${accent}` }}>
          <Icon size={21} strokeWidth={2.1} />
        </div>
        <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: accent, border: `1px solid color-mix(in srgb, ${accent} 40%, transparent)`, padding: '3px 9px', borderRadius: 99 }}>{tag}</span>
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginTop: 16, position: 'relative' }}>{title}</div>
      <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6, lineHeight: 1.5, position: 'relative' }}>{desc}</div>
      <div style={{ marginTop: 'auto', paddingTop: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative' }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: accent }}>{metric}</span>
        <ArrowUpRight size={17} style={{ color: accent }} />
      </div>
    </button>
  );
}

// Days-until helper for urgency coloring on deadlines.
function daysUntil(dateStr: string): number {
  const d = new Date(dateStr).getTime();
  return Math.ceil((d - Date.now()) / 86400000);
}
function urgencyDot(days: number): string {
  if (days <= 3) return 'var(--danger)';
  if (days <= 10) return 'var(--warning)';
  return 'var(--success)';
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

  const gpa = data.stats.gpa;
  const gpaPct = gpa != null ? Math.min(100, (Number(gpa) / 4) * 100) : 0;

  return (
    <div style={{ padding: '28px 40px 56px', maxWidth: 1440, margin: '0 auto' }}>
      {/* Hero — single compact line so the 3 paths sit above the fold */}
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 18 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
          {t('dashboard.greeting', { name: data.first_name })}
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>{t('dashboard.subtitle')}</p>
      </div>

      {/* THE THESIS: Orbis's three differentiated paths — Pull, Push, Review. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 16 }}>
        <PathCard
          accent="var(--path-pull)"
          icon={Search}
          tag={t('dashboard.paths.pullTag')}
          title={t('dashboard.paths.pullTitle')}
          desc={t('dashboard.paths.pullDesc')}
          metric={t('dashboard.paths.pullMetric')}
          onClick={() => window.dispatchEvent(new Event('orbis:open-chat'))}
        />
        <PathCard
          accent="var(--path-push)"
          icon={BellRing}
          tag={t('dashboard.paths.pushTag')}
          title={t('dashboard.paths.pushTitle')}
          desc={t('dashboard.paths.pushDesc')}
          metric={t('dashboard.paths.pushMetric', { n: data.stats.active_regulation_count })}
          onClick={() => navigate('/regulations')}
        />
        <PathCard
          accent="var(--path-review)"
          icon={FileCheck2}
          tag={t('dashboard.paths.reviewTag')}
          title={t('dashboard.paths.reviewTitle')}
          desc={t('dashboard.paths.reviewDesc')}
          metric={t('dashboard.paths.reviewMetric', { n: data.stats.pending_assignment_count })}
          onClick={() => navigate('/assignments')}
        />
      </div>

      {/* Bento grid: hero GPA + mini stats, then deadlines (wide) + calendar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 16 }}>

        {/* Featured GPA card — the focal point */}
        <div className="card" style={{
          gridColumn: 'span 4', padding: 24, position: 'relative', overflow: 'hidden',
          background: 'linear-gradient(160deg, color-mix(in srgb, var(--accent) 16%, var(--bg-card)), var(--bg-card) 60%)',
          boxShadow: 'var(--shadow-lg)',
        }}>
          <div style={{ position: 'absolute', top: -40, right: -40, width: 160, height: 160, borderRadius: '50%', background: 'radial-gradient(circle, color-mix(in srgb, var(--accent) 30%, transparent), transparent 70%)', filter: 'blur(8px)' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, fontWeight: 500, color: 'var(--text-secondary)', position: 'relative' }}>
            <GraduationCap size={16} strokeWidth={2} style={{ color: 'var(--accent)' }} />
            {t('dashboard.stats.gpa')}
          </div>
          <div style={{ fontSize: 52, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.04em', lineHeight: 1, marginTop: 14, fontVariantNumeric: 'tabular-nums', position: 'relative' }}>
            {gpa ?? '—'}<span style={{ fontSize: 20, color: 'var(--text-muted)', fontWeight: 600 }}> / 4.0</span>
          </div>
          {/* progress bar */}
          <div style={{ marginTop: 18, height: 6, borderRadius: 99, background: 'var(--bg-tertiary)', overflow: 'hidden', position: 'relative' }}>
            <div style={{ width: `${gpaPct}%`, height: '100%', borderRadius: 99, background: 'var(--accent)', transition: 'width 0.6s var(--ease)' }} />
          </div>
          <div style={{ marginTop: 16, display: 'flex', gap: 20, position: 'relative' }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{data.stats.total_credits_completed ?? '—'}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t('dashboard.stats.creditsCompleted')}</div>
            </div>
          </div>
        </div>

        {/* Mini stats column */}
        <div style={{ gridColumn: 'span 8', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, alignContent: 'start' }}>
          <MiniStat icon={BookOpen} label={t('dashboard.stats.courses')} value={data.stats.enrolled_course_count} />
          <MiniStat icon={ClipboardList} label={t('dashboard.stats.assignments')} value={data.stats.pending_assignment_count} />
          <MiniStat icon={ShieldAlert} label={t('dashboard.stats.regulations')} value={data.stats.active_regulation_count} />
          {/* Quick "go to chat" CTA fills the 4th cell */}
          <button onClick={() => window.dispatchEvent(new Event('orbis:open-chat'))} className="card card-hover" style={{
            padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 13, cursor: 'pointer', textAlign: 'left',
            border: '1px solid var(--accent)', background: 'var(--accent-subtle)',
          }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, flexShrink: 0, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ArrowUpRight size={18} strokeWidth={2.2} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14.5, fontWeight: 600, color: 'var(--text-primary)' }}>{t('sidebar.chat')}</div>
              <div style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>{t('dashboard.askAnything')}</div>
            </div>
          </button>
        </div>

        {/* Deadlines — dominant card */}
        <div className="card" style={{ gridColumn: 'span 7', padding: 0, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 22px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <ClipboardList size={17} strokeWidth={2} style={{ color: 'var(--accent)' }} />
              <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{t('dashboard.deadlines')}</span>
            </div>
            <button onClick={() => navigate('/assignments')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12.5, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
              {t('dashboard.links.assignments')} <ArrowUpRight size={13} />
            </button>
          </div>
          {data.upcoming_deadlines.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', padding: '8px 22px 24px', fontSize: 14 }}>{t('dashboard.noDeadlines')}</p>
          ) : (
            <div>
              {data.upcoming_deadlines.slice(0, 6).map((d, i, arr) => {
                const days = daysUntil(d.due_date);
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 13, padding: '13px 22px',
                    borderTop: '1px solid var(--border-color)',
                    background: i === 0 && arr.length ? 'transparent' : 'transparent',
                  }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: urgencyDot(days), boxShadow: `0 0 8px ${urgencyDot(days)}` }} />
                    <span style={{ flex: 1, color: 'var(--text-primary)', fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.title}</span>
                    <span style={{ fontSize: 12.5, fontWeight: 600, color: days <= 3 ? 'var(--danger)' : 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>
                      {days <= 0 ? t('dashboard.dueToday') : days === 1 ? t('dashboard.dueTomorrow') : t('dashboard.inDays', { n: days })}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Calendar — compact card */}
        <div className="card" style={{ gridColumn: 'span 5', padding: 0, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '18px 22px 14px' }}>
            <CalendarDays size={17} strokeWidth={2} style={{ color: 'var(--accent)' }} />
            <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{t('dashboard.calendar')}</span>
          </div>
          {data.upcoming_calendar.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', padding: '8px 22px 24px', fontSize: 14 }}>{t('dashboard.noCalendar')}</p>
          ) : (
            <div>
              {data.upcoming_calendar.slice(0, 6).map((c, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '12px 22px', borderTop: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, width: 38 }}>
                    <span style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{new Date(c.start_date).getDate()}</span>
                    <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{new Date(c.start_date).toLocaleDateString(undefined, { month: 'short' })}</span>
                  </div>
                  <span style={{ flex: 1, color: 'var(--text-secondary)', fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</span>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>

      {/* Quick links */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 16 }}>
        {quickLinks.map(link => {
          const Icon = link.icon;
          return (
            <button
              key={link.path}
              onClick={() => navigate(link.path)}
              className="card card-hover"
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px',
                color: 'var(--text-secondary)', fontSize: 13.5, fontWeight: 500, cursor: 'pointer',
              }}
            >
              <Icon size={16} strokeWidth={1.9} style={{ color: 'var(--accent)' }} />
              {link.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
