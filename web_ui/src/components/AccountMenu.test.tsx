import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AccountMenu } from './AccountMenu';
import { useIdentity } from '@/lib/useIdentity';

vi.mock('@/lib/useIdentity', () => ({
  useIdentity: vi.fn(),
}));

const baseTeam = {
  role: 'team' as const,
  auth_kind: 'team_token' as const,
  org_id: 'local',
  team_node_id: 'default',
  can_write: true,
  permissions: [] as string[],
};

function openMenu() {
  fireEvent.click(screen.getByRole('button'));
}

describe('AccountMenu', () => {
  beforeEach(() => {
    vi.mocked(useIdentity).mockReset();
  });

  it('shows display name only on collapsed button for SSO', () => {
    vi.mocked(useIdentity).mockReturnValue({
      identity: { ...baseTeam, name: 'Jane Doe', email: 'jane@example.com' },
      error: null,
      loading: false,
      refresh: vi.fn(),
    });
    render(<AccountMenu />);
    const persona = screen.getByText('Jane Doe');
    expect(persona).toBeInTheDocument();
    expect(persona).toHaveAttribute('title', 'jane@example.com');
    expect(screen.queryByText('local')).not.toBeInTheDocument();
    expect(screen.queryByText('default')).not.toBeInTheDocument();

    openMenu();
    expect(screen.getByText('jane@example.com')).toBeInTheDocument();
    expect(screen.getByText('local')).toBeInTheDocument();
    expect(screen.getByText('default')).toBeInTheDocument();
  });

  it('falls back to email when name is missing', () => {
    vi.mocked(useIdentity).mockReturnValue({
      identity: { ...baseTeam, name: null, email: 'jane@example.com' },
      error: null,
      loading: false,
      refresh: vi.fn(),
    });
    render(<AccountMenu />);
    expect(screen.getByText('jane@example.com')).toBeInTheDocument();
    expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument();
    expect(screen.queryByText('local')).not.toBeInTheDocument();

    openMenu();
    expect(screen.getByText('local')).toBeInTheDocument();
    expect(screen.getByText('default')).toBeInTheDocument();
  });

  it('omits a persona row for token-paste team login', () => {
    vi.mocked(useIdentity).mockReturnValue({
      identity: baseTeam,
      error: null,
      loading: false,
      refresh: vi.fn(),
    });
    render(<AccountMenu />);
    expect(screen.queryByText('jane@example.com')).not.toBeInTheDocument();
    expect(screen.queryByText('local')).not.toBeInTheDocument();
    expect(screen.queryByText('default')).not.toBeInTheDocument();
    expect(screen.queryByText('—')).not.toBeInTheDocument();

    openMenu();
    expect(screen.getByText('local')).toBeInTheDocument();
    expect(screen.getByText('default')).toBeInTheDocument();
  });
});
