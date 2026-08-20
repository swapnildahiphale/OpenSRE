import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RootChrome } from './RootChrome';
import { useInvestigationLauncher } from './InvestigationLauncherContext';
import { useIdentity } from '@/lib/useIdentity';

vi.mock('@/lib/useIdentity', () => ({
  useIdentity: vi.fn(),
}));

vi.mock('@/components/Sidebar', () => ({
  Sidebar: () => <div data-testid="legacy-sidebar" />,
}));

vi.mock('./AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-shell">{children}</div>
  ),
}));

function Probe() {
  const { isOpen } = useInvestigationLauncher();
  return <span data-testid="hook-ok">{isOpen ? 'open' : 'closed'}</span>;
}

describe('RootChrome', () => {
  beforeEach(() => {
    vi.mocked(useIdentity).mockReset();
  });

  it('provides InvestigationLauncher while identity is null', () => {
    vi.mocked(useIdentity).mockReturnValue({
      identity: null,
      error: null,
      loading: false,
      refresh: vi.fn(),
    });

    render(
      <RootChrome>
        <Probe />
      </RootChrome>,
    );

    expect(screen.getByTestId('hook-ok')).toHaveTextContent('closed');
    expect(screen.getByTestId('legacy-sidebar')).toBeInTheDocument();
  });

  it('provides InvestigationLauncher for non-team role', () => {
    vi.mocked(useIdentity).mockReturnValue({
      identity: {
        role: 'admin',
        auth_kind: 'admin_token',
        can_write: true,
        permissions: [],
      },
      error: null,
      loading: false,
      refresh: vi.fn(),
    });

    render(
      <RootChrome>
        <Probe />
      </RootChrome>,
    );

    expect(screen.getByTestId('hook-ok')).toHaveTextContent('closed');
    expect(screen.getByTestId('legacy-sidebar')).toBeInTheDocument();
  });

  it('uses AppShell for team role', () => {
    vi.mocked(useIdentity).mockReturnValue({
      identity: {
        role: 'team',
        auth_kind: 'team_token',
        can_write: true,
        permissions: [],
      },
      error: null,
      loading: false,
      refresh: vi.fn(),
    });

    render(
      <RootChrome>
        <Probe />
      </RootChrome>,
    );

    expect(screen.getByTestId('app-shell')).toBeInTheDocument();
    expect(screen.getByTestId('hook-ok')).toHaveTextContent('closed');
  });
});
