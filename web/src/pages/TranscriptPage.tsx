import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { GraduationCap } from 'lucide-react';
import { api } from '../services/api';

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
      <div style={{ padding: 32, maxWidth: 900, margin: '0 auto' }}>
        <h2 style={{ marginBottom: 24, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <GraduationCap size={20} strokeWidth={1.8} />
          {t('transcript.title')}
        </h2>
        <p style={{ color: 'var(--text-secondary)' }}>{t('transcript.empty')}</p>
      </div>
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
    <div style={{ padding: 32, maxWidth: 900, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 8, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <GraduationCap size={20} strokeWidth={1.8} />
        {t('transcript.title')}
      </h2>
      <div style={{ display: 'flex', gap: 24, marginBottom: 24, color: 'var(--text-secondary)' }}>
        <span>{t('transcript.cumulativeGpa')}: <strong style={{ color: 'var(--accent)' }}>{data.cumulative_gpa ?? '—'}</strong></span>
        <span>{t('transcript.totalCredits')}: <strong style={{ color: 'var(--accent)' }}>{data.total_credits}</strong></span>
      </div>

      {termOrder.map(term => (
        <div key={term}>
          <h3 style={{ marginBottom: 12, color: 'var(--accent)', textTransform: 'capitalize' }}>
            {term} <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>({t('transcript.gpa')}: {termGpa(byTerm[term])})</span>
          </h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 28, background: 'var(--bg-card)', borderRadius: 8, overflow: 'hidden' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #2d3561', textAlign: 'left', backgroundColor: 'var(--bg-table-header)' }}>
                <th style={{ padding: '8px 12px', color: 'var(--sidebar-text)' }}>{t('transcript.code')}</th>
                <th style={{ padding: '8px 12px', color: 'var(--sidebar-text)' }}>{t('transcript.course')}</th>
                <th style={{ padding: '8px 12px', color: 'var(--sidebar-text)' }}>{t('transcript.credits')}</th>
                <th style={{ padding: '8px 12px', color: 'var(--sidebar-text)' }}>{t('transcript.grade')}</th>
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
    </div>
  );
}
