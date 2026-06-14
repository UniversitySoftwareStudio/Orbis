import { useState, useEffect, useMemo, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ShieldAlert,
  Check,
  X,
  Clock,
  RefreshCw,
  Activity,
  CheckCircle2,
  FileText,
  Ban,
  Lightbulb,
  ExternalLink,
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
  source_url: string | null;
  evidence_quote: string | null;
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
  source_url?: string | null;
  evidence_quote?: string | null;
  match_type: string;
  applies: boolean;
  reason: string;
  persistable?: boolean;
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

interface RegulationRunSnapshot {
  run_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  sources_processed: number;
  chunks_processed: number;
  events_created: number;
  error_message: string | null;
}

interface RegulationDiagnostics {
  user: { id: number; email: string; name: string; type: string };
  assignments: Record<string, number>;
  rules: Record<string, number>;
  events: Record<string, number>;
  sources: Record<string, number>;
  last_run: RegulationRunSnapshot | null;
  last_run_events: Record<string, number>;
  last_run_candidate_decisions: Record<string, number>;
  last_run_candidate_reasons: Record<string, number>;
  observations: string[];
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

// The backend's `reason` is a debug-flavored string like:
//   "Profile values {'gpa': 2.6, 'enrolled_credits': 7, 'is_active': True} satisfy gpa >= 2.60."
// Parse it into readable evidence: a list of {field, value} facts + a plain condition
// clause, so the detail panel can render a clean SIS-style breakdown instead of raw text.
interface ParsedReason {
  facts: { key: string; value: string }[];
  condition: string | null;
  prose: string;
}

const FIELD_LABELS: Record<string, string> = {
  gpa: 'GPA',
  enrolled_credits: 'Enrolled credits',
  is_active: 'Active student',
  semester: 'Semester',
  program: 'Program',
  year: 'Year',
  total_credits: 'Total credits',
  completed_credits: 'Completed credits',
};

function prettyFieldKey(key: string): string {
  if (FIELD_LABELS[key]) return FIELD_LABELS[key];
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function prettyValue(raw: string): string {
  const v = raw.trim().replace(/^['"]|['"]$/g, '');
  if (v === 'True') return 'Yes';
  if (v === 'False') return 'No';
  return v;
}

function parseReason(reason: string): ParsedReason {
  const out: ParsedReason = { facts: [], condition: null, prose: reason };
  if (!reason) return out;

  // Pull the dict body: {'gpa': 2.6, 'enrolled_credits': 7, 'is_active': True}
  const dictMatch = reason.match(/\{([^}]*)\}/);
  if (dictMatch) {
    const body = dictMatch[1];
    // Split on commas that separate key/value pairs.
    for (const pair of body.split(',')) {
      const kv = pair.split(':');
      if (kv.length < 2) continue;
      const key = kv[0].trim().replace(/^['"]|['"]$/g, '');
      const value = kv.slice(1).join(':').trim();
      if (key) out.facts.push({ key: prettyFieldKey(key), value: prettyValue(value) });
    }
  }

  // Everything after "satisfy" / "satisfies" is the condition clause.
  const condMatch = reason.match(/satisf(?:y|ies)\s+(.+?)\.?\s*$/i);
  if (condMatch) {
    out.condition = condMatch[1].trim();
  }

  return out;
}

export function RegulationsPage() {
  const [items, setItems] = useState<RuleAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'assignments' | 'trace'>('assignments');
  const [checkRunning, setCheckRunning] = useState(false);
  const [traceSteps, setTraceSteps] = useState<TraceStep[]>([]);
  const [, setProfileContext] = useState('');
  const [decisions, setDecisions] = useState<RuleDecision[]>([]);
  const [effects, setEffects] = useState<AssignmentEffect[]>([]);
  const [summary, setSummary] = useState<CheckSummary | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<RegulationDiagnostics | null>(null);
  const [diagnosticsError, setDiagnosticsError] = useState<string | null>(null);
  const { t } = useTranslation();

  const loadRegulations = () => {
    return api.getMyRegulations().then(d => setItems(d ?? []));
  };

  const loadDiagnostics = () => {
    setDiagnosticsError(null);
    return api.getMyRegulationDiagnostics()
      .then(d => setDiagnostics(d ?? null))
      .catch((err: any) => {
        console.error(err);
        setDiagnosticsError(err.message || 'Could not load regulation diagnostics');
      });
  };

  useEffect(() => {
    Promise.allSettled([loadRegulations(), loadDiagnostics()]).finally(() => setLoading(false));
  }, []);

  // Keep selection valid: default to the first active item once loaded.
  useEffect(() => {
    if (loading) return;
    if (selectedId && items.some(i => i.id === selectedId)) return;
    const firstActive = items.find(i => i.status === 'active') ?? items[0];
    setSelectedId(firstActive?.id ?? null);
  }, [items, loading, selectedId]);

  const updateStatus = async (id: string, status: string) => {
    setBusyId(id);
    try {
      const updated = await api.updateRegulationStatus(id, status);
      if (updated) {
        // Resolved items (done/dismissed) drop out of the user's list; the
        // backend keeps the row with its new status for the audit trail.
        const stillActive = updated.status === 'active';
        setItems(prev =>
          stillActive
            ? prev.map(it => (it.id === id ? { ...it, status: updated.status } : it))
            : prev.filter(it => it.id !== id),
        );
        if (!stillActive && selectedId === id) setSelectedId(null);
        void loadDiagnostics();
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
    void loadDiagnostics();

    try {
      await api.runRegulationCheckStream((type, data) => {
        if (type === 'step') {
          setTraceSteps(prev => [...prev, { message: data.message, detail: data.detail }]);
        } else if (type === 'profile') {
          setProfileContext(data.context || '');
        } else if (type === 'rule_decisions') {
          const batch = Array.isArray(data.decisions) ? data.decisions : [];
          setDecisions(prev => [...prev, ...batch]);
        } else if (type === 'rule_decision') {
          setDecisions(prev => [...prev, data]);
        } else if (type === 'assignments') {
          const batch = Array.isArray(data.assignments) ? data.assignments : [];
          setEffects(prev => [...prev, ...batch]);
        } else if (type === 'assignment') {
          setEffects(prev => [...prev, data]);
        } else if (type === 'summary') {
          setSummary(data);
        } else if (type === 'done') {
          if (Array.isArray(data.assignments)) setItems(data.assignments);
          void loadDiagnostics();
          setCheckRunning(false);
        } else if (type === 'error') {
          setCheckError(data.detail || 'Regulation check failed');
          setCheckRunning(false);
        }
      });
    } catch (err: any) {
      console.error(err);
      setCheckError(err.message || 'Regulation check failed');
      void loadDiagnostics();
    } finally {
      setCheckRunning(false);
    }
  };

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{t('regulations.loading')}</div>;
  }

  const activeCount = items.filter(i => i.status === 'active').length;
  const applicableCount = decisions.filter(d => d.applies).length;
  const selected = items.find(i => i.id === selectedId) ?? null;

  return (
    <PageWrap maxWidth={1280}>
      <PageHeader
        icon={ShieldAlert}
        eyebrow={t('sidebar.regulations')}
        title={t('regulations.title')}
        right={(
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {items.length > 0 && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', height: 34, padding: '0 12px',
                border: '1px solid var(--border-color)', borderRadius: 999, color: 'var(--text-secondary)',
                fontSize: 12.5, fontWeight: 700, background: 'var(--bg-card)',
              }}>
                {activeCount} {t('regulations.statusLabel.active', 'active')}
              </span>
            )}
            <button
              className="btn btn-accent"
              onClick={runCheck}
              disabled={checkRunning}
              style={{ height: 42, display: 'inline-flex', alignItems: 'center', gap: 8 }}
            >
              <RefreshCw size={15} strokeWidth={2.2} style={{ animation: checkRunning ? 'cw-spin 0.9s linear infinite' : undefined }} />
              {checkRunning ? t('regulations.checking') : t('regulations.runCheck')}
            </button>
          </div>
        )}
      />

      <DiagnosticsPanel
        diagnostics={diagnostics}
        error={diagnosticsError}
        running={checkRunning}
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
          {t('regulations.tabs.assignments')}
        </button>
        <button
          onClick={() => setActiveTab('trace')}
          className="btn"
          style={{
            padding: '7px 12px', background: activeTab === 'trace' ? 'var(--accent-subtle)' : 'transparent',
            color: activeTab === 'trace' ? 'var(--accent)' : 'var(--text-secondary)',
          }}
        >
          {t('regulations.tabs.trace')}
        </button>
      </div>

      {activeTab === 'assignments' ? (
        <AssignmentsExplorer
          items={items}
          selected={selected}
          onSelect={(id) => setSelectedId(id)}
          busyId={busyId}
          updateStatus={updateStatus}
          t={t}
        />
      ) : (
        <AgentTrace
          running={checkRunning}
          error={checkError}
          steps={traceSteps}
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

type TFn = ReturnType<typeof useTranslation>['t'];

function DiagnosticsPanel({
  diagnostics,
  error,
  running,
}: {
  diagnostics: RegulationDiagnostics | null;
  error: string | null;
  running: boolean;
}) {
  const d = diagnostics;
  const lastRun = d?.last_run;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
      padding: '9px 12px', marginBottom: 14,
      border: '1px solid var(--border-color)', borderRadius: 999, background: 'var(--bg-card)',
    }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: running ? 'var(--warning)' : 'var(--accent)', fontSize: 12, fontWeight: 800 }}>
        <Activity size={14} />
        {running ? 'checking' : lastRun?.status ?? 'no run'}
      </span>
      {d ? (
        <>
          <StatusDot label="kb" value={d.sources.knowledge_base_rows ?? 0} />
          <StatusDot label="ev" value={d.events.total ?? 0} />
          <StatusDot label="rules" value={d.rules.active ?? 0} />
          <StatusDot label="mine" value={d.assignments.active ?? 0} />
        </>
      ) : (
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>loading</span>
      )}
      {error && <span style={{ color: 'var(--danger)', fontSize: 12 }}>{error}</span>}
    </div>
  );
}

function StatusDot({ label, value }: { label: string; value: number }) {
  return (
    <span style={{ color: 'var(--text-secondary)', fontSize: 12, fontWeight: 650, whiteSpace: 'nowrap' }}>
      {label} <span style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </span>
  );
}

function DebugRow({ label, value, danger }: { label: string; value: ReactNode; danger?: boolean }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '64px minmax(0, 1fr)', gap: 10, alignItems: 'baseline' }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 11.5 }}>{label}</div>
      <div style={{
        color: danger ? 'var(--danger)' : 'var(--text-secondary)', fontSize: 12.5,
        lineHeight: 1.35, overflowWrap: 'anywhere',
      }}>
        {value}
      </div>
    </div>
  );
}

