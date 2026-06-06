import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderPage } from './testUtils';
import { DashboardPage } from '../DashboardPage';
import { api } from '../../services/api';

vi.mock('../../services/api', () => ({
  api: { getDashboard: vi.fn() },
}));

const mockApi = api as unknown as { getDashboard: ReturnType<typeof vi.fn> };

describe('DashboardPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows loading then renders stats and deadlines', async () => {
    mockApi.getDashboard.mockResolvedValue({
      first_name: 'Ada',
      is_student: true,
      stats: {
        gpa: 3.5,
        total_credits_completed: 30,
        total_credits_enrolled: 15,
        enrolled_course_count: 4,
        pending_assignment_count: 2,
        active_regulation_count: 1,
      },
      upcoming_deadlines: [{ title: 'Project 1', due_date: '2026-06-10T00:00:00', kind: 'assignment' }],
      upcoming_calendar: [],
    });

    renderPage(<DashboardPage />);
    expect(screen.getByText('Loading dashboard...')).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText('Welcome, Ada')).toBeInTheDocument());
    expect(screen.getByText('3.5')).toBeInTheDocument();
    expect(screen.getByText('Project 1')).toBeInTheDocument();
    expect(screen.getByText('Enrolled Courses')).toBeInTheDocument();
  });

  it('renders empty deadlines message', async () => {
    mockApi.getDashboard.mockResolvedValue({
      first_name: 'Bob',
      is_student: true,
      stats: { gpa: null, total_credits_completed: null, total_credits_enrolled: null, enrolled_course_count: 0, pending_assignment_count: 0, active_regulation_count: 0 },
      upcoming_deadlines: [],
      upcoming_calendar: [],
    });

    renderPage(<DashboardPage />);
    await waitFor(() => expect(screen.getByText('No upcoming deadlines.')).toBeInTheDocument());
  });
});
