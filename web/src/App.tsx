import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { CalendarPage } from './pages/CalendarPage';
import { SchedulePage } from './pages/SchedulePage';
import { AssignmentsPage } from './pages/AssignmentsPage';
import { DashboardPage } from './pages/DashboardPage';
import { ProfilePage } from './pages/ProfilePage';
import { TranscriptPage } from './pages/TranscriptPage';
import { CoursesPage } from './pages/CoursesPage';
import { RegulationsPage } from './pages/RegulationsPage';
import { CatalogPage } from './pages/CatalogPage';
import { NotificationsPage } from './pages/NotificationsPage';
import { SettingsPage } from './pages/SettingsPage';
import { Sidebar } from './components/Sidebar';
import { ChatWidget } from './components/ChatWidget';
import './index.css';

function ProtectedLayout() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <Sidebar />
      <main style={{ flex: 1, overflow: 'auto' }}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/schedule" element={<SchedulePage />} />
          <Route path="/assignments" element={<AssignmentsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/transcript" element={<TranscriptPage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/regulations" element={<RegulationsPage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
      <ChatWidget />
    </div>
  );
}

function PublicRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  // Allow the /login?demo=1 auto-login to run even if a stale session exists.
  const forceLogin = new URLSearchParams(window.location.search).get('demo') === '1';
  return user && !forceLogin ? <Navigate to="/dashboard" replace /> : <>{children}</>;
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
            <Route path="/*" element={<ProtectedLayout />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
