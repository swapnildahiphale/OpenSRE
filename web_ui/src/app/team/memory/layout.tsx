'use client';

import { PageHeader, TeamPageShell } from '@/components/ui-flow';
import { MemoryTabs } from '@/components/team/MemoryTabs';

export default function MemoryLayout({ children }: { children: React.ReactNode }) {
  return (
    <TeamPageShell
      header={
        <PageHeader
          eyebrow="Team console"
          title="Memory"
          subtitle="Learn from past investigations to improve future ones"
        />
      }
    >
      <MemoryTabs />
      {children}
    </TeamPageShell>
  );
}
