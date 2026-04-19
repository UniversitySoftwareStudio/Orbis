import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Send, Bot } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import ReactMarkdown from 'react-markdown';
import type { Message } from '../types';

export function ChatPage() {
  const { user, chatHistory: messages, setChatHistory: setMessages } = useAuth();
  const { t, i18n } = useTranslation();

  const makeGreeting = (lang: string): Message => ({
    id: 'greeting',
    role: 'assistant',
    content: lang === 'tr'
      ? t('chat.greeting', { lng: 'tr' })
      : t('chat.greeting', { lng: 'en' }),
  });

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (messages.length === 0) {
      setMessages([makeGreeting(i18n.language)]);
    }
  }, []);

  useEffect(() => {
    setMessages(prev => {
      const withoutGreeting = prev.filter(m => m.id !== 'greeting');
      return [makeGreeting(i18n.language), ...withoutGreeting];
    });
  }, [i18n.language]);

  const handleSend = async () => {
    if (!input.trim() || !user) return;

    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);

    try {
      // Add a placeholder for the AI response
      setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

      await api.chatStream(userMsg, user.token, (chunk) => {
        setMessages(prev => {
          const newMsgs = [...prev];
          const lastMsgIndex = newMsgs.length - 1;

          // FIX: Create a shallow copy of the last message object
          // This prevents the "Double Render" duplication bug
          const lastMsg = { ...newMsgs[lastMsgIndex] };

          if (lastMsg.role === 'assistant') {
            lastMsg.content += chunk;
            // Put the copy back into the array
            newMsgs[lastMsgIndex] = lastMsg;
          }
          return newMsgs;
        });
      });
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: '[Error: Could not reach the agent.]' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 20, height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{ marginBottom: 20 }}>
        <h3 style={{ color: 'var(--text-primary)' }}>Orbis Chat</h3>
      </header>

      <div style={{
        border: '1px solid var(--border-color)',
        flex: 1,
        overflowY: 'auto',
        padding: 20,
        borderRadius: 8,
        backgroundColor: 'var(--bg-secondary)',
        marginBottom: 20,
      }}>
        {messages.map((msg, i) => {
          return (
          <div key={msg.id ?? i} style={{
            display: 'flex',
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            alignItems: 'flex-start',
            gap: 8,
            marginBottom: 10,
          }}>
            {msg.role === 'assistant' && (
              <div style={{ flexShrink: 0, marginTop: 10, color: 'var(--text-secondary)' }}>
                <Bot size={16} strokeWidth={1.8} />
              </div>
            )}
            <div style={{
              maxWidth: '70%',
              padding: '10px 15px',
              borderRadius: 15,
              backgroundColor: msg.role === 'user' ? 'var(--accent)' : 'var(--bg-tertiary)',
              color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
              whiteSpace: 'pre-wrap',
              overflowX: 'hidden',
              boxSizing: 'border-box',
            }}>
              <div className="markdown-body">
                <ReactMarkdown
                  components={{
                    p: ({children}) => <p>{children}</p>,
                    ul: ({children}) => (
                      <ul style={{margin: '2px 0 4px 0', paddingLeft: '20px'}}>{children}</ul>
                    ),
                    li: ({children}) => <li style={{marginBottom: '2px'}}>{children}</li>,
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              </div>
            </div>
          </div>
          );
        })}
        {isLoading && <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>Agent is typing...</div>}
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder={t('chat.placeholder')}
          style={{ flex: 1, padding: 15, borderRadius: 5, border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-primary)' }}
        />
        <button
          onClick={handleSend}
          disabled={isLoading}
          className="btn btn-accent"
          style={{ padding: '0 25px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <Send size={18} strokeWidth={1.8} />
        </button>
      </div>
    </div>
  );
}
