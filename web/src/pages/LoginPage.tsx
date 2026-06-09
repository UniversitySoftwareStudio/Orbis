import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { GraduationCap, ArrowRight, Globe } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'tr' ? 'en' : 'tr';
    i18n.changeLanguage(newLang);
    localStorage.setItem('orbis_lang', newLang);
  };

  const doLogin = async (email: string, pass: string) => {
    setLoading(true);
    try {
      const res = await api.post('/auth/login', {
        email,
        password: pass,
      });

      login({
        token: res.access_token || 'cookie',
        userType: res.user_type || 'student',
        firstName: res.first_name || '',
        lastName: res.last_name || '',
        email: res.email || '',
      });

      navigate('/dashboard');
    } catch (err: any) {
      console.error(err);
      alert(t('login.error') + ': ' + (err.message || JSON.stringify(err)));
    } finally {
      setLoading(false);
    }
  };

  // Dev convenience: /login?demo=1 auto-signs-in a seeded student.
  const ranDemo = useRef(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('demo') === '1' && !ranDemo.current) {
      ranDemo.current = true;
      const email = params.get('email') || 'h.bilgin@bilgiedu.net';
      doLogin(email, params.get('pw') || 'demo1234');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post('/auth/login', {
        email: username,
        password: password,
      });

      login({
        token: res.access_token || 'cookie',
        userType: res.user_type || 'student',
        firstName: res.first_name || '',
        lastName: res.last_name || '',
        email: res.email || '',
      });

      navigate('/dashboard');
    } catch (err: any) {
      console.error(err);
      alert(t('login.error') + ': ' + (err.message || JSON.stringify(err)));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      minHeight: '100vh',
      background: 'var(--bg-primary)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Ambient accent glow */}
      <div style={{
        position: 'absolute', top: '-20%', left: '-10%', width: 600, height: 600,
        background: 'radial-gradient(circle, color-mix(in srgb, var(--accent) 22%, transparent), transparent 70%)',
        filter: 'blur(40px)', pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', bottom: '-25%', right: '-5%', width: 500, height: 500,
        background: 'radial-gradient(circle, color-mix(in srgb, var(--accent) 14%, transparent), transparent 70%)',
        filter: 'blur(40px)', pointerEvents: 'none',
      }} />

      {/* Language toggle */}
      <button
        onClick={toggleLanguage}
        className="btn btn-ghost"
        style={{
          position: 'absolute', top: 20, right: 20, zIndex: 10,
          display: 'flex', alignItems: 'center', gap: 6, fontSize: 13,
          color: 'var(--text-secondary)',
        }}
      >
        <Globe size={15} strokeWidth={1.8} />
        {i18n.language === 'tr' ? 'EN' : 'TR'}
      </button>

      {/* Centered card */}
      <div style={{
        margin: 'auto', width: '100%', maxWidth: 400, padding: 24,
        position: 'relative', zIndex: 1,
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16,
            background: 'linear-gradient(135deg, var(--accent), color-mix(in srgb, var(--accent) 55%, #000))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 8px 24px color-mix(in srgb, var(--accent) 35%, transparent)',
            marginBottom: 18,
          }}>
            <GraduationCap size={28} color="#fff" strokeWidth={1.8} />
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
            {t('login.title')}
          </h1>
          <p style={{ fontSize: 14, color: 'var(--text-muted)', marginTop: 6 }}>
            {t('login.subtitle')}
          </p>
        </div>

        {/* Form card */}
        <form onSubmit={handleLogin} className="card" style={{
          display: 'flex', flexDirection: 'column', gap: 14,
          padding: 28, background: 'var(--bg-card)',
        }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>{t('login.email')}</span>
            <input
              placeholder="you@bilgi.edu.tr"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              style={inputStyle}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>{t('login.password')}</span>
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
              style={inputStyle}
            />
          </label>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-accent"
            style={{
              marginTop: 6, padding: '12px 16px', fontSize: 15, fontWeight: 600,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? t('login.submitting') : t('login.submit')}
            {!loading && <ArrowRight size={17} strokeWidth={2} />}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: 12.5, color: 'var(--text-muted)', marginTop: 22 }}>
          {t('login.footer')}
        </p>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: '11px 14px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-tertiary)',
  color: 'var(--text-primary)',
  fontSize: 14,
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
};