function AssignmentsExplorer({
  items,
  selected,
  onSelect,
  busyId,
  updateStatus,
  t,
}: {
  items: RuleAssignment[];
  selected: RuleAssignment | null;
  onSelect: (id: string) => void;
  busyId: string | null;
  updateStatus: (id: string, status: string) => void;
  t: TFn;
}) {
  if (items.length === 0) {
    return (
      <div className="card" style={{ padding: '22px 18px', color: 'var(--text-secondary)', fontSize: 13 }}>
        {t('regulations.empty')}
      </div>
    );
  }

  // Order: active first (by urgency), then resolved.
  const urgencyRank = (u: string) => (u === 'high' ? 0 : u === 'medium' ? 1 : 2);
  const sorted = [...items].sort((a, b) => {
    const aActive = a.status === 'active' ? 0 : 1;
    const bActive = b.status === 'active' ? 0 : 1;
    if (aActive !== bActive) return aActive - bActive;
    return urgencyRank(a.urgency) - urgencyRank(b.urgency);
  });

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 360px), 1fr))',
      gap: 0, alignItems: 'start',
      border: '1px solid var(--border-color)', borderRadius: 'var(--radius)', overflow: 'hidden',
      background: 'var(--bg-card)',
    }}>
      {/* Left: X-style feed of obligations — hairline dividers, no nested boxes */}
      <div style={{ borderRight: '1px solid var(--border-color)' }}>
        {sorted.map((item, idx) => (
          <RegulationRow
            key={item.id}
            item={item}
            active={selected?.id === item.id}
            last={idx === sorted.length - 1}
            onSelect={() => onSelect(item.id)}
            statusLabel={t(`regulations.statusLabel.${item.status}`, item.status)}
            urgencyLabel={t(`regulations.urgency.${item.urgency}`, item.urgency)}
          />
        ))}
      </div>

      {/* Right: detail pane for the selected obligation */}
      {selected ? (
        <RegulationDetail
          key={selected.id}
          item={selected}
          busy={busyId === selected.id}
          updateStatus={updateStatus}
          t={t}
        />
      ) : (
        <DetailPlaceholder t={t} />
      )}
    </div>
  );
}

