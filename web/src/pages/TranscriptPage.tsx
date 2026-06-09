import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { GraduationCap } from 'lucide-react';
import { api } from '../services/api';
import { PageHeader, PageWrap } from '../components/PageHeader';

interface TranscriptEntry {
  course_code: string;
  course_name: string;
  term: string;
  credits: number;
  grade_letter: string | null;
  grade_numeric: number | null;
}

interface Transcript {
  entries: TranscriptEntry[];
  cumulative_gpa: number | null;
  total_credits: number;
}

export function TranscriptPage() {
  const [data, setData] = useState<Transcript | null>(null);
  const [loading, setLoading] = useState(true);
  const { t } = useTranslation();

  useEffect(() => {
    api.getTranscript().then(d => {
      setData(d);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{t('transcript.loading')}</div>;
  }
  if (!data || data.entries.length === 0) {
    return (
      <PageWrap maxWidth={1200}>
        <PageHeader icon={GraduationCap} eyebrow={t('sidebar.transcript')} title={t('transcript.title')} />
        <p style={{ color: 'var(--text-secondary)' }}>{t('transcript.empty')}</p>
      </PageWrap>
    );
  }

  // Group entries by term, preserving the backend's recency order.
  const byTerm: Record<string, TranscriptEntry[]> = {};
  const termOrder: string[] = [];
  for (const e of data.entries) {
    if (!byTerm[e.term]) { byTerm[e.term] = []; termOrder.push(e.term); }
    byTerm[e.term].push(e);
  }

  const termGpa = (entries: TranscriptEntry[]): string => {
    const graded = entries.filter(e => e.grade_numeric != null);
    if (graded.length === 0) return '—';
    const totalCredits = graded.reduce((s, e) => s + e.credits, 0);
    const weighted = graded.reduce((s, e) => s + (e.grade_numeric ?? 0) * e.credits, 0);
    return totalCredits ? (weighted / totalCredits).toFixed(2) : '—';
  };

  return (
    <PageWrap maxWidth={1200}>
      <PageHeader
        icon={GraduationCap}
        eyebrow={t('sidebar.transcript')}
        title={t('transcript.title')}
        right={
          <div style={{ display: 'flex', gap: 12 }}>
            <div className="card" style={{ padding: '12px 20px', textAlign: 'center' }}>
              <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--accent)', letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>{data.cumulative_gpa ?? '—'}</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2 }}>{t('transcript.cumulativeGpa')}</div>
            </div>
            <div className="card" style={{ padding: '12px 20px', textAlign: 'center' }}>
              <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>{data.total_credits}</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2 }}>{t('transcript.totalCredits')}</div>
            </div>
          </div>
        }
      />

      {termOrder.map(term => (
        <div key={term}>
          <h3 style={{ marginBottom: 12, color: 'var(--accent)', textTransform: 'capitalize' }}>
            {term} <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>({t('transcript.gpa')}: {termGpa(byTerm[term])})</span>
          </h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 28, background: 'var(--bg-card)', borderRadius: 8, overflow: 'hidden' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', backgroundColor: 'var(--bg-table-header)' }}>
                <th style={{ padding: '10px 14px', fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>{t('transcript.code')}</th>
                <th style={{ padding: '10px 14px', fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>{t('transcript.course')}</th>
                <th style={{ padding: '10px 14px', fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>{t('transcript.credits')}</th>
                <th style={{ padding: '10px 14px', fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>{t('transcript.grade')}</th>
              </tr>
            </thead>
            <tbody>
              {byTerm[term].map((e, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '10px 12px', fontSize: 14, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{e.course_code}</td>
                  <td style={{ padding: '10px 12px', fontSize: 14, color: 'var(--text-primary)' }}>{e.course_name}</td>
                  <td style={{ padding: '10px 12px', fontSize: 14, color: 'var(--text-primary)' }}>{e.credits}</td>
                  <td style={{ padding: '10px 12px', fontSize: 14, color: 'var(--text-primary)' }}>
                    {e.grade_letter ?? '—'}{e.grade_numeric != null ? ` (${e.grade_numeric})` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </PageWrap>
  );
}
