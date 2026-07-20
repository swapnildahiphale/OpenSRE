'use client';

import { Brain } from 'lucide-react';
import { TeamPageHeader } from '@/components/team/TeamPageHeader';
import { MemoryTabs } from '@/components/team/MemoryTabs';

export default function MemoryLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <TeamPageHeader
        icon={Brain}
        title="Memory"
        subtitle="Learn from past investigations to improve future ones"
      />
      <MemoryTabs />
      {children}
    </div>
  );
}
