import { useState, useEffect, useRef } from 'react';
import { ClipboardList, Upload, CheckCircle, XCircle, Clock, Flag, ChevronLeft, ChevronRight, Activity, FileText } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

const REVIEW_CSS = `
@keyframes sa-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes sa-slide { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@keyframes sa-spin { to { transform: rotate(360deg); } }
.sa-spinner { width: 26px; height: 26px; border-radius: 50%; border: 3px solid var(--border-color); border-top-color: var(--accent); animation: sa-spin 0.7s linear infinite; }
.sa-spinner-sm { width: 16px; height: 16px; border-width: 2px; }
`;

const REVIEW_STORAGE_KEY = 'orbis_assignment_reviews';

type TimelineStep = { label: string; detail?: string; t: number };

type StoredReview = {
  status: 'approved' | 'rejected' | 'flagged';
  feedback: string;
  filename?: string;
  reviewed_at: string;
  requirements: string[];
  findings: Array<{ requirement?: string; satisfied?: boolean; evidence?: string; evidence_line?: number; reasoning?: string }>;
  timeline?: TimelineStep[];
  source_text?: string;
  source_truncated?: boolean;
  submission_id?: number;
  can_flag_rejection?: boolean;
};

function loadReviews(): Record<string, StoredReview> {
  try {
    return JSON.parse(localStorage.getItem(REVIEW_STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

function saveReview(assignmentId: number, review: StoredReview) {
  const all = loadReviews();
  all[String(assignmentId)] = review;
  try {
    localStorage.setItem(REVIEW_STORAGE_KEY, JSON.stringify(all));
  } catch { /* quota — ignore */ }
}

function getStoredReview(assignmentId: number): StoredReview | null {
  return loadReviews()[String(assignmentId)] ?? null;
}

interface Submission {
  id: number;
  status: 'pending' | 'approved' | 'rejected' | 'flagged';
  ai_feedback: string;
  submitted_at: string;
  original_filename: string;
  evaluation_report?: EvaluationReport | null;
  flagged_by_student?: boolean;
  student_flag_reason?: string | null;
  flagged_at?: string | null;
}

interface Assignment {
  id: number;
  title: string;
  description: string | null;
  due_date: string;
  max_points: number;
  section_id: number;
  submission: Submission | null;
}

interface SubmitResult {
  submission_id: number;
  status: 'approved' | 'rejected' | 'flagged';
  ai_feedback: string;
  evaluation_report?: EvaluationReport;
  can_flag_rejection?: boolean;
}

interface EvaluationReport {
  file?: {
    size_kb?: number;
    line_count?: number;
    extraction_method?: string;
    archive_entries?: Array<{ path: string; read: boolean; reason: string | null }>;
  };
  llm?: {
    parsed?: {
      confidence?: number;
      assignment_understanding?: string;
      submission_summary?: string;
      requirement_findings?: Array<{
        requirement?: string;
        satisfied?: boolean;
        evidence_line?: number;
        evidence?: string;
        reasoning?: string;
      }>;
      evidence?: Array<{ line?: number; quote?: string; why_it_matters?: string }>;
      missing_requirements?: string[];
      flags?: string[];
    };
  };
}

function StatusBadge({ status }: { status: Submission['status'] }) {
  const colors: Record<string, string> = {
    approved: '#22c55e',
    rejected: '#ef4444',
    pending: '#f59e0b',
    flagged: '#8b5cf6',
  };
  const icons = {
    approved: <CheckCircle size={14} strokeWidth={2} />,
    rejected: <XCircle size={14} strokeWidth={2} />,
    pending: <Clock size={14} strokeWidth={2} />,
    flagged: <Flag size={14} strokeWidth={2} />,
  };
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: '2px 10px',
      borderRadius: 12,
      backgroundColor: colors[status] + '22',
      color: colors[status],
      fontSize: 12,
      fontWeight: 600,
    }}>
      {icons[status]}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

const PHASE_INDEX: Record<string, number> = {
  inspecting: 0, inspected: 0,
  understanding: 1, requirements: 1,
  judging: 2, token: 2, finding: 2,
  verdict: 3, result: 3, complete: 3,
};
const PHASE_CAPTION: Record<string, string> = {
  inspecting: 'Reading your file…',
  inspected: 'Reading the assignment brief…',
  understanding: 'Listing the requirements…',
  requirements: 'Checking your work against each requirement…',
  judging: 'Checking your work against each requirement…',
  token: 'Reviewing…',
  finding: 'Recording results…',
  verdict: 'Finishing up…',
};

type Finding = { requirement?: string; satisfied?: boolean; evidence?: string; evidence_line?: number; reasoning?: string };

function RequirementList({ requirements, findings, live, activeIndex, onSelect, hasSource }: {
  requirements: string[]; findings: Finding[]; live: boolean;
  activeIndex?: number; onSelect?: (i: number, f: Finding) => void; hasSource?: boolean;
}) {
  if (requirements.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {requirements.map((r, i) => {
        const f = findings.find(x => x.requirement === r) ?? findings[i];
        const checked = i < findings.length;
        const ok = f?.satisfied;
        const clickable = checked && hasSource && !!f;
        const isActive = activeIndex === i;
        return (
          <div
            key={i}
            onClick={clickable ? () => onSelect?.(i, f as Finding) : undefined}
            style={{
              display: 'flex', gap: 12, padding: '14px 12px', margin: '0 -12px', borderRadius: 10,
              borderTop: i === 0 ? 'none' : '1px solid var(--border-color)',
              opacity: checked || !live ? 1 : 0.45, transition: 'all 0.15s ease',
              cursor: clickable ? 'pointer' : 'default',
              background: isActive ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'transparent',
            }}
            onMouseEnter={e => { if (clickable && !isActive) (e.currentTarget as HTMLElement).style.background = 'var(--bg-tertiary)'; }}
            onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
          >
            <div style={{ flexShrink: 0, marginTop: 1, color: checked ? (ok ? '#22c55e' : '#ef4444') : 'var(--text-muted)' }}>
              {checked ? (ok ? <CheckCircle size={18} /> : <XCircle size={18} />) : (live ? <span className="sa-spinner sa-spinner-sm" /> : <Clock size={16} />)}
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ color: 'var(--text-primary)', fontWeight: 500, fontSize: 14, lineHeight: 1.45, flex: 1 }}>{r}</div>
                {clickable && <ChevronRight size={15} style={{ color: isActive ? 'var(--accent)' : 'var(--text-muted)', flexShrink: 0 }} />}
              </div>
              {checked && f?.reasoning && (
                <div style={{ color: 'var(--text-secondary)', marginTop: 4, fontSize: 13, lineHeight: 1.5 }}>{f.reasoning}</div>
              )}
              {checked && f?.evidence && (
                <div style={{ color: 'var(--text-muted)', marginTop: 4, fontSize: 12.5, lineHeight: 1.45 }}>
                  {f.evidence_line ? `Line ${f.evidence_line}: ` : ''}{f.evidence}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function WorkTrail({ steps, running }: { steps: TimelineStep[]; running: boolean }) {
  return (
    <aside style={{
      width: 340, flexShrink: 0, alignSelf: 'stretch',
      borderRight: '1px solid var(--border-color)', background: 'var(--bg-secondary)',
      padding: '28px 24px', overflowY: 'auto',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Activity size={15} style={{ color: 'var(--accent)' }} />
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.7, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
          Agent work
        </span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 22 }}>
        {running ? 'Working through your submission' : `${steps.length} steps`}
      </div>

      {steps.length === 0 && !running && (
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No activity recorded.</div>
      )}

      <div style={{ position: 'relative' }}>
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1;
          const live = running && isLast;
          return (
            <div key={i} style={{ position: 'relative', paddingLeft: 26, paddingBottom: isLast ? 0 : 20, animation: 'sa-slide 0.25s ease' }}>
              {/* connector line */}
              {!isLast && (
                <span style={{ position: 'absolute', left: 7, top: 16, bottom: 0, width: 2, background: 'var(--border-color)' }} />
              )}
              {/* node */}
              <span style={{
                position: 'absolute', left: 0, top: 2, width: 16, height: 16, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: live ? 'var(--accent)' : 'color-mix(in srgb, var(--accent) 18%, transparent)',
                boxShadow: live ? '0 0 0 4px color-mix(in srgb, var(--accent) 18%, transparent)' : 'none',
              }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: live ? '#fff' : 'var(--accent)' }} />
              </span>
              <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4 }}>{s.label}</div>
              {s.detail && <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', marginTop: 2, lineHeight: 1.45 }}>{s.detail}</div>}
            </div>
          );
        })}
        {running && (
          <div style={{ paddingLeft: 26, marginTop: 4, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 12.5 }}>
            <span className="sa-spinner sa-spinner-sm" style={{ width: 13, height: 13 }} /> working…
          </div>
        )}
      </div>
    </aside>
  );
}

// Locate where a finding's evidence appears in the source text.
// Returns [start, end] character offsets, or null if not found.
function locateEvidence(source: string, finding: Finding | null): [number, number] | null {
  if (!source || !finding) return null;
  const norm = (s: string) => s.replace(/\s+/g, ' ').trim().toLowerCase();
  const ev = (finding.evidence || '').trim();
  // 1) try to match the quoted evidence text (whitespace-insensitive)
  if (ev && ev.length >= 4 && !/^no\b/i.test(ev)) {
    const haystack = norm(source);
    // build a few candidate needles: full, then a leading chunk
    const candidates = [ev, ev.slice(0, 60), ev.split(/[.;,]/)[0]].map(norm).filter(c => c.length >= 4);
    for (const needle of candidates) {
      const idx = haystack.indexOf(needle);
      if (idx === -1) continue;
      // map normalized index back to original by walking and counting non-space runs
      return mapNormToOriginal(source, idx, needle.length);
    }
  }
  // 2) fall back to the cited line number
  const ln = finding.evidence_line;
  if (ln && ln > 0) {
    const lines = source.split('\n');
    if (ln <= lines.length) {
      let start = 0;
      for (let i = 0; i < ln - 1; i++) start += lines[i].length + 1;
      return [start, start + lines[ln - 1].length];
    }
  }
  return null;
}

// Map an index in the whitespace-collapsed string back to original offsets.
function mapNormToOriginal(source: string, normStart: number, normLen: number): [number, number] {
  let normCount = 0, origStart = -1, origEnd = -1, prevSpace = false;
  for (let i = 0; i < source.length; i++) {
    const isSpace = /\s/.test(source[i]);
    let contributes = true;
    if (isSpace) { if (prevSpace) contributes = false; }
    prevSpace = isSpace;
    if (contributes) {
      if (normCount === normStart && origStart === -1) origStart = i;
      if (normCount === normStart + normLen) { origEnd = i; break; }
      normCount++;
    }
  }
  if (origStart === -1) origStart = 0;
  if (origEnd === -1) origEnd = Math.min(source.length, origStart + normLen + 20);
  return [origStart, origEnd];
}

function SourceViewer({ source, truncated, filename, active }: {
  source: string; truncated?: boolean; filename?: string; active: Finding | null;
}) {
  const markRef = useRef<HTMLSpanElement>(null);
  const span = locateEvidence(source, active);

  useEffect(() => {
    if (markRef.current) markRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [active]);

  let body: React.ReactNode;
  if (span) {
    const [s, e] = span;
    body = (
      <>
        {source.slice(0, s)}
        <span ref={markRef} style={{ background: 'color-mix(in srgb, var(--accent) 32%, transparent)', borderRadius: 3, boxShadow: '0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent)' }}>
          {source.slice(s, e)}
        </span>
        {source.slice(e)}
      </>
    );
  } else {
    body = source;
  }

  return (
    <aside style={{
      width: 420, flexShrink: 0, alignSelf: 'stretch', borderLeft: '1px solid var(--border-color)',
      background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column',
    }}>
      <div style={{ padding: '18px 20px 12px', borderBottom: '1px solid var(--border-color)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={15} style={{ color: 'var(--accent)' }} />
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.7, textTransform: 'uppercase', color: 'var(--text-muted)' }}>Source</span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600, marginTop: 6, wordBreak: 'break-all' }}>{filename}</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          {active ? (span ? 'Highlighting the referenced passage' : 'No exact match — showing full text') : 'Click a requirement to jump to its reference'}
        </div>
      </div>
      <pre style={{
        flex: 1, overflowY: 'auto', margin: 0, padding: '16px 20px',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12, lineHeight: 1.6,
        color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      }}>
        {body}
        {truncated && <div style={{ marginTop: 16, color: 'var(--text-muted)', fontStyle: 'italic' }}>… (truncated)</div>}
      </pre>
    </aside>
  );
}

function ReviewExperience({ assignment, initialReview, onBack, onSaved }: {
  assignment: Assignment;
  initialReview: StoredReview | null;
  onBack: () => void;
  onSaved: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [phase, setPhase] = useState<string>('');
  const [requirements, setRequirements] = useState<string[]>(initialReview?.requirements ?? []);
  const [findings, setFindings] = useState<Finding[]>(initialReview?.findings ?? []);
  const [review, setReview] = useState<StoredReview | null>(initialReview);
  const [timeline, setTimeline] = useState<TimelineStep[]>(initialReview?.timeline ?? []);
  const [sourceText, setSourceText] = useState<string>(initialReview?.source_text ?? '');
  const [sourceTruncated, setSourceTruncated] = useState<boolean>(initialReview?.source_truncated ?? false);
  const [activeReq, setActiveReq] = useState<number | null>(null);
  const [activeFinding, setActiveFinding] = useState<Finding | null>(null);
  const [flagReason, setFlagReason] = useState('');
  const [flagging, setFlagging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const caption = PHASE_CAPTION[phase] ?? '';
  const showResults = !!review && !uploading;

  const handleSubmit = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    setPhase('');
    setRequirements([]);
    setFindings([]);
    setReview(null);
    setTimeline([]);
    setSourceText('');
    setActiveReq(null);
    setActiveFinding(null);
    let src = '';
    let srcTrunc = false;
    const trail: TimelineStep[] = [];
    const log = (label: string, detail?: string) => {
      trail.push({ label, detail, t: Date.now() });
      setTimeline([...trail]);
    };
    try {
      let finalResult: SubmitResult | null = null;
      let liveReqs: string[] = [];
      let liveFindings: Finding[] = [];
      let checkedLogged = 0;
      await api.submitAssignmentStream(assignment.id, file, (type, data) => {
        if (type === 'inspecting') {
          log('Reading the document', file.name);
        } else if (type === 'inspected') {
          log('Document read', `${(data.line_count ?? 0)} lines · ${(data.extracted_chars ?? 0).toLocaleString()} characters`);
          src = data.extracted_text || '';
          srcTrunc = !!data.extracted_truncated;
          setSourceText(src);
          setSourceTruncated(srcTrunc);
        } else if (type === 'understanding') {
          log('Studying the assignment brief');
        } else if (type === 'requirements') {
          liveReqs = data.requirements || [];
          setRequirements(liveReqs);
          log('Identified requirements', `${liveReqs.length} to check`);
        } else if (type === 'judging') {
          log('Checking work against each requirement');
        } else if (type === 'finding') {
          liveFindings = [...liveFindings, data.finding];
          setFindings(liveFindings);
          checkedLogged = liveFindings.length;
          // collapse per-finding noise into a single updating step
          const last = trail[trail.length - 1];
          if (last && last.label === 'Reviewing requirements') {
            last.detail = `${checkedLogged}/${liveReqs.length || '?'} checked`;
            last.t = Date.now();
            setTimeline([...trail]);
          } else {
            log('Reviewing requirements', `${checkedLogged}/${liveReqs.length || '?'} checked`);
          }
        } else if (type === 'verdict') {
          log('Reached a verdict', data.decision ? String(data.decision) : undefined);
        } else if (type === 'result') {
          finalResult = data as SubmitResult;
        } else if (type === 'error') {
          throw new Error(data.detail || 'Evaluation failed');
        }
        if (PHASE_INDEX[type] !== undefined) setPhase(type);
      });
      if (finalResult) {
        const r = finalResult as SubmitResult;
        const stored: StoredReview = {
          status: r.status,
          feedback: r.ai_feedback,
          filename: file.name,
          reviewed_at: new Date().toISOString(),
          requirements: liveReqs,
          findings: liveFindings,
          timeline: trail,
          source_text: src,
          source_truncated: srcTrunc,
          submission_id: r.submission_id,
          can_flag_rejection: r.can_flag_rejection,
        };
        saveReview(assignment.id, stored);
        setReview(stored);
        onSaved();
      } else {
        setError('The evaluation did not return a result.');
      }
    } catch (e: any) {
      setError(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleFlag = async () => {
    if (!review?.submission_id || flagging) return;
    setFlagging(true);
    try {
      await api.flagSubmissionRejection(review.submission_id, flagReason);
      const updated: StoredReview = { ...review, status: 'flagged', can_flag_rejection: false };
      saveReview(assignment.id, updated);
      setReview(updated);
      onSaved();
    } catch (e: any) {
      setError(e.message || 'Could not flag rejection');
    } finally {
      setFlagging(false);
    }
  };

  const satisfiedCount = findings.filter(f => f.satisfied).length;
  const running = uploading;
  const totalReqs = review ? review.requirements.length : requirements.length;
  const met = review ? review.findings.filter(f => f.satisfied).length : satisfiedCount;
  const statusColor = review?.status === 'approved' ? '#22c55e' : review?.status === 'rejected' ? '#ef4444' : review?.status === 'flagged' ? '#8b5cf6' : 'var(--text-muted)';

  const showTrail = running || timeline.length > 0;
  const showSource = showResults && !!sourceText;

  const selectReq = (i: number, f: Finding) => {
    if (activeReq === i) { setActiveReq(null); setActiveFinding(null); }
    else { setActiveReq(i); setActiveFinding(f); }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100%', height: '100%', animation: 'sa-fade 0.2s ease' }}>
      <style>{REVIEW_CSS}</style>

      {showTrail && <WorkTrail steps={timeline} running={running} />}

      <div style={{ flex: 1, minWidth: 0, margin: showSource ? 0 : '0 auto', maxWidth: showSource ? 'none' : 820, padding: '24px 36px 60px', overflowY: 'auto' }}>
      <button
        onClick={onBack}
        disabled={uploading}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, background: 'none', border: 'none',
          color: 'var(--text-muted)', cursor: uploading ? 'default' : 'pointer', fontSize: 13,
          padding: '4px 0', marginBottom: 18, opacity: uploading ? 0.4 : 1,
        }}
      >
        <ChevronLeft size={16} /> Back to assignments
      </button>

      {/* Header */}
      <h1 style={{ margin: 0, color: 'var(--text-primary)', fontSize: 22, fontWeight: 700, lineHeight: 1.3 }}>{assignment.title}</h1>
      <div style={{ marginTop: 6, fontSize: 13, color: 'var(--text-muted)' }}>
        Due {new Date(assignment.due_date).toLocaleDateString()} · {assignment.max_points} points
      </div>

      {/* IDLE: upload */}
      {!running && !showResults && !error && (
        <div style={{ marginTop: 24 }}>
          {assignment.description && (
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, marginTop: 0 }}>{assignment.description}</p>
          )}
          <div
            onClick={() => inputRef.current?.click()}
            style={{
              border: `1.5px dashed ${file ? 'var(--accent)' : 'var(--border-color)'}`, borderRadius: 12, padding: '40px 20px',
              textAlign: 'center', cursor: 'pointer', transition: 'border-color 0.15s ease', marginTop: 16,
            }}
          >
            <Upload size={30} strokeWidth={1.4} style={{ marginBottom: 10, color: file ? 'var(--accent)' : 'var(--text-muted)' }} />
            <div style={{ fontSize: 14, color: file ? 'var(--text-primary)' : 'var(--text-muted)' }}>
              {file ? file.name : 'Choose a file (PDF, DOCX, TXT, code, ZIP)'}
            </div>
            <input
              ref={inputRef} type="file"
              accept=".pdf,.docx,.txt,.md,.json,.csv,.py,.js,.jsx,.ts,.tsx,.java,.c,.cpp,.cs,.go,.rb,.rs,.html,.css,.zip,.tex,.bib,.ipynb"
              style={{ display: 'none' }}
              onChange={e => { const f = e.target.files?.[0]; if (f) setFile(f); }}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={!file}
            style={{
              marginTop: 16, padding: '10px 22px', borderRadius: 8, border: 'none',
              background: file ? 'var(--accent)' : 'var(--bg-tertiary)', color: file ? '#fff' : 'var(--text-muted)',
              cursor: file ? 'pointer' : 'default', fontSize: 14, fontWeight: 600,
            }}
          >
            Submit for review
          </button>
        </div>
      )}

      {/* RUNNING: single status line (the left trail carries the detail) */}
      {running && (
        <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', gap: 10, fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
          <span className="sa-spinner sa-spinner-sm" />
          {caption || 'Reviewing…'}
        </div>
      )}

      {/* RESULTS: status line */}
      {showResults && review && (
        <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', gap: 10 }}>
          {review.status === 'approved' ? <CheckCircle size={20} color={statusColor} /> : review.status === 'flagged' ? <Flag size={20} color={statusColor} /> : <XCircle size={20} color={statusColor} />}
          <span style={{ fontSize: 16, fontWeight: 700, color: statusColor }}>
            {review.status === 'approved' ? 'Approved' : review.status === 'flagged' ? 'Flagged' : 'Rejected'}
          </span>
          {totalReqs > 0 && <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>· {met}/{totalReqs} requirements met</span>}
        </div>
      )}
      {showResults && review && (
        <div style={{ marginTop: 6, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {review.feedback.replace(/^(APPROVED|REJECTED):\s*/i, '')}
        </div>
      )}

      {/* Requirements list (shared by running + results) */}
      {totalReqs > 0 && (
        <div style={{ marginTop: 22 }}>
          {showSource && (
            <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginBottom: 10 }}>
              Click any requirement to see exactly where it was checked in your file →
            </div>
          )}
          <RequirementList
            requirements={review ? review.requirements : requirements}
            findings={review ? review.findings : findings}
            live={running}
            hasSource={showSource}
            activeIndex={activeReq ?? undefined}
            onSelect={selectReq}
          />
        </div>
      )}

      {/* Pre-stream spinner */}
      {running && totalReqs === 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 22, color: 'var(--text-muted)', fontSize: 13 }}>
          <span className="sa-spinner sa-spinner-sm" /> Reading your submission…
        </div>
      )}

      {/* Result actions */}
      {showResults && review && (
        <div style={{ marginTop: 28 }}>
          {review.status === 'rejected' && review.can_flag_rejection && review.submission_id && (
            <div style={{ marginBottom: 20 }}>
              <textarea
                value={flagReason}
                onChange={e => setFlagReason(e.target.value)}
                placeholder="Disagree? Tell the instructor why (optional)"
                rows={2}
                style={{
                  width: '100%', boxSizing: 'border-box', resize: 'vertical', border: '1px solid var(--border-color)',
                  borderRadius: 8, background: 'var(--bg-tertiary)', color: 'var(--text-primary)', padding: 10, fontSize: 13, outline: 'none',
                }}
              />
              <button
                onClick={handleFlag} disabled={flagging}
                style={{
                  marginTop: 8, padding: '8px 16px', borderRadius: 8, border: '1px solid var(--border-color)',
                  background: 'transparent', color: flagging ? 'var(--text-muted)' : '#8b5cf6',
                  cursor: flagging ? 'default' : 'pointer', fontSize: 13, fontWeight: 600,
                }}
              >
                {flagging ? 'Flagging…' : 'Flag for review'}
              </button>
            </div>
          )}
          <button
            onClick={() => { setReview(null); setFile(null); setRequirements([]); setFindings([]); setTimeline([]); setError(''); }}
            style={{ padding: '10px 22px', borderRadius: 8, border: 'none', background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}
          >
            Submit a new file
          </button>
        </div>
      )}

      {error && (
        <div style={{ marginTop: 24, fontSize: 14, lineHeight: 1.55, color: '#ef4444' }}>
          {error}
          <div style={{ marginTop: 10 }}>
            <button
              onClick={() => setError('')}
              style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid var(--border-color)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}
            >
              Try again
            </button>
          </div>
        </div>
      )}
      </div>

      {showSource && (
        <SourceViewer source={sourceText} truncated={sourceTruncated} filename={review?.filename} active={activeFinding} />
      )}
    </div>
  );
}

