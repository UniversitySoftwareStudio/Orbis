import { useState, useEffect, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ShieldAlert,
  Check,
  X,
  Clock,
  AlertTriangle,
  RefreshCw,
  Activity,
  CheckCircle2,
  CircleDot,
  FileText,
  UserRound,
} from 'lucide-react';
import { api } from '../services/api';
import { PageHeader, PageWrap } from '../components/PageHeader';

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

interface TraceStep {
  message: string;
  detail?: string;
}

interface RuleDecision {
  rule_id: string;
  rule_text: string;
  applies_to?: string | null;
  trigger?: string | null;
  deadline?: string | null;
  blocking?: boolean;
  consequence?: string | null;
  authority?: string | null;
  match_type: string;
  applies: boolean;
  reason: string;
}

interface AssignmentEffect {
  assignment_id: string;
  rule_id: string;
  rule_text: string;
  urgency: string;
  status: string;
  before_status: string | null;
  action: string;
  reason: string;
}

interface CheckSummary {
  rules_checked: number;
  applicable: number;
  created: number;
  updated: number;
  reactivated: number;
  retired?: number;
  unchanged: number;
}

function urgencyColor(urgency: string): string {
  switch (urgency) {
    case 'high': return 'var(--danger)';
    case 'medium': return 'var(--warning)';
    default: return 'var(--info)';
  }
}

function decisionTone(applies: boolean): string {
  return applies ? 'var(--success)' : 'var(--text-muted)';
}

function actionLabel(action: string): string {
  switch (action) {
    case 'created': return 'New';
    case 'updated': return 'Updated';
    case 'reactivated': return 'Reactivated';
    case 'retired': return 'No longer applies';
    default: return 'Still applies';
  }
}

