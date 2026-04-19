import { createContext, useContext, useState, useEffect, type ReactNode, type Dispatch, type SetStateAction } from 'react';
import type { Message } from '../types';

const API_BASE_URL = 'http://localhost:8000/api';

export interface AuthUser {
  token: string;
  userType: string;
  firstName: string;
  lastName: string;
  email: string;
}

interface AuthContextType {
  user: AuthUser | null;
  login: (userData: AuthUser) => void;
  logout: () => void;
  chatHistory: Message[];
  setChatHistory: Dispatch<SetStateAction<Message[]>>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const STORAGE_KEY = 'orbis_user';
const LEGACY_KEY = 'token';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [chatHistory, setChatHistory] = useState<Message[]>([]);
  const [user, setUser] = useState<AuthUser | null>(() => {
    // Try to restore from localStorage
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        return JSON.parse(stored) as AuthUser;
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }

    // One-time migration: read old "token" key
    const legacyToken = localStorage.getItem(LEGACY_KEY);
    if (legacyToken) {
      localStorage.removeItem(LEGACY_KEY);
      // We only have the token sentinel, not user info — create a minimal user
      const migrated: AuthUser = {
        token: legacyToken,
        userType: 'student',
        firstName: 'User',
        lastName: '',
        email: '',
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated));
      return migrated;
    }

    return null;
  });

  const login = (userData: AuthUser) => {
    setUser(userData);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(userData));
  };

  const logout = () => {
    setUser(null);
    setChatHistory([]);
    localStorage.removeItem(STORAGE_KEY);
  };

  // Background token refresh — keeps session alive every 20 minutes
  useEffect(() => {
    if (!user) return;

    const REFRESH_INTERVAL_MS = 20 * 60 * 1000; // 20 minutes

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: 'POST',
          credentials: 'include', // sends the httpOnly cookie
        });
        if (response.status === 401) {
          // Session truly expired — log out
          logout();
          window.location.href = '/login';
        }
        // On success: backend sets a new cookie automatically.
        // No state update needed — the cookie is httpOnly and
        // managed entirely by the browser.
      } catch {
        // Network error — do not log out, just try again next interval
      }
    }, REFRESH_INTERVAL_MS);

    return () => clearInterval(interval); // cleanup on logout
  }, [user]);

  return (
    <AuthContext.Provider value={{ user, login, logout, chatHistory, setChatHistory }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
