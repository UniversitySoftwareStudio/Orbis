import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderPage } from './testUtils';
import { ProfilePage } from '../ProfilePage';
import { api } from '../../services/api';

vi.mock('../../services/api', () => ({
  api: { getProfile: vi.fn() },
}));

const mockApi = api as unknown as { getProfile: ReturnType<typeof vi.fn> };

describe('ProfilePage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders identity, academic fields and active flags', async () => {
    mockApi.getProfile.mockResolvedValue({
      first_name: 'Ada', last_name: 'Lovelace', email: 'ada@bilgiedu.net',
      user_type: 'student', student_id: '2025001', gpa: 3.5,
      department: 'Computer Engineering', faculty: 'Engineering',
      program_level: 'undergraduate', academic_year: 2, semester_number: 3,
      total_credits_completed: 30, total_credits_enrolled: 15,
      is_on_probation: false, has_advisor_hold: true, has_financial_hold: false,
      is_exchange_student: false, is_double_major: false, is_minor: false,
    });

    renderPage(<ProfilePage />);
    await waitFor(() => expect(screen.getByText('Ada Lovelace')).toBeInTheDocument());
    expect(screen.getByText('Computer Engineering')).toBeInTheDocument();
    expect(screen.getByText('Advisor Hold')).toBeInTheDocument();
    // A flag that is false should not render.
    expect(screen.queryByText('On Probation')).not.toBeInTheDocument();
  });

  it('shows no-flags message when none active', async () => {
    mockApi.getProfile.mockResolvedValue({
      first_name: 'Bob', last_name: 'X', email: 'b@x.net', user_type: 'student',
      student_id: '1', gpa: null, department: null, faculty: null, program_level: null,
      academic_year: null, semester_number: null, total_credits_completed: null,
      total_credits_enrolled: null, is_on_probation: false, has_advisor_hold: false,
      has_financial_hold: false, is_exchange_student: false, is_double_major: false, is_minor: false,
    });
    renderPage(<ProfilePage />);
    await waitFor(() => expect(screen.getByText('No active status flags.')).toBeInTheDocument());
  });
});