function RegulationRow({
  item,
  active,
  last,
  onSelect,
  statusLabel,
  urgencyLabel,
}: {
  item: RuleAssignment;
  active: boolean;
  last: boolean;
  onSelect: () => void;
  statusLabel: string;
  urgencyLabel: string;
}) {
  const tone = urgencyColor(item.urgency);
  const resolved = item.status !== 'active';
  return (
    <button
      onClick={onSelect}
      className="reg-feed-row"
      data-active={active ? 'true' : undefined}
      style={{
        display: 'block', width: '100%', textAlign: 'left',
        padding: '14px 18px', border: 'none', cursor: 'pointer',
        background: active ? 'var(--accent-subtle)' : 'transparent',
        borderBottom: last ? 'none' : '1px solid var(--border-color)',
        borderLeft: `2px solid ${active ? tone : 'transparent'}`,
        opacity: resolved ? 0.55 : 1,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: tone, flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 700, color: tone, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {urgencyLabel}
        </span>
        {item.blocking && !resolved && (
          <span style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
            <Ban size={11.5} strokeWidth={2.2} /> blocking
          </span>
        )}
        {resolved && (
          <span style={{ marginLeft: 'auto', fontSize: 10.5, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {statusLabel}
          </span>
        )}
      </div>
      <div style={{
        fontSize: 13.5, fontWeight: 550, color: 'var(--text-primary)', lineHeight: 1.45,
        letterSpacing: '-0.01em',
        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      }}>
        {item.rule_text}
      </div>
      {item.deadline && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 7, fontSize: 12, color: 'var(--text-muted)' }}>
          <Clock size={12} strokeWidth={2} />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.deadline}</span>
        </div>
      )}
    </button>
  );
}

