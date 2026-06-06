import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderPage } from './testUtils';
import { TranscriptPage } from '../TranscriptPage';
import { api } from '../../services/api';

vi.mock('../../services/api', () => ({
  api: { getTranscript: vi.fn() },
}));

const mockApi = api as unknown as { getTranscript: ReturnType<typeof vi.fn> };

describe('TranscriptPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders grouped entries with cumulative gpa', async () => {
    mockApi.getTranscript.mockResolvedValue({
      entries: [
        { course_code: 'CS101', course_name: 'Intro to CS', term: 'fall 2025', credits: 3, grade_letter: 'A-', grade_numeric: 3.7 },
        { course_code: 'MATH101', course_name: 'Calculus', term: 'fall 2025', credits: 4, grade_letter: 'B', grade_numeric: 3.0 },
      ],
      cumulative_gpa: 3.3,
      total_credits: 7,
    });

    renderPage(<TranscriptPage />);
    await waitFor(() => expect(screen.getByText('Intro to CS')).toBeInTheDocument());
    expect(screen.getByText('Calculus')).toBeInTheDocument();
    expect(screen.getByText('3.3')).toBeInTheDocument();
  });

  it('renders empty state', async () => {
    mockApi.getTranscript.mockResolvedValue({ entries: [], cumulative_gpa: null, total_credits: 0 });
    renderPage(<TranscriptPage />);
    await waitFor(() => expect(screen.getByText('No completed courses found.')).toBeInTheDocument());
  });
});