export function RegulationsPage() {
  const [items, setItems] = useState<RuleAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'assignments' | 'trace'>('assignments');
  const [checkRunning, setCheckRunning] = useState(false);
  const [traceSteps, setTraceSteps] = useState<TraceStep[]>([]);
  const [profileContext, setProfileContext] = useState('');
  const [decisions, setDecisions] = useState<RuleDecision[]>([]);
  const [effects, setEffects] = useState<AssignmentEffect[]>([]);
  const [summary, setSummary] = useState<CheckSummary | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);
  const { t } = useTranslation();

  const loadRegulations = () => {
    return api.getMyRegulations().then(d => setItems(d ?? []));
  };

  useEffect(() => {
    loadRegulations().catch(console.error).finally(() => setLoading(false));
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

  const runCheck = async () => {
    if (checkRunning) return;
    setActiveTab('trace');
    setCheckRunning(true);
    setCheckError(null);
    setTraceSteps([]);
    setProfileContext('');
    setDecisions([]);
    setEffects([]);
    setSummary(null);

    try {
      await api.runRegulationCheckStream((type, data) => {
        if (type === 'step') {
          setTraceSteps(prev => [...prev, { message: data.message, detail: data.detail }]);
        } else if (type === 'profile') {
          setProfileContext(data.context || '');
        } else if (type === 'rule_decision') {
          setDecisions(prev => [...prev, data]);
        } else if (type === 'assignment') {
          setEffects(prev => [...prev, data]);
        } else if (type === 'summary') {
          setSummary(data);
        } else if (type === 'done') {
          if (Array.isArray(data.assignments)) setItems(data.assignments);
          setCheckRunning(false);
        } else if (type === 'error') {
          setCheckError(data.detail || 'Regulation check failed');
          setCheckRunning(false);
        }
      });
    } catch (err: any) {
      console.error(err);
      setCheckError(err.message || 'Regulation check failed');
    } finally {
      setCheckRunning(false);
    }
  };

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{t('regulations.loading')}</div>;
  }

  const activeCount = items.filter(i => i.status === 'active').length;
  const applicableCount = decisions.filter(d => d.applies).length;

  return (
    <PageWrap maxWidth={1120}>
      <PageHeader
        icon={ShieldAlert}
        eyebrow={t('sidebar.regulations')}
        title={t('regulations.title')}
        subtitle={t('regulations.subtitle')}
        right={(
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {items.length > 0 && (
              <div className="card" style={{ padding: '12px 20px', textAlign: 'center' }}>
                <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--accent)', letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>{activeCount}</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2 }}>{t('regulations.statusLabel.active', 'active')}</div>
              </div>
            )}
            <button
              className="btn btn-accent"
              onClick={runCheck}
              disabled={checkRunning}
              style={{ height: 42, display: 'inline-flex', alignItems: 'center', gap: 8 }}
            >
              <RefreshCw size={15} strokeWidth={2.2} style={{ animation: checkRunning ? 'cw-spin 0.9s linear infinite' : undefined }} />
              {checkRunning ? 'Checking' : 'Run Check'}
            </button>
          </div>
        )}
      />

      <div style={{
        display: 'inline-flex', padding: 3, borderRadius: 10, border: '1px solid var(--border-color)',
        background: 'var(--bg-card)', marginBottom: 18,
      }}>
        <button
          onClick={() => setActiveTab('assignments')}
          className="btn"
          style={{
            padding: '7px 12px', background: activeTab === 'assignments' ? 'var(--accent-subtle)' : 'transparent',
            color: activeTab === 'assignments' ? 'var(--accent)' : 'var(--text-secondary)',
          }}
        >
          Current Assignments
        </button>
        <button
          onClick={() => setActiveTab('trace')}
          className="btn"
          style={{
            padding: '7px 12px', background: activeTab === 'trace' ? 'var(--accent-subtle)' : 'transparent',
            color: activeTab === 'trace' ? 'var(--accent)' : 'var(--text-secondary)',
          }}
        >
          Agent Trace
        </button>
      </div>

      {activeTab === 'assignments' ? (
        <AssignmentsGrid
          items={items}
          busyId={busyId}
          updateStatus={updateStatus}
          emptyText={t('regulations.empty')}
          statusLabel={(status) => t(`regulations.statusLabel.${status}`, status)}
          urgencyLabel={(urgency) => t(`regulations.urgency.${urgency}`, urgency)}
          deadlineLabel={t('regulations.deadline')}
          markActionedLabel={t('regulations.markActioned')}
          dismissLabel={t('regulations.dismiss')}
        />
      ) : (
        <AgentTrace
          running={checkRunning}
          error={checkError}
          steps={traceSteps}
          profileContext={profileContext}
          decisions={decisions}
          effects={effects}
          summary={summary}
          applicableCount={applicableCount}
          onRun={runCheck}
        />
      )}
    </PageWrap>
  );
}

