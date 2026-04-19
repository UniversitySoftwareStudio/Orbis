import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { login } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'tr' ? 'en' : 'tr';
    i18n.changeLanguage(newLang);
    localStorage.setItem('orbis_lang', newLang);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
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

      navigate('/chat');
    } catch (err: any) {
      console.error(err);
      alert(t('login.error') + ': ' + (err.message || JSON.stringify(err)));
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', position: 'relative' }}>
      {/* Language toggle — top right */}
      <button
        onClick={toggleLanguage}
        style={{
          position: 'absolute',
          top: 16,
          right: 16,
          background: 'transparent',
          border: '1px solid #ddd',
          borderRadius: 4,
          padding: '4px 10px',
          cursor: 'pointer',
          fontSize: 13,
          color: '#666',
        }}
      >
        {i18n.language === 'tr' ? 'TR | EN' : 'EN | TR'}
      </button>

      <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 10, width: 300 }}>
        <h2>🎓 {t('login.title')}</h2>
        <input
          placeholder={t('login.email')}
          value={username}
          onChange={e => setUsername(e.target.value)}
          style={{ padding: 10, borderRadius: 4, border: '1px solid #ddd' }}
        />
        <input
          type="password"
          placeholder={t('login.password')}
          value={password}
          onChange={e => setPassword(e.target.value)}
          style={{ padding: 10, borderRadius: 4, border: '1px solid #ddd' }}
        />
        <button
          type="submit"
          style={{ padding: 10, background: '#007bff', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}
        >
          {t('login.submit')}
        </button>
      </form>
    </div>
  );
}
