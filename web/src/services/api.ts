const API_BASE_URL = 'http://localhost:8000/api';

function handleUnauthorized(response: Response): void {
  if (response.status === 401) {
    localStorage.removeItem('orbis_user');
    window.location.href = '/login';
  }
}

export const api = {
  // 1. Standard POST (for Login)
  post: async (endpoint: string, data: any, token?: string) => {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
      credentials: 'include', // send/receive httpOnly cookies
    });

    if (response.status === 401) {
      handleUnauthorized(response);
      return;
    }
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'API Error');
    }
    return response.json();
  },

  // 2. Streaming Chat (The RAG Magic)
  chatStream: async (
    message: string,
    token: string,
    onChunk: (text: string) => void
  ) => {
    const headers: HeadersInit = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message }),
      credentials: 'include', // send cookie for server-side auth
    });

    if (response.status === 401) {
      handleUnauthorized(response);
      return;
    }
    if (!response.ok) throw new Error(response.statusText);
    if (!response.body) throw new Error('No response body');

    // Read the stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      onChunk(chunk);
    }
  },

  // 3. Academic Calendar
  getCalendar: async (academicYear = '2025-2026', appliesTo = 'undergraduate') => {
    const params = new URLSearchParams({ academic_year: academicYear, applies_to: appliesTo });
    const response = await fetch(`${API_BASE_URL}/sis/calendar?${params}`, {
      credentials: 'include',
    });
    if (response.status === 401) {
      handleUnauthorized(response);
      return;
    }
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'API Error');
    }
    return response.json();
  },

  // 4. Student Schedule
  getMySchedule: async () => {
    const response = await fetch(`${API_BASE_URL}/sis/schedule/me`, {
      credentials: 'include',
    });
    if (response.status === 401) {
      handleUnauthorized(response);
      return;
    }
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'API Error');
    }
    return response.json();
  },
};