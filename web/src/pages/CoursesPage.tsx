import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BookOpen, MapPin, User as UserIcon } from 'lucide-react';
import { api } from '../services/api';
import { PageHeader, PageWrap } from '../components/PageHeader';

interface Slot {
  day_of_week: string | null;
  start_time: string | null;
  end_time: string | null;
  location: string | null;
  is_online: boolean | null;
}

interface EnrolledCourse {
  course_code: string;
  course_name: string;
  section_number: string;
  section_type: string;
  instructor_name: string | null;
  status: string;
  slots: Slot[];
}

function fmtTime(t: string | null): string {
  if (!t) return '';
  return t.slice(0, 5);
}

// Deterministic department color so each course code reads distinctly but stays on-palette.
const DEPT_TONES = ['var(--path-pull)', 'var(--path-push)', 'var(--path-review)', '#a78bfa', '#22c55e', '#f472b6'];
function deptColor(dept: string): string {
  let h = 0;
  for (let i = 0; i < dept.length; i++) h = (h * 31 + dept.charCodeAt(i)) >>> 0;
  return DEPT_TONES[h % DEPT_TONES.length];
}

export function CoursesPage() {
  const [courses, setCourses] = useState<EnrolledCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const { t } = useTranslation();

  useEffect(() => {
    api.getMyCourses().then(d => {
      setCourses(d ?? []);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{t('courses.loading')}</div>;
  }

  const dayLabel = (day: string | null) => (day ? t(`courses.days.${day}`, day) : '');

  return (
    <PageWrap>
      <PageHeader
        icon={BookOpen}
        eyebrow={t('sidebar.courses')}
        title={t('courses.title')}
        subtitle={t('courses.count', { count: courses.length })}
      />

      {courses.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>{t('courses.empty')}</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 16 }}>
          {courses.map((c, i) => {
            const dept = c.course_code.split(/[\s\d]/)[0] || c.course_code.slice(0, 4);
            const tone = deptColor(dept);
            return (
            <div key={i} className="card card-hover" style={{ padding: 0, overflow: 'hidden', display: 'flex' }}>
              {/* Colored code rail */}
              <div style={{
                width: 76, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                gap: 2, padding: '0 8px',
                background: `linear-gradient(160deg, color-mix(in srgb, ${tone} 24%, var(--bg-card)), var(--bg-card))`,
                borderRight: `1px solid color-mix(in srgb, ${tone} 30%, var(--border-color))`,
              }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: tone, letterSpacing: '0.02em' }}>{dept}</span>
                <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>{c.course_code.replace(/\D/g, '') || '—'}</span>
              </div>

              {/* Body */}
              <div style={{ flex: 1, minWidth: 0, padding: '16px 18px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.3 }}>{c.course_name}</div>
                    <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 3 }}>
                      {t('courses.section')} {c.section_number} · {c.section_type}
                    </div>
                  </div>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 99, fontSize: 11.5,
                    fontWeight: 600, background: 'color-mix(in srgb, var(--success) 16%, transparent)', color: 'var(--success)', height: 'fit-content', flexShrink: 0,
                  }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--success)' }} />
                    {t(`courses.status.${c.status}`, c.status)}
                  </span>
                </div>

                {c.instructor_name && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 12, color: 'var(--text-secondary)', fontSize: 13 }}>
                    <UserIcon size={14} strokeWidth={1.8} />
                    {c.instructor_name}
                  </div>
                )}

                {c.slots.length > 0 && (
                  <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {c.slots.map((s, j) => (
                      <span key={j} style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '5px 10px', borderRadius: 8,
                        background: 'var(--bg-tertiary)', color: 'var(--text-secondary)',
                      }}>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{dayLabel(s.day_of_week)}</span>
                        {fmtTime(s.start_time)}–{fmtTime(s.end_time)}
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: 'var(--text-muted)' }}>
                          <MapPin size={11} strokeWidth={1.8} />
                          {s.is_online ? t('courses.online') : (s.location || 'TBA')}
                        </span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
            );
          })}
        </div>
      )}
    </PageWrap>
  );
}
