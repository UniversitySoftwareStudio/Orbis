import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderPage } from './testUtils';
import { RegulationsPage } from '../RegulationsPage';
import { api } from '../../services/api';

vi.mock('../../services/api', () => ({
  api: { getMyRegulations: vi.fn(), updateRegulationStatus: vi.fn() },
}));

const mockApi = api as unknown as {
  getMyRegulations: ReturnType<typeof vi.fn>;
  updateRegulationStatus: ReturnType<typeof vi.fn>;
};

const sampleItem = {
  id: 'abc-123',
  urgency: 'high',
  status: 'active',
  reason: 'Your GPA is below threshold.',
  assigned_at: '2026-01-01T00:00:00',
  rule_text: 'Meet your advisor if your GPA falls below 1.80.',
  applies_to: 'undergraduate students',
  trigger: 'GPA below 1.80',
  deadline: 'within 2 weeks',
  consequence: 'registration hold',
  authority: 'faculty board',
  blocking: true,
  valid_until: null,
};

describe('RegulationsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists assigned regulations', async () => {
    mockApi.getMyRegulations.mockResolvedValue([sampleItem]);
    renderPage(<RegulationsPage />);
    await waitFor(() => expect(screen.getByText(/Meet your advisor/)).toBeInTheDocument());
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText(/registration hold/)).toBeInTheDocument();
  });

  it('marks a regulation as actioned and updates the status label', async () => {
    mockApi.getMyRegulations.mockResolvedValue([sampleItem]);
    mockApi.updateRegulationStatus.mockResolvedValue({ ...sampleItem, status: 'actioned' });

    renderPage(<RegulationsPage />);
    await waitFor(() => expect(screen.getByText('Mark as Done')).toBeInTheDocument());

    await userEvent.click(screen.getByText('Mark as Done'));

    await waitFor(() =>
      expect(mockApi.updateRegulationStatus).toHaveBeenCalledWith('abc-123', 'actioned'),
    );
    // After update, the action buttons disappear (status no longer 'active').
    await waitFor(() => expect(screen.queryByText('Mark as Done')).not.toBeInTheDocument());
  });

  it('renders empty state', async () => {
    mockApi.getMyRegulations.mockResolvedValue([]);
    renderPage(<RegulationsPage />);
    await waitFor(() =>
      expect(screen.getByText('No regulations are currently assigned to you.')).toBeInTheDocument(),
    );
  });
});
