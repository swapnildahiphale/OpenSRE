'use client';

import { useIdentity } from '@/lib/useIdentity';
import { Sidebar } from '@/components/Sidebar';
import { AppShell } from './AppShell';
import { InvestigationLauncherProvider } from './InvestigationLauncherContext';

export function RootChrome({ children }: { children: React.ReactNode }) {
  const { identity } = useIdentity();

  const chrome =
    identity?.role === 'team' ? (
      <AppShell>{children}</AppShell>
    ) : (
      <div className="min-h-screen">
        <Sidebar />
        <main className="min-h-screen transition-all duration-200 lg:pl-64">
          {children}
        </main>
      </div>
    );

  // Always wrap page children so team routes can call useInvestigationLauncher()
  // during identity bootstrap and before RequireRole gates render.
  return <InvestigationLauncherProvider>{chrome}</InvestigationLauncherProvider>;
}
