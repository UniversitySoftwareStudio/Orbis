import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BookOpen, MapPin, User as UserIcon } from 'lucide-react';
import { api } from '../services/api';

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
    <div style={{ padding: 32, maxWidth: 900, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 8, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <BookOpen size={20} strokeWidth={1.8} />
        {t('courses.title')}
      </h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>
        {t('courses.count', { count: courses.length })}
      </p>

      {courses.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>{t('courses.empty')}</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {courses.map((c, i) => (
            <div key={i} className="card" style={{ padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {c.course_code} — {c.course_name}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                    {t('courses.section')} {c.section_number} · {c.section_type}
                  </div>
                </div>
                <span style={{
                  display: 'inline-block', padding: '2px 10px', borderRadius: 12, fontSize: 12,
                  fontWeight: 500, background: '#66bb6a', color: '#fff', height: 'fit-content',
                }}>
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
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {c.slots.map((s, j) => (
                    <div key={j} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-primary)' }}>
                      <span style={{ fontWeight: 500, minWidth: 40 }}>{dayLabel(s.day_of_week)}</span>
                      <span>{fmtTime(s.start_time)}–{fmtTime(s.end_time)}</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text-secondary)' }}>
                        <MapPin size={13} strokeWidth={1.8} />
                        {s.is_online ? t('courses.online') : (s.location || 'TBA')}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
