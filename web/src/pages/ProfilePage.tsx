import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { User } from 'lucide-react';
import { api } from '../services/api';
import { PageHeader } from '../components/PageHeader';

interface Profile {
  first_name: string;
  last_name: string;
  email: string;
  user_type: string;
  student_id: string | null;
  gpa: number | null;
  department: string | null;
  faculty: string | null;
  program_level: string | null;
  academic_year: number | null;
  semester_number: number | null;
  total_credits_completed: number | null;
  total_credits_enrolled: number | null;
  is_on_probation: boolean;
  has_advisor_hold: boolean;
  has_financial_hold: boolean;
  is_exchange_student: boolean;
  is_double_major: boolean;
  is_minor: boolean;
}

function Field({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-color)' }}>
      <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>{label}</span>
      <span style={{ color: 'var(--text-primary)', fontSize: 14, fontWeight: 500 }}>{value ?? '—'}</span>
    </div>
  );
}

export function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const { t } = useTranslation();

  useEffect(() => {
    api.getProfile().then(p => {
      setProfile(p);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{t('profile.loading')}</div>;
  }
  if (!profile) {
    return <div style={{ padding: 40, color: 'var(--text-secondary)' }}>{t('profile.empty')}</div>;
  }

  const flags: Array<{ key: keyof Profile; label: string; tone: 'warn' | 'info' }> = [
    { key: 'is_on_probation', label: t('profile.flags.probation'), tone: 'warn' },
    { key: 'has_advisor_hold', label: t('profile.flags.advisorHold'), tone: 'warn' },
    { key: 'has_financial_hold', label: t('profile.flags.financialHold'), tone: 'warn' },
    { key: 'is_exchange_student', label: t('profile.flags.exchange'), tone: 'info' },
    { key: 'is_double_major', label: t('profile.flags.doubleMajor'), tone: 'info' },
    { key: 'is_minor', label: t('profile.flags.minor'), tone: 'info' },
  ];
  const activeFlags = flags.filter(f => profile[f.key]);

  return (
    <div style={{ padding: '32px 48px 64px', maxWidth: 1100, margin: '0 auto' }}>
      <PageHeader icon={User} eyebrow={t('sidebar.profile')} title={t('profile.title')} />

      <div className="card" style={{ padding: 20, marginBottom: 24 }}>
        <h3 style={{ marginTop: 0, marginBottom: 8, color: 'var(--text-primary)' }}>
          {profile.first_name} {profile.last_name}
        </h3>
        <Field label={t('profile.email')} value={profile.email} />
        <Field label={t('profile.userType')} value={profile.user_type} />
        <Field label={t('profile.studentId')} value={profile.student_id} />
        <Field label={t('profile.gpa')} value={profile.gpa} />
      </div>

      <h3 style={{ marginBottom: 12, color: 'var(--accent)' }}>{t('profile.academic')}</h3>
      <div className="card" style={{ padding: 20, marginBottom: 24 }}>
        <Field label={t('profile.department')} value={profile.department} />
        <Field label={t('profile.faculty')} value={profile.faculty} />
        <Field label={t('profile.programLevel')} value={profile.program_level} />
        <Field label={t('profile.academicYear')} value={profile.academic_year} />
        <Field label={t('profile.semester')} value={profile.semester_number} />
        <Field label={t('profile.creditsCompleted')} value={profile.total_credits_completed} />
        <Field label={t('profile.creditsEnrolled')} value={profile.total_credits_enrolled} />
      </div>

      <h3 style={{ marginBottom: 12, color: 'var(--accent)' }}>{t('profile.status')}</h3>
      {activeFlags.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>{t('profile.noFlags')}</p>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {activeFlags.map(f => (
            <span key={f.key} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 12px', borderRadius: 99, fontSize: 13, fontWeight: 600,
              background: `color-mix(in srgb, ${f.tone === 'warn' ? 'var(--warning)' : 'var(--info)'} 16%, transparent)`,
              color: f.tone === 'warn' ? 'var(--warning)' : 'var(--info)',
            }}>
              {f.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
