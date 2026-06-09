import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageSquare, X, Maximize2, Minimize2, Send, Bot, Sparkles, Plus, Check, ExternalLink, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import type { Message, ChatSource } from '../types';

// Example prompts shown in the empty state — illustrate exactly what the chat does.
const EXAMPLES = [
  { q: 'chat.examples.addDrop', fallback: 'When is the add/drop deadline this semester?' },
  { q: 'chat.examples.internship', fallback: 'What are the mandatory internship requirements?' },
  { q: 'chat.examples.prereq', fallback: 'What are the prerequisites for COMP 201?' },
  { q: 'chat.examples.erasmus', fallback: 'How do I apply for the Erasmus exchange program?' },
];

// Floating, expandable RAG chat. Lives on every page as a bottom-right launcher.
// Three states: closed (bubble) → docked panel → expanded full-page overlay.
export function ChatWidget() {
  const { user, chatHistory: messages, setChatHistory: setMessages } = useAuth();
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeSource, setActiveSource] = useState<ChatSource | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Open cited documents in the right-side reader (expands the panel full-page).
  const openSource = (src: ChatSource) => { setActiveSource(src); setExpanded(true); };

  const makeGreeting = (lang: string): Message => ({
    id: 'greeting', role: 'assistant',
    content: lang === 'tr' ? t('chat.greeting', { lng: 'tr' }) : t('chat.greeting', { lng: 'en' }),
  });

  useEffect(() => {
    if (messages.length === 0) setMessages([makeGreeting(i18n.language)]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setMessages(prev => [makeGreeting(i18n.language), ...prev.filter(m => m.id !== 'greeting')]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i18n.language]);

  // Auto-scroll + focus when opening / new messages.
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, open, isLoading]);
  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 100); }, [open]);

  // Allow other components (e.g. the dashboard "Ask official sources" card) to open the widget.
  useEffect(() => {
    const openHandler = () => setOpen(true);
    window.addEventListener('orbis:open-chat', openHandler);
    return () => window.removeEventListener('orbis:open-chat', openHandler);
  }, []);

  const handleSend = async (preset?: string) => {
    const userMsg = (preset ?? input).trim();
    if (!userMsg || !user || isLoading) return;
    const focusedSource = activeSource;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);
    try {
      setMessages(prev => [...prev, { role: 'assistant', content: '', steps: [], sources: [], running: true }]);
      const patchLast = (fn: (m: Message) => Message) => setMessages(prev => {
        const n = [...prev]; const i = n.length - 1;
        if (n[i].role === 'assistant') n[i] = fn({ ...n[i] });
        return n;
      });
      await api.chatStream(userMsg, user.token, (type, data) => {
        if (type === 'step') {
          patchLast(m => ({ ...m, steps: [...(m.steps || []), { message: data.message, detail: data.detail }] }));
        } else if (type === 'source') {
          const source = { title: data.title, url: data.url, type: data.doc_type, category: data.category, language: data.language, snippet: data.snippet, content: data.content };
          patchLast(m => ({ ...m, sources: [...(m.sources || []), source] }));
          setActiveSource(current => current ?? source);
          setExpanded(true);
        } else if (type === 'chunk') {
          patchLast(m => ({ ...m, content: m.content + (data.text || '') }));
        } else if (type === 'done') {
          patchLast(m => ({ ...m, running: false }));
        } else if (type === 'error') {
          patchLast(m => ({ ...m, content: m.content || '[Error: Could not reach the agent.]', running: false }));
        }
      }, focusedSource);
      patchLast(m => ({ ...m, running: false }));
    } catch (err) {
      console.error(err);
      setMessages(prev => {
        const n = [...prev]; const i = n.length - 1;
        if (n[i]?.role === 'assistant') n[i] = { ...n[i], content: n[i].content || '[Error: Could not reach the agent.]', running: false };
        return n;
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!user) return null;

  // "Empty" = no real exchange yet (only the greeting message present).
  const isEmpty = messages.every(m => m.id === 'greeting');
  const referenceSources = [...messages].reverse().find(m => m.role === 'assistant' && m.sources?.length)?.sources ?? [];
  const transcriptMaxWidth = expanded ? 'min(920px, 100%)' : 'none';
  const expandedInlinePadding = 'clamp(20px, 5vw, 76px)';

  // ---- Launcher bubble (closed) ----
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Open Orbis chat"
        className="cw-launcher"
      >
        <span className="cw-launcher-ping" />
        <Sparkles size={13} className="cw-launcher-spark" strokeWidth={2.4} />
        <MessageSquare size={23} strokeWidth={2.1} />
      </button>
    );
  }

  // ---- Panel geometry ----
  // Docked: compact bottom-right card. Expanded: TRUE full-page overlay.
  const panelStyle: React.CSSProperties = expanded
    ? { inset: 0, width: '100vw', height: '100vh', borderRadius: 0, border: 'none' }
    : {
        right: 24, bottom: 24, width: 'min(420px, calc(100vw - 48px))', height: 'min(640px, calc(100vh - 48px))',
        borderRadius: 18, border: '1px solid var(--border-strong)',
      };

  return (
    <>
    {/* Dim backdrop only when full-page */}
    {expanded && (
      <div onClick={() => setExpanded(false)} style={{ position: 'fixed', inset: 0, zIndex: 999, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(2px)' }} />
    )}
    <div
      style={{
        position: 'fixed', zIndex: 1000, display: 'flex', flexDirection: 'column',
        background: 'var(--bg-secondary)',
        boxShadow: expanded ? 'none' : 'var(--shadow-lg)', overflow: 'hidden',
        animation: expanded ? 'cw-grow 0.22s var(--ease)' : 'cw-pop 0.2s var(--ease)', ...panelStyle,
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
        padding: '14px 16px', borderBottom: '1px solid var(--border-color)',
        background: 'linear-gradient(180deg, color-mix(in srgb, var(--path-pull) 8%, var(--bg-secondary)), var(--bg-secondary))',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 9, flexShrink: 0,
            background: 'var(--path-pull)', color: '#04201c',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Bot size={18} strokeWidth={2.2} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.2 }}>{t('chat.heading', 'Ask official sources')}</div>
            <div style={{ fontSize: 11, color: 'var(--path-pull)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Sparkles size={10} /> {t('chat.eyebrow', 'Pull · RAG')}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <button onClick={() => { setMessages([makeGreeting(i18n.language)]); setInput(''); setActiveSource(null); }} title={t('chat.newChat', 'New chat')} className="cw-iconbtn" disabled={isLoading}>
            <Plus size={17} />
          </button>
          <button onClick={() => setExpanded(e => !e)} title={expanded ? 'Shrink' : 'Expand'} className="cw-iconbtn">
            {expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
          <button onClick={() => setOpen(false)} title="Close" className="cw-iconbtn">
            <X size={17} />
          </button>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, display: 'flex', overflow: 'hidden' }}>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      {/* Messages */}
      <div
        ref={scrollRef}
        style={{
          flex: 1, minHeight: 0, overflowY: 'auto',
          padding: expanded ? `20px ${expandedInlinePadding} 18px` : '16px',
        }}
      >
        <div style={{ width: '100%', maxWidth: transcriptMaxWidth, margin: '0 auto' }}>
          {/* Empty state — illustrate what this chat is for, with example prompts */}
          {isEmpty && (
            <div style={{ padding: expanded ? '32px 0 8px' : '12px 4px 8px', animation: 'cw-pop 0.25s var(--ease)' }}>
              <div style={{
                width: 52, height: 52, borderRadius: 15, marginBottom: 18,
                background: 'linear-gradient(140deg, var(--path-pull), color-mix(in srgb, var(--path-pull) 55%, #000))',
                color: '#04201c', display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 8px 22px -6px color-mix(in srgb, var(--path-pull) 60%, transparent)',
              }}>
                <Bot size={26} strokeWidth={2} />
              </div>
              <div style={{ fontSize: 19, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                {t('chat.empty.title', 'Ask anything about Bilgi')}
              </div>
              <div style={{ fontSize: 13.5, color: 'var(--text-secondary)', marginTop: 7, lineHeight: 1.55 }}>
                {t('chat.empty.body', 'Grounded answers from official regulations, the course catalog, and the academic calendar — every reply is backed by real sources.')}
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', margin: '20px 0 10px' }}>
                {t('chat.empty.tryLabel', 'Try asking')}
              </div>
              <div style={{ display: 'grid', gap: 9 }}>
                {EXAMPLES.map((ex, i) => (
                  <button key={i} className="cw-chip" onClick={() => handleSend(t(ex.q, ex.fallback))}>
                    {t(ex.q, ex.fallback)}
                  </button>
                ))}
              </div>
            </div>
          )}
          {!isEmpty && messages.map((msg, i) => (
            <div key={msg.id ?? i} style={{
              display: 'flex', gap: 10, marginBottom: expanded ? 10 : 14,
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              alignItems: 'flex-start',
            }}>
              {msg.role === 'assistant' && (
                <div style={{ flexShrink: 0, marginTop: 6, color: 'var(--path-pull)' }}><Bot size={16} strokeWidth={1.9} /></div>
              )}
              <div style={{
                maxWidth: msg.role === 'user' ? 'min(74%, 720px)' : 'min(780px, calc(100% - 28px))',
                width: msg.role === 'assistant' ? '100%' : 'auto',
                minWidth: 0,
              }}>
                {/* Agent steps (assistant only) */}
                {msg.role === 'assistant' && msg.steps && msg.steps.length > 0 && (
                  <div style={{
                    marginBottom: msg.content ? 8 : 0,
                    border: '1px solid var(--border-color)', borderRadius: 8,
                    padding: '9px 12px', background: 'var(--bg-card)',
                  }}>
                    {msg.steps.map((s, j) => {
                      const last = j === msg.steps!.length - 1;
                      const live = msg.running && last && !msg.content;
                      return (
                        <div key={j} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '2px 0' }}>
                          <span style={{ flexShrink: 0, marginTop: 5 }}>
                            {live ? <span className="sa-spinner sa-spinner-sm" style={{ width: 11, height: 11, borderWidth: 2 }} />
                                  : <Check size={13} strokeWidth={2.6} style={{ color: 'var(--path-pull)' }} />}
                          </span>
                          <div style={{ minWidth: 0 }}>
                            <span style={{ fontSize: 12.5, color: live ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: live ? 600 : 500 }}>{s.message}</span>
                            {s.detail && <span style={{ fontSize: 11.5, color: 'var(--text-muted)', marginLeft: 6 }}>{s.detail}</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Answer bubble */}
                {(msg.content || msg.role === 'user') && (
                  <div style={{
                    padding: expanded ? '10px 14px' : '9px 13px', borderRadius: 10,
                    background: msg.role === 'user' ? 'var(--accent)' : 'var(--bg-tertiary)',
                    color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                    fontSize: 14, lineHeight: 1.55,
                  }}>
                    <div className="markdown-body">
                      <ReactMarkdown
                        components={{
                          ul: ({ children }) => <ul style={{ margin: '2px 0 4px 0', paddingLeft: 18 }}>{children}</ul>,
                          li: ({ children }) => <li style={{ marginBottom: 2 }}>{children}</li>,
                          a: ({ children, href }) => <a href={href} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>{children}</a>,
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 13, paddingLeft: 24 }}>
              <span className="chat-dots"><i /><i /><i /></span>
              {t('chat.thinking', 'Searching official sources…')}
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div
        style={{
          padding: expanded ? `12px ${expandedInlinePadding}` : 14,
          borderTop: '1px solid var(--border-color)', background: 'var(--bg-secondary)',
        }}
      >
        <div style={{ display: 'flex', gap: 8, width: '100%', maxWidth: transcriptMaxWidth, margin: '0 auto' }}>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder={t('chat.placeholder')}
            style={{
              flex: 1, minWidth: 0, height: 42, padding: '0 14px', borderRadius: 10, fontSize: 14,
              border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-primary)', outline: 'none',
            }}
          />
          <button onClick={() => handleSend()} disabled={isLoading || !input.trim()} className="btn btn-accent"
            style={{ width: 52, height: 42, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: (isLoading || !input.trim()) ? 0.5 : 1, flexShrink: 0 }}>
            <Send size={17} strokeWidth={2} />
          </button>
        </div>
      </div>
      </div>
      {expanded && activeSource && referenceSources.length > 0 && (
        <SourcesPanel
          sources={referenceSources}
          activeSource={activeSource}
          onSelect={openSource}
          onClose={() => setActiveSource(null)}
          closeLabel={t('chat.closeSource', 'Close source')}
          emptyLabel={t('chat.noSourcePreview', 'No preview available.')}
        />
      )}
      </div>
    </div>
    </>
  );
}

function SourcesPanel({
  sources,
  activeSource,
  onSelect,
  onClose,
  closeLabel,
  emptyLabel,
}: {
  sources: ChatSource[];
  activeSource: ChatSource | null;
  onSelect: (source: ChatSource) => void;
  onClose: () => void;
  closeLabel: string;
  emptyLabel: string;
}) {
  const selected = activeSource ?? sources[0];

  return (
    <aside style={{
      width: 'clamp(360px, 30vw, 460px)', minWidth: 0, height: '100%',
      borderLeft: '1px solid var(--border-color)', background: 'var(--bg-card)',
      display: 'flex', flexDirection: 'column',
    }}>
      <div style={{
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
        padding: '16px 18px', borderBottom: '1px solid var(--border-color)',
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--path-pull)', marginBottom: 8 }}>
            <FileText size={16} />
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>References</span>
          </div>
          <div style={{ fontSize: 14.5, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.35 }}>
            {sources.length} official source{sources.length === 1 ? '' : 's'}
          </div>
        </div>
        <button onClick={onClose} title={closeLabel} className="cw-iconbtn" style={{ flexShrink: 0 }}>
          <X size={16} />
        </button>
      </div>
      <div style={{ padding: 12, borderBottom: '1px solid var(--border-color)', display: 'grid', gap: 8, minWidth: 0, overflow: 'hidden' }}>
        {sources.map((source, index) => {
          const isActive = selected && source.title === selected.title && source.url === selected.url;
          return (
            <button
              key={`${source.url}-${index}`}
              onClick={() => onSelect(source)}
              className="cw-source"
              style={{
                width: '100%', minWidth: 0, overflow: 'hidden',
                cursor: 'pointer', textAlign: 'left', alignItems: 'flex-start',
                borderColor: isActive ? 'var(--accent)' : 'var(--border-color)',
                background: isActive ? 'var(--accent-subtle)' : 'var(--bg-secondary)',
              }}
            >
              <span style={{
                flexShrink: 0, width: 24, height: 24, borderRadius: 6,
                background: isActive ? 'var(--accent)' : 'var(--bg-tertiary)',
                color: isActive ? '#fff' : 'var(--accent)', display: 'flex',
                alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 800,
              }}>
                {index + 1}
              </span>
              <span style={{ minWidth: 0, flex: 1 }}>
                <span style={{
                  display: 'block', fontSize: 12.5, fontWeight: 650, color: 'var(--text-primary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'normal', lineHeight: 1.25,
                }}>
                  [{index + 1}] {source.title}
                </span>
                <span style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {source.url.replace(/^https?:\/\//, '')}
                </span>
              </span>
            </button>
          );
        })}
      </div>
      <div style={{
        flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px 18px',
        color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.65, whiteSpace: 'pre-wrap',
      }}>
        {selected && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.4 }}>
              {selected.title}
            </div>
            <a href={selected.url} target="_blank" rel="noreferrer" style={{
              marginTop: 7, display: 'inline-flex', alignItems: 'center', gap: 5,
              fontSize: 12, color: 'var(--accent)', textDecoration: 'none',
              maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {selected.url.replace(/^https?:\/\//, '')}
              <ExternalLink size={12} style={{ flexShrink: 0 }} />
            </a>
          </div>
        )}
        {selected?.content || selected?.snippet || emptyLabel}
      </div>
    </aside>
  );
}
