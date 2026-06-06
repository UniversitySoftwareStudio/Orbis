import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderPage } from './testUtils';
import { CoursesPage } from '../CoursesPage';
import { api } from '../../services/api';

vi.mock('../../services/api', () => ({
  api: { getMyCourses: vi.fn() },
}));

const mockApi = api as unknown as { getMyCourses: ReturnType<typeof vi.fn> };

describe('CoursesPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders enrolled course cards with slots', async () => {
    mockApi.getMyCourses.mockResolvedValue([
      {
        course_code: 'CS102', course_name: 'Data Structures', section_number: '02',
        section_type: 'LECTURE', instructor_name: 'Dr. Hopper', status: 'enrolled',
        slots: [{ day_of_week: 'MON', start_time: '09:00:00', end_time: '11:00:00', location: 'B-201', is_online: false }],
      },
    ]);

    renderPage(<CoursesPage />);
    await waitFor(() => expect(screen.getByText('CS102 — Data Structures')).toBeInTheDocument());
    expect(screen.getByText('Dr. Hopper')).toBeInTheDocument();
    expect(screen.getByText('B-201')).toBeInTheDocument();
    expect(screen.getByText('09:00–11:00')).toBeInTheDocument();
  });

  it('renders empty state', async () => {
    mockApi.getMyCourses.mockResolvedValue([]);
    renderPage(<CoursesPage />);
    await waitFor(() => expect(screen.getByText('You are not enrolled in any courses.')).toBeInTheDocument());
  });
});
