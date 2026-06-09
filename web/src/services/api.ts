const API_BASE_URL = 'http://localhost:8000/api';

function handleUnauthorized(response: Response): void {
  if (response.status === 401) {
    localStorage.removeItem('orbis_user');
    window.location.href = '/login';
  }
}

// Shared authenticated GET → JSON helper (mirrors the inline pattern used by
// the older endpoints: cookie credentials, 401 redirect, detail-aware errors).
async function getJson(endpoint: string) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    credentials: 'include',
  });
  if (response.status === 401) { handleUnauthorized(response); return; }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'API Error');
  }
  return response.json();
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

  // 2. Streaming Chat — agentic RAG over SSE. Emits step/source/chunk/done events.
  chatStream: async (
    message: string,
    token: string,
    onEvent: (type: string, data: any) => void,
    focusedSource?: {
      title: string;
      url: string;
      type?: string;
      category?: string;
      language?: string;
      snippet?: string;
      content?: string;
    } | null,
  ) => {
    const headers: HeadersInit = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message, focused_source: focusedSource || null }),
      credentials: 'include',
    });

    if (response.status === 401) { handleUnauthorized(response); return; }
    if (!response.ok) throw new Error(response.statusText);
    if (!response.body) throw new Error('No response body');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep: number;
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        let eventType = 'message';
        const dataLines: string[] = [];
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) eventType = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
        }
        if (dataLines.length === 0) continue;
        try { onEvent(eventType, JSON.parse(dataLines.join('\n'))); } catch { /* ignore */ }
      }
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

  // 5. My Assignments
  getMyAssignments: async () => {
    const response = await fetch(`${API_BASE_URL}/assignments/me`, {
      credentials: 'include',
    });
    if (response.status === 401) { handleUnauthorized(response); return; }
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'API Error');
    }
    return response.json();
  },

  // 6. Submit Assignment
  submitAssignment: async (assignmentId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE_URL}/assignments/${assignmentId}/submit`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });
    if (response.status === 401) { handleUnauthorized(response); return; }
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'API Error');
    }
    return response.json();
  },

  // 6b. Submit Assignment (streaming) — emits agent reasoning steps via SSE.
  submitAssignmentStream: async (
    assignmentId: number,
    file: File,
    onEvent: (type: string, data: any) => void,
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE_URL}/assignments/${assignmentId}/submit/stream`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });
    if (response.status === 401) { handleUnauthorized(response); return; }
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'API Error');
    }
    if (!response.body) throw new Error('No response body');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line.
      let sep: number;
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        let eventType = 'message';
        const dataLines: string[] = [];
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) eventType = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
        }
        if (dataLines.length === 0) continue;
        try {
          onEvent(eventType, JSON.parse(dataLines.join('\n')));
        } catch {
          // ignore malformed frames
        }
      }
    }
  },

  flagSubmissionRejection: async (submissionId: number, reason: string) => {
    const response = await fetch(`${API_BASE_URL}/assignments/submissions/${submissionId}/flag`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
      credentials: 'include',
    });
    if (response.status === 401) { handleUnauthorized(response); return; }
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

  // 7. Dashboard aggregate
  getDashboard: () => getJson('/sis/dashboard'),

  // 8. Profile
  getProfile: () => getJson('/sis/profile/me'),

  // 9. Transcript
  getTranscript: () => getJson('/sis/transcript/me'),

  // 10. Current enrolled courses
  getMyCourses: () => getJson('/sis/courses/me'),

  // 11. My regulation assignments
  getMyRegulations: () => getJson('/regulations/me'),

  // 12. Update a regulation assignment status (actioned | dismissed | active)
  updateRegulationStatus: async (assignmentId: string, status: string) => {
    const response = await fetch(
      `${API_BASE_URL}/regulations/assignments/${assignmentId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
        credentials: 'include',
      },
    );
    if (response.status === 401) { handleUnauthorized(response); return; }
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'API Error');
    }
    return response.json();
  },

  // 13. Run regulation self-check — streams the assignment agent audit trail.
  runRegulationCheckStream: async (
    onEvent: (type: string, data: any) => void,
  ) => {
    const response = await fetch(`${API_BASE_URL}/regulations/check/stream`, {
      method: 'POST',
      credentials: 'include',
    });
    if (response.status === 401) { handleUnauthorized(response); return; }
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'API Error');
    }
    if (!response.body) throw new Error('No response body');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep: number;
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        let eventType = 'message';
        const dataLines: string[] = [];
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) eventType = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
        }
        if (dataLines.length === 0) continue;
        try { onEvent(eventType, JSON.parse(dataLines.join('\n'))); } catch { /* ignore malformed frames */ }
      }
    }
  },
};
