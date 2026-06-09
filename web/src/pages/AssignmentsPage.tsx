import { useState, useEffect, useRef } from 'react';
import { ClipboardList, Upload, CheckCircle, XCircle, Clock, Flag, ChevronLeft, ChevronRight, Activity, FileText } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { PageHeader } from '../components/PageHeader';

const REVIEW_CSS = `
@keyframes sa-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes sa-slide { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@keyframes sa-spin { to { transform: rotate(360deg); } }
@keyframes sa-panel-in { from { opacity: 0; transform: translateX(-16px); } to { opacity: 1; transform: none; } }
.sa-spinner { width: 26px; height: 26px; border-radius: 50%; border: 3px solid var(--border-color); border-top-color: var(--accent); animation: sa-spin 0.7s linear infinite; }
.sa-spinner-sm { width: 16px; height: 16px; border-width: 2px; }
`;

const REVIEW_STORAGE_KEY = 'orbis_assignment_reviews';

type TimelineStep = { label: string; detail?: string; t: number; kind?: string; phase?: string };

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
            className={clickable && !isActive ? 'req-row' : undefined}
            style={{
              display: 'flex', gap: 12, padding: '14px 12px', margin: '0 -12px', borderRadius: 10,
              borderTop: i === 0 ? 'none' : '1px solid var(--border-color)',
              opacity: checked || !live ? 1 : 0.45, transition: 'background 0.15s ease, opacity 0.15s ease',
              cursor: clickable ? 'pointer' : 'default',
              background: isActive ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'transparent',
            }}
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

