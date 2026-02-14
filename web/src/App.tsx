import { useState } from 'react';
import { api } from './services/api';
import './index.css'; // Assuming you have basic styles or Tailwind
import ReactMarkdown from 'react-markdown'

// Types
interface Message {
  role: 'user' | 'assistant';
  content: string;
}

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  
  // Chat State
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // --- ACTIONS ---

const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.post('/auth/login', { 
        email: username,
        password: password 
      }); 
      
      if (res.access_token) {
        setToken(res.access_token);
        localStorage.setItem('token', res.access_token);
      }
    } catch (err: any) {
      console.error(err);
      alert('Login Failed: ' + JSON.stringify(err.message || err));
    }
  };

const handleSend = async () => {
    if (!input.trim() || !token) return;

    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);

    try {
      // Add a placeholder for the AI response
      setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

      await api.chatStream(userMsg, token, (chunk) => {
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

  const handleLogout = () => {
    setToken(null);
    localStorage.removeItem('token');
    setMessages([]);
  };

  // --- RENDER ---

  if (!token) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: '50px' }}>
        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '10px', width: '300px' }}>
          <h2>🎓 UniChat Login</h2>
          <input 
            placeholder="Username" 
            value={username} 
            onChange={e => setUsername(e.target.value)}
            style={{ padding: '10px' }}
          />
          <input 
            type="password" 
            placeholder="Password" 
            value={password} 
            onChange={e => setPassword(e.target.value)} 
            style={{ padding: '10px' }}
          />
          <button type="submit" style={{ padding: '10px', background: '#007bff', color: 'white', border: 'none', cursor: 'pointer' }}>
            Login
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="app" style={{ maxWidth: '800px', margin: '0 auto', padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h3>🎓 UniChat Agent</h3>
        <button onClick={handleLogout} style={{ padding: '5px 10px', cursor: 'pointer' }}>Logout</button>
      </header>

      <div style={{ 
        border: '1px solid #ccc', 
        height: '500px', 
        overflowY: 'auto', 
        padding: '20px', 
        borderRadius: '8px',
        backgroundColor: '#f9f9f9',
        marginBottom: '20px'
      }}>
        {messages.length === 0 && <p style={{ color: '#888', textAlign: 'center' }}>Ask me about courses, regulations, or campus life!</p>}
        
        {messages.map((msg, i) => (
          <div key={i} style={{ 
            display: 'flex', 
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '10px'
          }}>
            <div style={{ 
              maxWidth: '70%', 
              padding: '10px 15px', 
              borderRadius: '15px', 
              backgroundColor: msg.role === 'user' ? '#007bff' : '#e9ecef',
              color: msg.role === 'user' ? 'white' : 'black',
              whiteSpace: 'pre-wrap'
            }}>
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          </div>
        ))}
        {isLoading && <div style={{ color: '#888', fontStyle: 'italic' }}>Agent is typing...</div>}
      </div>

      <div style={{ display: 'flex', gap: '10px' }}>
        <input 
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="Type your question..."
          style={{ flex: 1, padding: '15px', borderRadius: '5px', border: '1px solid #ddd' }}
        />
        <button 
          onClick={handleSend} 
          disabled={isLoading}
          style={{ padding: '0 25px', background: '#007bff', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default App;