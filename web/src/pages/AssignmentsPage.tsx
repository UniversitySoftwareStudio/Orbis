import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { ClipboardList, Upload, X, CheckCircle, XCircle, Clock } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

interface Submission {
  id: number;
  status: 'pending' | 'approved' | 'rejected';
  ai_feedback: string;
  submitted_at: string;
  original_filename: string;
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

function StatusBadge({ status }: { status: Submission['status'] }) {
  const colors: Record<string, string> = {
    approved: '#22c55e',
    rejected: '#ef4444',
    pending: '#f59e0b',
  };
  const icons = {
    approved: <CheckCircle size={14} strokeWidth={2} />,
    rejected: <XCircle size={14} strokeWidth={2} />,
    pending: <Clock size={14} strokeWidth={2} />,
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

function SubmitModal({ assignment, onClose, onDone }: {
  assignment: Assignment;
  onClose: () => void;
  onDone: (result: { status: string; ai_feedback: string }) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const result = await api.submitAssignment(assignment.id, file);
      onDone(result);
    } catch (e: any) {
      setError(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000,
    }}>
      <div style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: 16,
        padding: 32,
        width: 480,
        maxWidth: '90vw',
        boxShadow: 'var(--shadow)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <h3 style={{ margin: 0, color: 'var(--text-primary)', fontSize: 18 }}>{assignment.title}</h3>
            {assignment.description && (
              <p style={{ margin: '6px 0 0', color: 'var(--text-secondary)', fontSize: 13 }}>
                {assignment.description}
              </p>
            )}
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}>
            <X size={20} strokeWidth={1.8} />
          </button>
        </div>

        <div
          onClick={() => inputRef.current?.click()}
          style={{
            border: '2px dashed var(--border-color)',
            borderRadius: 10,
            padding: '32px 16px',
            textAlign: 'center',
            cursor: 'pointer',
            color: file ? 'var(--accent)' : 'var(--text-muted)',
            transition: 'border-color 0.15s ease',
            marginBottom: 16,
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-color)'; }}
        >
          <Upload size={28} strokeWidth={1.5} style={{ marginBottom: 8 }} />
          <div style={{ fontSize: 14 }}>
            {file ? file.name : 'Click to select a file (PDF, DOCX, TXT — max 10 MB)'}
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            style={{ display: 'none' }}
            onChange={e => {
              const f = e.target.files?.[0];
              if (f) setFile(f);
            }}
          />
        </div>

        {error && (
          <div style={{ color: '#ef4444', fontSize: 13, marginBottom: 12 }}>{error}</div>
        )}

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 18px', borderRadius: 8, border: '1px solid var(--border-color)',
              background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 14,
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!file || uploading}
            style={{
              padding: '8px 18px', borderRadius: 8, border: 'none',
              background: file && !uploading ? 'var(--accent)' : 'var(--bg-tertiary)',
              color: file && !uploading ? '#fff' : 'var(--text-muted)',
              cursor: file && !uploading ? 'pointer' : 'default',
              fontSize: 14, fontWeight: 600, transition: 'background 0.15s ease',
            }}
          >
            {uploading ? 'Validating…' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  );
}

function ResultModal({ status, feedback, onClose }: {
  status: string;
  feedback: string;
  onClose: () => void;
}) {
  const approved = status === 'approved';
  return (
    <div style={{
      position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000,
    }}>
      <div style={{
        backgroundColor: 'var(--bg-secondary)',
        border: `1px solid ${approved ? '#22c55e' : '#ef4444'}`,
        borderRadius: 16,
        padding: 32,
        width: 440,
        maxWidth: '90vw',
        boxShadow: 'var(--shadow)',
        textAlign: 'center',
      }}>
        {approved
          ? <CheckCircle size={48} color="#22c55e" strokeWidth={1.5} />
          : <XCircle size={48} color="#ef4444" strokeWidth={1.5} />
        }
        <h3 style={{ margin: '16px 0 8px', color: 'var(--text-primary)' }}>
          {approved ? 'Submission Approved' : 'Submission Rejected'}
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 24 }}>
          {feedback.replace(/^(APPROVED|REJECTED):\s*/i, '')}
        </p>
        <button
          onClick={onClose}
          style={{
            padding: '8px 24px', borderRadius: 8, border: 'none',
            background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 14, fontWeight: 600,
          }}
        >
          OK
        </button>
      </div>
    </div>
  );
}

export function AssignmentsPage() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Assignment | null>(null);
  const [result, setResult] = useState<{ status: string; ai_feedback: string } | null>(null);

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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
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
                {a.submission && (
                  <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <StatusBadge status={a.submission.status} />
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {a.submission.original_filename}
                    </span>
                  </div>
                )}
              </div>

              <button
                onClick={() => setSelected(a)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  border: '1px solid var(--accent)',
                  background: 'transparent',
                  color: 'var(--accent)',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s ease',
                  flexShrink: 0,
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.background = 'var(--accent)';
                  (e.currentTarget as HTMLElement).style.color = '#fff';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.background = 'transparent';
                  (e.currentTarget as HTMLElement).style.color = 'var(--accent)';
                }}
              >
                {a.submission ? 'Resubmit' : 'Submit'}
              </button>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <SubmitModal
          assignment={selected}
          onClose={() => setSelected(null)}
          onDone={res => {
            setSelected(null);
            setResult(res);
            load();
          }}
        />
      )}

      {result && (
        <ResultModal
          status={result.status}
          feedback={result.ai_feedback}
          onClose={() => setResult(null)}
        />
      )}
    </div>
  );
}