export function AssignmentsPage() {
  const { user } = useAuth();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Assignment | null>(null);
  const [reviewsVersion, setReviewsVersion] = useState(0); // bump to re-read localStorage

  const load = () => {
    api.getMyAssignments().then((data: Assignment[]) => {
      setAssignments(data ?? []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    if (user?.userType !== 'student') { setLoading(false); return; }
    load();
  }, [user]);

  if (user?.userType !== 'student') {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
        This page is only available to students.
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
        Loading assignments…
      </div>
    );
  }

  // Full-page review experience takes over when a student opens an assignment.
  if (selected) {
    return (
      <ReviewExperience
        key={selected.id}
        assignment={selected}
        initialReview={getStoredReview(selected.id)}
        onBack={() => setSelected(null)}
        onSaved={() => { setReviewsVersion(v => v + 1); load(); }}
      />
    );
  }

  return (
    <div style={{ padding: 32 }}>
      <h2 style={{ marginBottom: 24, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <ClipboardList size={20} strokeWidth={1.8} />
        Assignments
      </h2>

      {assignments.length === 0 ? (
        <div style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: 40 }}>
          No pending assignments.
        </div>
      ) : (
        <div key={reviewsVersion} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {assignments.map(a => (
            <div
              key={a.id}
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                borderRadius: 12,
                padding: '18px 22px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                boxShadow: 'var(--shadow)',
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 15, marginBottom: 4 }}>
                  {a.title}
                </div>
                {a.description && (
                  <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {a.description}
                  </div>
                )}
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Due: {new Date(a.due_date).toLocaleDateString()} · {a.max_points} pts
                </div>
                {(() => {
                  const stored = getStoredReview(a.id);
                  const status = a.submission?.status ?? stored?.status;
                  const filename = a.submission?.original_filename ?? stored?.filename;
                  if (!status) return null;
                  return (
                    <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <StatusBadge status={status} />
                      {filename && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{filename}</span>}
                    </div>
                  );
                })()}
              </div>

              {(() => {
                const reviewed = !!getStoredReview(a.id) || !!a.submission;
                return (
                  <button
                    onClick={() => setSelected(a)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: 8,
                      border: '1px solid var(--accent)',
                      background: reviewed ? 'transparent' : 'var(--accent)',
                      color: reviewed ? 'var(--accent)' : '#fff',
                      cursor: 'pointer',
                      fontSize: 13,
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                      transition: 'all 0.15s ease',
                      flexShrink: 0,
                    }}
                  >
                    {reviewed ? 'View results' : 'Submit'}
                  </button>
                );
              })()}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