// Turn the raw streamed verdict JSON into readable reasoning prose: pull out the
// human sentences (reasoning/evidence/feedback fields) and drop JSON scaffolding.
function humanizeReasoning(raw: string): string {
  if (!raw) return '';
  // Collect quoted natural-language strings that look like sentences.
  const out: string[] = [];
  const re = /"(?:reasoning|evidence|feedback|why_it_matters|summary|assignment_understanding|submission_summary)"\s*:\s*"((?:[^"\\]|\\.)*)"/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(raw)) !== null) {
    const s = m[1].replace(/\\"/g, '"').replace(/\\n/g, ' ').trim();
    if (s.length > 3) out.push(s);
  }
  if (out.length) return out.join('\n\n');
  // Before any field closes, show the live tail as plain text (strip JSON noise).
  const tail = raw.replace(/[{}[\]"]/g, ' ').replace(/\b\w+\s*:/g, '').replace(/\s+/g, ' ').trim();
  return tail.slice(-600);
}

// Per-step node color/icon by kind — makes the agent's actions scannable.
function stepTone(kind?: string): { color: string; mono?: boolean } {
  switch (kind) {
    case 'read': return { color: '#22c55e', mono: true };
    case 'skip': return { color: 'var(--text-muted)', mono: true };
    case 'met': return { color: '#22c55e' };
    case 'unmet': return { color: '#ef4444' };
    case 'reason': return { color: 'var(--accent)' };
    default: return { color: 'var(--accent)' };
  }
}

// The "big steps" the granular substeps roll up under.
const PHASE_GROUPS: Array<{ id: string; label: string; icon: typeof Activity }> = [
  { id: 'inspect', label: 'Extract document', icon: FileText },
  { id: 'requirements', label: 'Understand assignment', icon: ClipboardList },
  { id: 'judge', label: 'Judge against requirements', icon: Activity },
  { id: 'verdict', label: 'Final verdict', icon: CheckCircle },
];

function PhaseGroup({ group, steps, isActive, isDone, defaultOpen }: {
  group: { id: string; label: string; icon: typeof Activity };
  steps: TimelineStep[]; isActive: boolean; isDone: boolean; defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  // Keep the active group open; let the user toggle finished ones.
  useEffect(() => { if (isActive) setOpen(true); }, [isActive]);

  const Icon = group.icon;
  const headColor = isActive ? 'var(--accent)' : isDone ? '#22c55e' : 'var(--text-muted)';

  return (
    <div style={{ borderBottom: '1px solid var(--border-color)' }}>
      <button onClick={() => setOpen(o => !o)} className="hoverable" style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 11, padding: '13px 8px',
        background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left',
      }}>
        <span style={{
          width: 26, height: 26, borderRadius: 8, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: isActive ? 'var(--accent)' : isDone ? 'color-mix(in srgb, #22c55e 18%, transparent)' : 'var(--bg-tertiary)',
          color: isActive ? '#fff' : headColor,
        }}>
          {isActive ? <span className="sa-spinner sa-spinner-sm" style={{ width: 13, height: 13 }} /> : <Icon size={14} strokeWidth={2.1} />}
        </span>
        <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)' }}>{group.label}</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{steps.length}</span>
        <ChevronRight size={15} style={{ color: 'var(--text-muted)', transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s var(--ease)', flexShrink: 0 }} />
      </button>

      {open && steps.length > 0 && (
        <div style={{ position: 'relative', padding: '0 8px 14px 16px' }}>
          {steps.map((s, i) => {
            const tone = stepTone(s.kind); const c = tone.color;
            const isLast = i === steps.length - 1;
            const live = isActive && isLast;
            return (
              <div key={i} style={{ position: 'relative', paddingLeft: 22, paddingBottom: isLast ? 0 : 11, animation: 'sa-slide 0.18s ease' }}>
                {!isLast && <span style={{ position: 'absolute', left: 5.5, top: 13, bottom: 0, width: 1.5, background: 'var(--border-color)' }} />}
                <span style={{
                  position: 'absolute', left: 0, top: 2, width: 12, height: 12, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: live ? c : `color-mix(in srgb, ${c} 22%, transparent)`,
                  boxShadow: live ? `0 0 0 3px color-mix(in srgb, ${c} 20%, transparent)` : 'none',
                }}>
                  <span style={{ width: 4, height: 4, borderRadius: '50%', background: live ? '#fff' : c }} />
                </span>
                <div style={{
                  fontSize: 12, fontWeight: s.kind === 'read' || s.kind === 'skip' ? 500 : 600,
                  color: s.kind === 'skip' ? 'var(--text-muted)' : 'var(--text-primary)', lineHeight: 1.4,
                  fontFamily: tone.mono ? 'ui-monospace, Menlo, monospace' : undefined, wordBreak: 'break-word',
                }}>{s.label}</div>
                {s.detail && (
                  s.kind === 'reason'
                    ? <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{s.detail}{live && <span className="cw-caret" />}</div>
                    : <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1, lineHeight: 1.45, wordBreak: 'break-word' }}>{s.detail}</div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function WorkTrail({ steps, running }: { steps: TimelineStep[]; running: boolean }) {
  // Group steps under their phase. Find which phase is currently active.
  const byPhase: Record<string, TimelineStep[]> = {};
  for (const s of steps) (byPhase[s.phase || 'inspect'] ??= []).push(s);
  const activePhase = steps.length ? (steps[steps.length - 1].phase || 'inspect') : '';
  const activeIdx = PHASE_GROUPS.findIndex(g => g.id === activePhase);

  // Newest (active) phase first so the live work flows to the top of the eye.
  const ordered = PHASE_GROUPS
    .map((g, idx) => ({ g, idx, steps: byPhase[g.id] || [] }))
    .filter(x => x.steps.length > 0)
    .reverse();

  return (
    <aside style={{
      width: 380, flexShrink: 0, alignSelf: 'stretch',
      borderRight: '1px solid var(--border-color)', background: 'var(--bg-secondary)',
      padding: '22px 16px', overflowY: 'auto',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, padding: '0 8px' }}>
        <Activity size={15} style={{ color: 'var(--accent)' }} />
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.7, textTransform: 'uppercase', color: 'var(--text-muted)' }}>Agent work</span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14, padding: '0 8px' }}>
        {running ? 'Working through your submission…' : `${steps.length} steps`}
      </div>

      {steps.length === 0 && !running && (
        <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '0 8px' }}>No activity recorded.</div>
      )}

      <div>
        {ordered.map(({ g, idx, steps: gs }) => (
          <PhaseGroup
            key={g.id}
            group={g}
            steps={gs}
            isActive={running && g.id === activePhase}
            isDone={!running || idx < activeIdx}
            defaultOpen={g.id === activePhase}
          />
        ))}
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

const LANG_BY_EXT: Record<string, { label: string; color: string }> = {
  py: { label: 'Python', color: '#3776ab' }, js: { label: 'JavaScript', color: '#f7df1e' },
  ts: { label: 'TypeScript', color: '#3178c6' }, tsx: { label: 'TSX', color: '#3178c6' },
  jsx: { label: 'JSX', color: '#f7df1e' }, java: { label: 'Java', color: '#e76f00' },
  c: { label: 'C', color: '#a8b9cc' }, cpp: { label: 'C++', color: '#00599c' }, cs: { label: 'C#', color: '#9b4f96' },
  go: { label: 'Go', color: '#00add8' }, rb: { label: 'Ruby', color: '#cc342d' }, rs: { label: 'Rust', color: '#dea584' },
  html: { label: 'HTML', color: '#e34c26' }, css: { label: 'CSS', color: '#563d7c' },
  md: { label: 'Markdown', color: '#888' }, json: { label: 'JSON', color: '#cbcb41' },
  txt: { label: 'Text', color: '#888' }, pdf: { label: 'PDF', color: '#ef4444' },
  docx: { label: 'Word', color: '#2b579a' }, zip: { label: 'Archive', color: '#f59e0b' },
  tex: { label: 'LaTeX', color: '#008080' }, ipynb: { label: 'Notebook', color: '#f37726' },
};

const SYNTAX_LANG: Record<string, string> = {
  py: 'python', js: 'javascript', jsx: 'jsx', ts: 'typescript', tsx: 'tsx',
  java: 'java', c: 'c', cpp: 'cpp', cs: 'csharp', go: 'go', rb: 'ruby', rs: 'rust',
  html: 'markup', css: 'css', md: 'markdown', json: 'json', sh: 'bash',
  tex: 'latex', ipynb: 'json', txt: 'text',
};

function SourceViewer({ source, truncated, filename, active }: {
  source: string; truncated?: boolean; filename?: string; active: Finding | null;
}) {
  const span = locateEvidence(source, active);

  const ext = (filename?.split('.').pop() || '').toLowerCase();
  const lang = LANG_BY_EXT[ext] ?? { label: ext ? ext.toUpperCase() : 'File', color: 'var(--accent)' };
  const syntaxLang = SYNTAX_LANG[ext] ?? 'text';
  const lines = source.split('\n');

  // Map the cited char range → [firstLine, lastLine] (1-based) for highlighting.
  let hitStart = -1, hitEnd = -1;
  if (span) {
    let pos = 0;
    for (let i = 0; i < lines.length; i++) {
      const lineEnd = pos + lines[i].length;
      if (span[0] < lineEnd && span[1] > pos) { if (hitStart === -1) hitStart = i + 1; hitEnd = i + 1; }
      pos = lineEnd + 1;
    }
  }

  const codeRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (hitStart > 0 && codeRef.current) {
      const el = codeRef.current.querySelector(`[data-line="${hitStart}"]`) as HTMLElement | null;
      el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }, [active, hitStart]);

  return (
    <aside style={{
      width: 480, flexShrink: 0, alignSelf: 'stretch', borderLeft: '1px solid var(--border-color)',
      background: '#0d1117', display: 'flex', flexDirection: 'column',
    }}>
      {/* File tab header */}
      <div style={{ borderBottom: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px 0' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8, padding: '7px 13px 9px',
            background: '#0d1117', borderRadius: '8px 8px 0 0',
            border: '1px solid var(--border-color)', borderBottom: 'none', marginBottom: -1,
          }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: lang.color, flexShrink: 0 }} />
            <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'ui-monospace, Menlo, monospace', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{filename || 'submission'}</span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '8px 16px' }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: lang.color, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{lang.label}</span>
          <span style={{ fontSize: 11.5, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
            {lines.length} lines · {source.length.toLocaleString()} chars
          </span>
        </div>
        {active && (
          <div style={{ padding: '0 16px 9px', fontSize: 11.5, color: hitStart > 0 ? 'var(--accent)' : 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 5 }}>
            <FileText size={11} /> {hitStart > 0 ? `Cited evidence · line ${hitStart}${hitEnd > hitStart ? `–${hitEnd}` : ''}` : 'No exact match — full file shown'}
          </div>
        )}
      </div>

      {/* Syntax-highlighted code with cited-line highlight */}
      <div ref={codeRef} style={{ flex: 1, overflow: 'auto' }}>
        <SyntaxHighlighter
          language={syntaxLang}
          style={oneDark}
          showLineNumbers
          wrapLines
          lineProps={(n: number) => {
            const hit = hitStart > 0 && n >= hitStart && n <= hitEnd;
            return {
              'data-line': n,
              style: {
                display: 'block',
                background: hit ? 'color-mix(in srgb, var(--accent) 18%, transparent)' : 'transparent',
                boxShadow: hit ? 'inset 2px 0 0 var(--accent)' : undefined,
              },
            } as React.HTMLProps<HTMLElement>;
          }}
          customStyle={{ margin: 0, background: 'transparent', padding: '14px 4px 14px 0', fontSize: 12.5, lineHeight: 1.7 }}
          codeTagProps={{ style: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' } }}
          lineNumberStyle={{ minWidth: '3em', paddingRight: '1.1em', color: '#5f5f6b', userSelect: 'none' }}
        >
          {source}
        </SyntaxHighlighter>
        {truncated && <div style={{ padding: '12px 16px', color: 'var(--text-muted)', fontStyle: 'italic', fontSize: 11.5 }}>… file truncated for display</div>}
      </div>
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
    const log = (label: string, detail?: string, kind?: string, phase = 'inspect') => {
      trail.push({ label, detail, t: Date.now(), kind, phase });
      setTimeline([...trail]);
    };
    try {
      let finalResult: SubmitResult | null = null;
      let liveReqs: string[] = [];
      let liveFindings: Finding[] = [];
      let reasoningBuf = '';
      let reasoningStarted = false;
      await api.submitAssignmentStream(assignment.id, file, (type, data) => {
        if (type === 'step') {
          // Granular agent narration — every real sub-step, streamed live.
          log(String(data.message ?? ''), data.detail ? String(data.detail) : undefined, data.kind, String(data.phase ?? 'inspect'));
        } else if (type === 'inspecting') {
          log('Opening the file', file.name, undefined, 'inspect');
        } else if (type === 'inspected') {
          // Granular steps already narrated via 'step'; just capture the source text + warnings here.
          for (const w of (data.warnings || [])) log('Warning', String(w), 'skip', 'inspect');
          src = data.extracted_text || '';
          srcTrunc = !!data.extracted_truncated;
          setSourceText(src);
          setSourceTruncated(srcTrunc);
        } else if (type === 'understanding') {
          // narrated via 'step'
        } else if (type === 'requirements') {
          liveReqs = data.requirements || [];
          setRequirements(liveReqs);
        } else if (type === 'judging') {
          // narrated via 'step'
        } else if (type === 'token') {
          // The LLM's live chain-of-thought — streamed as a growing "Reasoning"
          // step inside the Agent Work block (left), readable prose.
          reasoningBuf += (data.text ?? '');
          const prose = humanizeReasoning(reasoningBuf);
          if (!reasoningStarted) { reasoningStarted = true; log('Reasoning', prose, 'reason', 'judge'); }
          else {
            const last = trail[trail.length - 1];
            if (last && last.label === 'Reasoning') { last.detail = prose; last.t = Date.now(); setTimeline([...trail]); }
          }
        } else if (type === 'finding') {
          liveFindings = [...liveFindings, data.finding];
          setFindings(liveFindings);
          const f = data.finding as Finding;
          const reqShort = (f.requirement || '').replace(/^The submission must |^Submission must address: /i, '').slice(0, 70);
          log(`${f.satisfied ? 'Met' : 'Not met'} — ${reqShort}`, f.reasoning?.slice(0, 160), f.satisfied ? 'met' : 'unmet', 'judge');
        } else if (type === 'verdict') {
          const conf = data.confidence != null ? ` · ${Math.round(Number(data.confidence) * 100)}% confidence` : '';
          log('Reached a verdict', `${data.decision ?? ''}${conf}`, undefined, 'verdict');
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

      {/* RUNNING: single status line — the detailed reasoning streams in the
          Agent Work block on the left. */}
      {running && (
        <div style={{ marginTop: 26, display: 'flex', alignItems: 'center', gap: 10, fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
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
    <div style={{ padding: '44px 40px 64px', maxWidth: 960, margin: '0 auto' }}>
      <PageHeader
        icon={ClipboardList}
        eyebrow="Review · Agent"
        title="Submission review"
        subtitle="Upload your work — an agent checks each requirement against the brief with cited evidence."
      />

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