function DetailPlaceholder({ t }: { t: TFn }) {
  return (
    <div style={{
      padding: '32px 20px', textAlign: 'center', display: 'flex', flexDirection: 'column',
      alignItems: 'center', gap: 12, minHeight: 360, justifyContent: 'center',
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--accent-subtle)', color: 'var(--accent)',
      }}>
        <FileText size={22} />
      </div>
      <div style={{ color: 'var(--text-primary)', fontWeight: 650, fontSize: 15 }}>{t('regulations.selectPrompt')}</div>
    </div>
  );
}

function RegulationDetail({
  item,
  busy,
  updateStatus,
  t,
}: {
  item: RuleAssignment;
  busy: boolean;
  updateStatus: (id: string, status: string) => void;
  t: TFn;
}) {
  const tone = urgencyColor(item.urgency);
  const parsed = useMemo(() => parseReason(item.reason), [item.reason]);
  const resolved = item.status !== 'active';

  return (
    <div style={{ position: 'sticky', top: 12 }}>
      <div style={{ padding: '22px 26px 26px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5,
            fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: tone,
          }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: tone }} />
            {t(`regulations.urgency.${item.urgency}`, item.urgency)}
          </span>
          <span style={{ color: 'var(--border-strong)' }}>·</span>
          <span style={{
            fontSize: 11.5, fontWeight: 600, color: resolved ? 'var(--text-muted)' : 'var(--success)',
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}>
            {t(`regulations.statusLabel.${item.status}`, item.status)}
          </span>
        </div>

        <div style={{ fontSize: 19, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4, letterSpacing: '-0.02em' }}>
          {item.rule_text}
        </div>

        <div style={{
          marginTop: 18, padding: '14px 16px', borderRadius: 12,
          background: `color-mix(in srgb, ${tone} 7%, var(--bg-secondary))`,
          border: `1px solid color-mix(in srgb, ${tone} 22%, transparent)`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8, color: tone, fontSize: 11.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            <Lightbulb size={14} strokeWidth={2.2} />
            {t('regulations.whyApplies')}
          </div>
          <div style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {parsed.condition ? (
              <>
                <code style={{
                  fontSize: 13, padding: '1px 7px', borderRadius: 6, fontFamily: 'ui-monospace, monospace',
                  background: 'var(--bg-tertiary)', color: 'var(--text-primary)', whiteSpace: 'nowrap',
                }}>{parsed.condition}</code>
              </>
            ) : (
              parsed.prose
            )}
          </div>

          {parsed.facts.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginTop: 12 }}>
              {parsed.facts.map(f => (
                <span key={f.key} style={{
                  display: 'inline-flex', alignItems: 'baseline', gap: 6, padding: '5px 11px', borderRadius: 99,
                  background: 'var(--bg-card)', border: '1px solid var(--border-color)',
                }}>
                  <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{f.key}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{f.value}</span>
                </span>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginTop: 22 }}>
          <FactRow label={t('regulations.deadline')} accent={tone}>{item.deadline}</FactRow>
          <FactRow label={t('regulations.consequence')} accent="var(--warning)">{item.consequence}</FactRow>
          <FactRow label={t('regulations.appliesTo')}>{item.applies_to}</FactRow>
          <FactRow label={t('regulations.trigger')}>{item.trigger}</FactRow>
          <FactRow label={t('regulations.authority')}>{item.authority}</FactRow>
          {(item.source_url || item.evidence_quote) && (
            <FactRow label={t('regulations.source', 'Source')}>
              <SourceProof sourceUrl={item.source_url} evidenceQuote={item.evidence_quote} />
            </FactRow>
          )}
          {item.blocking && (
            <FactRow label={t('regulations.blocking')} accent="var(--danger)">Blocks action</FactRow>
          )}
        </div>

        {!resolved && (
          <div style={{ display: 'flex', gap: 8, marginTop: 22 }}>
            <button
              className="btn btn-accent"
              disabled={busy}
              onClick={() => updateStatus(item.id, 'actioned')}
              style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, justifyContent: 'center', height: 42, borderRadius: 99 }}
            >
              <Check size={15} strokeWidth={2.2} />
              {t('regulations.markActioned')}
            </button>
            <button
              className="btn btn-ghost"
              disabled={busy}
              onClick={() => updateStatus(item.id, 'dismissed')}
              style={{ display: 'flex', alignItems: 'center', gap: 6, height: 42, borderRadius: 99, padding: '0 18px' }}
            >
              <X size={15} strokeWidth={2.2} />
              {t('regulations.dismiss')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function FactRow({ label, accent, children }: { label: string; accent?: string; children: ReactNode }) {
  if (children == null || children === '') return null;
  return (
    <div style={{ display: 'flex', gap: 16, padding: '12px 0', borderTop: '1px solid var(--border-color)' }}>
      <div style={{
        flexShrink: 0, width: 92, fontSize: 11, color: 'var(--text-muted)',
        textTransform: 'uppercase', letterSpacing: '0.04em', paddingTop: 1,
      }}>
        {label}
      </div>
      <div style={{ fontSize: 13.5, color: accent ?? 'var(--text-primary)', lineHeight: 1.5, minWidth: 0 }}>
        {children}
      </div>
    </div>
  );
}

function SourceProof({
  sourceUrl,
  evidenceQuote,
}: {
  sourceUrl?: string | null;
  evidenceQuote?: string | null;
}) {
  if (!sourceUrl && !evidenceQuote) return null;
  return (
    <div style={{ display: 'grid', gap: 7 }}>
      {sourceUrl && (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noreferrer"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5, width: 'fit-content',
            color: 'var(--accent)', fontSize: 12.5, fontWeight: 750, textDecoration: 'none',
          }}
        >
          Source <ExternalLink size={12} strokeWidth={2.2} />
        </a>
      )}
      {evidenceQuote && (
        <span style={{
          color: 'var(--text-secondary)', fontSize: 12.5, lineHeight: 1.45,
          display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>
          {evidenceQuote}
        </span>
      )}
    </div>
  );
}

function AgentTrace({
  running,
  error,
  steps,
  decisions,
  effects,
  summary,
  applicableCount,
  onRun,
}: {
  running: boolean;
  error: string | null;
  steps: TraceStep[];
  decisions: RuleDecision[];
  effects: AssignmentEffect[];
  summary: CheckSummary | null;
  applicableCount: number;
  onRun: () => void;
}) {
  const lastStep = steps[steps.length - 1];
  return (
    <div style={{ border: '1px solid var(--border-color)', borderRadius: 'var(--radius)', background: 'var(--bg-card)', overflow: 'hidden' }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        padding: '12px 14px', borderBottom: '1px solid var(--border-color)', flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <Activity size={15} color="var(--accent)" />
          <span style={{ color: 'var(--text-primary)', fontWeight: 750, fontSize: 14 }}>Check</span>
          <span style={{ color: 'var(--text-muted)', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {lastStep ? lastStep.message : 'ready'}
          </span>
        </div>
        <button className="btn btn-accent" onClick={onRun} disabled={running} style={{ height: 34, display: 'inline-flex', alignItems: 'center', gap: 7 }}>
          <RefreshCw size={14} style={{ animation: running ? 'cw-spin 0.9s linear infinite' : undefined }} />
          {running ? 'Run...' : 'Run'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '10px 14px', borderBottom: '1px solid var(--border-color)' }}>
        <MiniMetric label="checked" value={summary?.rules_checked ?? decisions.length} />
        <MiniMetric label="applies" value={summary?.applicable ?? applicableCount} />
        <MiniMetric label="new" value={summary?.created ?? effects.filter(e => e.action === 'created').length} />
        <MiniMetric label="changed" value={summary ? summary.updated + summary.reactivated + (summary.retired ?? 0) : effects.filter(e => e.action !== 'created' && e.action !== 'unchanged').length} />
        {error && <span style={{ color: 'var(--danger)', fontSize: 12, alignSelf: 'center' }}>{error}</span>}
      </div>

      <ReasoningExplorer decisions={decisions} applicableCount={applicableCount} />

      <AffectedStrip
        effects={effects}
        running={running}
        summary={summary}
        applicableCount={applicableCount}
      />
    </div>
  );
}

type DecisionFilter = 'all' | 'applies' | 'miss' | 'held';

function MiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'baseline', gap: 5, color: 'var(--text-secondary)',
      fontSize: 12, fontWeight: 650,
    }}>
      <span style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums', fontWeight: 850 }}>{value}</span>
      {label}
    </span>
  );
}

function AffectedStrip({
  effects,
  running,
  summary,
  applicableCount,
}: {
  effects: AssignmentEffect[];
  running: boolean;
  summary: CheckSummary | null;
  applicableCount: number;
}) {
  return (
    <div style={{ borderTop: '1px solid var(--border-color)', padding: '10px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: effects.length > 0 ? 8 : 0 }}>
        <CheckCircle2 size={15} color="var(--success)" />
        <span style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: 13 }}>Updates</span>
        {effects.length === 0 && (
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            {affectedEmptyMessage({ running, summary, applicableCount })}
          </span>
        )}
      </div>
      {effects.length > 0 && (
        <div style={{ display: 'grid' }}>
          {effects.map(effect => {
            const tone = urgencyColor(effect.urgency);
            return (
              <div key={`${effect.assignment_id}-${effect.action}`} style={{
                display: 'grid', gridTemplateColumns: '92px minmax(0, 1fr) auto', gap: 10,
                alignItems: 'baseline', padding: '8px 0', borderTop: '1px solid var(--border-color)',
              }}>
                <span style={{ color: tone, fontSize: 11, fontWeight: 850, textTransform: 'uppercase' }}>{actionLabel(effect.action)}</span>
                <span style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 650, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {effect.rule_text}
                </span>
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{effect.status}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ReasoningExplorer({
  decisions,
  applicableCount,
}: {
  decisions: RuleDecision[];
  applicableCount: number;
}) {
  const [filter, setFilter] = useState<DecisionFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const visible = useMemo(() => {
    switch (filter) {
      case 'applies':
        return decisions.filter(d => d.applies);
      case 'miss':
        return decisions.filter(d => !d.applies && d.persistable !== false);
      case 'held':
        return decisions.filter(d => d.persistable === false);
      default:
        return decisions;
    }
  }, [decisions, filter]);

  useEffect(() => {
    if (visible.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !visible.some(d => d.rule_id === selectedId)) {
      setSelectedId(visible[0].rule_id);
    }
  }, [visible, selectedId]);

  const selected = visible.find(d => d.rule_id === selectedId) ?? visible[0] ?? null;
  const noMatchCount = decisions.filter(d => !d.applies && d.persistable !== false).length;
  const heldCount = decisions.filter(d => d.persistable === false).length;

  return (
    <div style={{
      background: 'var(--bg-card)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        padding: '15px 16px', borderBottom: '1px solid var(--border-color)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={16} color="var(--accent)" />
          <div>
            <div style={{ color: 'var(--text-primary)', fontWeight: 700 }}>Reasoning</div>
          </div>
        </div>
      </div>

      <div style={{
        display: 'flex', gap: 6, padding: '10px 12px', borderBottom: '1px solid var(--border-color)',
        flexWrap: 'wrap',
      }}>
        <FilterChip active={filter === 'all'} onClick={() => setFilter('all')}>All {decisions.length}</FilterChip>
        <FilterChip active={filter === 'applies'} onClick={() => setFilter('applies')}>Yes {applicableCount}</FilterChip>
        <FilterChip active={filter === 'miss'} onClick={() => setFilter('miss')}>No {noMatchCount}</FilterChip>
        <FilterChip active={filter === 'held'} onClick={() => setFilter('held')}>Held {heldCount}</FilterChip>
      </div>

      {decisions.length === 0 ? (
        <div style={{ padding: 18, color: 'var(--text-muted)', fontSize: 13 }}>
          Run check.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))' }}>
          <div style={{ borderRight: '1px solid var(--border-color)' }}>
            {visible.length === 0 ? (
              <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 13 }}>None.</div>
            ) : visible.map((decision, index) => (
              <DecisionRow
                key={decision.rule_id}
                decision={decision}
                active={selected?.rule_id === decision.rule_id}
                last={index === visible.length - 1}
                onSelect={() => setSelectedId(decision.rule_id)}
              />
            ))}
          </div>

          <DecisionDetail decision={selected} />
        </div>
      )}
    </div>
  );
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="btn"
      style={{
        height: 30, padding: '0 11px', borderRadius: 999, fontSize: 12, fontWeight: 700,
        background: active ? 'var(--accent-subtle)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--text-secondary)',
        border: active ? '1px solid color-mix(in srgb, var(--accent) 28%, transparent)' : '1px solid var(--border-color)',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </button>
  );
}

function DecisionRow({
  decision,
  active,
  last,
  onSelect,
}: {
  decision: RuleDecision;
  active: boolean;
  last: boolean;
  onSelect: () => void;
}) {
  const tone = decision.persistable === false ? 'var(--warning)' : decisionTone(decision.applies);
  const label = decision.persistable === false ? 'held' : decision.applies ? 'applies' : 'no match';

  return (
    <button
      type="button"
      onClick={onSelect}
      className="reg-feed-row"
      data-active={active ? 'true' : undefined}
      style={{
        display: 'block', width: '100%', textAlign: 'left', border: 'none',
        borderBottom: last ? 'none' : '1px solid var(--border-color)',
        borderLeft: `2px solid ${active ? tone : 'transparent'}`,
        background: active ? 'var(--accent-subtle)' : 'transparent',
        padding: '13px 15px', cursor: 'pointer',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 9, alignItems: 'center', marginBottom: 6 }}>
        <span style={{ color: tone, fontSize: 10.5, fontWeight: 850, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{decision.match_type}</span>
      </div>
      <div style={{
        color: 'var(--text-primary)', fontSize: 13, fontWeight: 650, lineHeight: 1.38,
        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      }}>
        {decision.rule_text}
      </div>
      <div style={{
        marginTop: 6, color: 'var(--text-muted)', fontSize: 12, lineHeight: 1.38,
        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      }}>
        {decision.reason || 'No reason.'}
      </div>
    </button>
  );
}

function DecisionDetail({ decision }: { decision: RuleDecision | null }) {
  if (!decision) {
    return (
      <div style={{ padding: 28, color: 'var(--text-muted)', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        Select one.
      </div>
    );
  }

  const tone = decision.persistable === false ? 'var(--warning)' : decisionTone(decision.applies);
  const status = decision.persistable === false ? 'held' : decision.applies ? 'applies' : 'no match';

  return (
    <div style={{ padding: 18, position: 'sticky', top: 12, alignSelf: 'start' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 13 }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: tone, flexShrink: 0 }} />
        <span style={{ color: tone, fontSize: 11, fontWeight: 850, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          {status}
        </span>
      </div>

      <div style={{ color: 'var(--text-primary)', fontSize: 18, fontWeight: 700, lineHeight: 1.35 }}>
        {decision.rule_text}
      </div>

      <div style={{
        marginTop: 18, padding: '14px 0', borderTop: '1px solid var(--border-color)',
        borderBottom: '1px solid var(--border-color)',
      }}>
        <div style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 750, marginBottom: 7 }}>Why</div>
        <div style={{ color: 'var(--text-secondary)', fontSize: 13.5, lineHeight: 1.58 }}>
          {decision.reason || 'No reason.'}
        </div>
      </div>

      {(decision.source_url || decision.evidence_quote) && (
        <div style={{ padding: '12px 0', borderBottom: '1px solid var(--border-color)' }}>
          <SourceProof sourceUrl={decision.source_url} evidenceQuote={decision.evidence_quote} />
        </div>
      )}

      <div style={{ display: 'grid', gap: 8, marginTop: 16 }}>
        <DebugRow label="Type" value={decision.match_type} />
        <DebugRow label="Scope" value={decision.applies_to || '-'} />
        <DebugRow label="Trigger" value={decision.trigger || '-'} />
        <DebugRow label="Due" value={decision.deadline || '-'} />
        <DebugRow label="Risk" value={decision.consequence || '-'} />
        <DebugRow label="Block" value={decision.blocking ? 'yes' : 'no'} />
        <DebugRow label="Save" value={decision.persistable === false ? 'held' : 'yes'} />
      </div>
    </div>
  );
}

function affectedEmptyMessage({
  running,
  summary,
  applicableCount,
}: {
  running: boolean;
  summary: CheckSummary | null;
  applicableCount: number;
}): string {
  if (running && applicableCount > 0) {
    return `${applicableCount} matched; saving...`;
  }
  if (running) {
    return 'Waiting...';
  }
  if (summary && summary.applicable > 0) {
    return `${summary.applicable} matched; no changes.`;
  }
  if (summary) {
    return 'No matches.';
  }
  return 'No changes.';
}
