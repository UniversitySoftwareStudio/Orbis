import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldAlert, Check, X, Clock } from 'lucide-react';
import { api } from '../services/api';

interface RuleAssignment {
  id: string;
  urgency: string;
  status: string;
  reason: string;
  assigned_at: string;
  rule_text: string;
  applies_to: string | null;
  trigger: string | null;
  deadline: string | null;
  consequence: string | null;
  authority: string | null;
  blocking: boolean;
  valid_until: string | null;
}

function urgencyColor(urgency: string): string {
  switch (urgency) {
    case 'high': return '#ef5350';
    case 'medium': return '#ff9800';
    default: return '#42a5f5';
  }
}

export function RegulationsPage() {
  const [items, setItems] = useState<RuleAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const { t } = useTranslation();

  useEffect(() => {
    api.getMyRegulations().then(d => {
      setItems(d ?? []);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  const updateStatus = async (id: string, status: string) => {
    setBusyId(id);
    try {
      const updated = await api.updateRegulationStatus(id, status);
      if (updated) {
        setItems(prev => prev.map(it => (it.id === id ? { ...it, status: updated.status } : it)));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{t('regulations.loading')}</div>;
  }

  return (
    <div style={{ padding: 32, maxWidth: 820, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 8, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <ShieldAlert size={20} strokeWidth={1.8} />
        {t('regulations.title')}
      </h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>{t('regulations.subtitle')}</p>

      {items.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>{t('regulations.empty')}</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {items.map(item => (
            <div key={item.id} className="card" style={{
              padding: 20,
              opacity: item.status === 'active' ? 1 : 0.6,
              borderLeft: `4px solid ${urgencyColor(item.urgency)}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                <span style={{
                  display: 'inline-block', padding: '2px 10px', borderRadius: 12, fontSize: 12,
                  fontWeight: 500, background: urgencyColor(item.urgency), color: '#fff',
                }}>
                  {t(`regulations.urgency.${item.urgency}`, item.urgency)}
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {t(`regulations.statusLabel.${item.status}`, item.status)}
                </span>
              </div>

              <div style={{ fontSize: 15, color: 'var(--text-primary)', marginBottom: 8 }}>{item.rule_text}</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>{item.reason}</div>

              {item.deadline && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
                  <Clock size={13} strokeWidth={1.8} />
                  {t('regulations.deadline')}: {item.deadline}
                </div>
              )}
              {item.consequence && (
                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
                  {t('regulations.consequence')}: {item.consequence}
                </div>
              )}

              {item.status === 'active' && (
                <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                  <button
                    className="btn btn-accent"
                    disabled={busyId === item.id}
                    onClick={() => updateStatus(item.id, 'actioned')}
                    style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    <Check size={15} strokeWidth={2} />
                    {t('regulations.markActioned')}
                  </button>
                  <button
                    className="btn btn-ghost"
                    disabled={busyId === item.id}
                    onClick={() => updateStatus(item.id, 'dismissed')}
                    style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    <X size={15} strokeWidth={2} />
                    {t('regulations.dismiss')}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