function AssignmentsGrid({
  items,
  busyId,
  updateStatus,
  emptyText,
  statusLabel,
  urgencyLabel,
  deadlineLabel,
  markActionedLabel,
  dismissLabel,
}: {
  items: RuleAssignment[];
  busyId: string | null;
  updateStatus: (id: string, status: string) => void;
  emptyText: string;
  statusLabel: (status: string) => string;
  urgencyLabel: (urgency: string) => string;
  deadlineLabel: string;
  markActionedLabel: string;
  dismissLabel: string;
}) {
  if (items.length === 0) {
    return <p style={{ color: 'var(--text-secondary)' }}>{emptyText}</p>;
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16, alignItems: 'stretch' }}>
      {items.map(item => {
        const tone = urgencyColor(item.urgency);
        return (
          <div key={item.id} className="card" style={{
            padding: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden',
            opacity: item.status === 'active' ? 1 : 0.55,
          }}>
            <div style={{ height: 3, background: tone }} />

            <div style={{ padding: '16px 18px 18px', display: 'flex', flexDirection: 'column', flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', borderRadius: 99, fontSize: 11,
                  fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
                  background: `color-mix(in srgb, ${tone} 16%, transparent)`, color: tone,
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: tone }} />
                  {urgencyLabel(item.urgency)}
                </span>
                <span style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {statusLabel(item.status)}
                </span>
              </div>

              <div style={{ fontSize: 14.5, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.5, letterSpacing: '-0.01em' }}>{item.rule_text}</div>

              <div style={{
                fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginTop: 10,
                paddingLeft: 11, borderLeft: `2px solid ${tone}`,
              }}>{item.reason}</div>

              {(item.deadline || item.consequence) && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14 }}>
                  {item.deadline && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '5px 10px', borderRadius: 8, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
                      <Clock size={12.5} strokeWidth={2} style={{ color: tone }} />
                      <b style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{deadlineLabel}:</b> {item.deadline}
                    </span>
                  )}
                  {item.consequence && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '5px 10px', borderRadius: 8, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
                      <AlertTriangle size={12.5} strokeWidth={2} style={{ color: 'var(--text-muted)' }} />
                      {item.consequence}
                    </span>
                  )}
                </div>
              )}

              {item.status === 'active' && (
                <div style={{ display: 'flex', gap: 8, marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border-color)' }}>
                  <button
                    className="btn btn-accent"
                    disabled={busyId === item.id}
                    onClick={() => updateStatus(item.id, 'actioned')}
                    style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    <Check size={15} strokeWidth={2.2} />
                    {markActionedLabel}
                  </button>
                  <button
                    className="btn btn-ghost"
                    disabled={busyId === item.id}
                    onClick={() => updateStatus(item.id, 'dismissed')}
                    style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    <X size={15} strokeWidth={2.2} />
                    {dismissLabel}
                  </button>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AgentTrace({
  running,
  error,
  steps,
  profileContext,
  decisions,
  effects,
  summary,
  applicableCount,
  onRun,
}: {
  running: boolean;
  error: string | null;
  steps: TraceStep[];
  profileContext: string;
  decisions: RuleDecision[];
  effects: AssignmentEffect[];
  summary: CheckSummary | null;
  applicableCount: number;
  onRun: () => void;
}) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 0.9fr) minmax(420px, 1.25fr)', gap: 16, alignItems: 'start' }}>
      <div style={{ display: 'grid', gap: 14 }}>
        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent)', fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                <Activity size={15} />
                Self Check
              </div>
              <div style={{ marginTop: 6, color: 'var(--text-primary)', fontWeight: 650, fontSize: 16 }}>
                Match regulations against your current profile
              </div>
            </div>
            <button className="btn btn-accent" onClick={onRun} disabled={running} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <RefreshCw size={15} style={{ animation: running ? 'cw-spin 0.9s linear infinite' : undefined }} />
              {running ? 'Running' : 'Run Again'}
            </button>
          </div>

          {summary && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 16 }}>
              <Metric label="Checked" value={summary.rules_checked} />
              <Metric label="Applies" value={summary.applicable} />
              <Metric label="New" value={summary.created} />
              <Metric label="Changed" value={summary.updated + summary.reactivated + (summary.retired ?? 0)} />
            </div>
          )}

          {!summary && !running && decisions.length === 0 && (
            <div style={{ marginTop: 14, color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.5 }}>
              Run a check to see how the agent builds your context, evaluates each regulation, and updates your assignments.
            </div>
          )}
          {error && <div style={{ marginTop: 14, color: 'var(--danger)', fontSize: 13 }}>{error}</div>}
        </div>

        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <UserRound size={16} color="var(--accent)" />
            <div style={{ color: 'var(--text-primary)', fontWeight: 650 }}>User Context</div>
          </div>
          <pre style={{
            whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: profileContext ? 'var(--text-secondary)' : 'var(--text-muted)',
            fontFamily: 'inherit', fontSize: 12.5, lineHeight: 1.55, margin: 0,
          }}>
            {profileContext || 'No check has been run yet.'}
          </pre>
        </div>

        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <CircleDot size={16} color="var(--accent)" />
            <div style={{ color: 'var(--text-primary)', fontWeight: 650 }}>Agent Steps</div>
          </div>
          <div style={{ display: 'grid', gap: 9 }}>
            {steps.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No steps yet.</div>
            ) : steps.map((step, index) => (
              <div key={`${step.message}-${index}`} style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
                <CheckCircle2 size={15} color="var(--path-pull)" style={{ marginTop: 2, flexShrink: 0 }} />
                <div>
                  <div style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 600 }}>{step.message}</div>
                  {step.detail && <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 2 }}>{step.detail}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 14 }}>
        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <FileText size={16} color="var(--accent)" />
              <div style={{ color: 'var(--text-primary)', fontWeight: 650 }}>Rule Decisions</div>
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{applicableCount} applicable</div>
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            {decisions.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Decisions will appear here during a check.</div>
            ) : decisions.map(decision => {
              const tone = decisionTone(decision.applies);
              return (
                <div key={decision.rule_id} style={{
                  border: '1px solid var(--border-color)', borderRadius: 8, padding: 12,
                  background: decision.applies ? 'color-mix(in srgb, var(--success) 7%, var(--bg-secondary))' : 'var(--bg-secondary)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
                    <div style={{ color: 'var(--text-primary)', fontWeight: 650, fontSize: 13.5, lineHeight: 1.45 }}>{decision.rule_text}</div>
                    <span style={{
                      color: tone, background: `color-mix(in srgb, ${tone} 14%, transparent)`, borderRadius: 999,
                      padding: '3px 8px', fontSize: 10.5, fontWeight: 800, textTransform: 'uppercase', flexShrink: 0,
                    }}>
                      {decision.applies ? 'applies' : 'no match'}
                    </span>
                  </div>
                  <div style={{ marginTop: 8, color: 'var(--text-secondary)', fontSize: 12.5, lineHeight: 1.5 }}>{decision.reason}</div>
                  <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <TinyChip>{decision.match_type}</TinyChip>
                    {decision.deadline && <TinyChip>deadline: {decision.deadline}</TinyChip>}
                    {decision.blocking && <TinyChip>blocking</TinyChip>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <CheckCircle2 size={16} color="var(--success)" />
            <div style={{ color: 'var(--text-primary)', fontWeight: 650 }}>Affected Regulations</div>
          </div>
          <div style={{ display: 'grid', gap: 9 }}>
            {effects.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>{running ? 'Waiting for assignment updates.' : 'No affected assignments yet.'}</div>
            ) : effects.map(effect => {
              const tone = urgencyColor(effect.urgency);
              return (
                <div key={`${effect.assignment_id}-${effect.action}`} style={{ border: '1px solid var(--border-color)', borderRadius: 8, padding: 11, background: 'var(--bg-secondary)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ color: tone, fontSize: 11, fontWeight: 800, textTransform: 'uppercase' }}>{actionLabel(effect.action)}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{effect.status}</span>
                  </div>
                  <div style={{ marginTop: 6, color: 'var(--text-primary)', fontSize: 13, lineHeight: 1.45, fontWeight: 600 }}>{effect.rule_text}</div>
                  <div style={{ marginTop: 6, color: 'var(--text-secondary)', fontSize: 12.5, lineHeight: 1.45 }}>{effect.reason}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ background: 'var(--bg-tertiary)', borderRadius: 8, padding: '9px 10px' }}>
      <div style={{ color: 'var(--text-primary)', fontWeight: 800, fontSize: 18, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 1 }}>{label}</div>
    </div>
  );
}

function TinyChip({ children }: { children: ReactNode }) {
  return (
    <span style={{ color: 'var(--text-muted)', background: 'var(--bg-tertiary)', borderRadius: 7, padding: '3px 7px', fontSize: 11 }}>
      {children}
    </span>
  );
}
