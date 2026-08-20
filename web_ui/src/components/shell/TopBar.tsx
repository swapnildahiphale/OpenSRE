'use client';

import Link from 'next/link';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui-flow/Button';
import { OpenSreBrandLogo } from '@/components/brand/OpenSreBrandLogo';
import { useInvestigationLauncher } from './InvestigationLauncherContext';

type Props = {
  sidebarWidth: number;
};

export function TopBar({ sidebarWidth }: Props) {
  const { open } = useInvestigationLauncher();
  const collapsed = sidebarWidth <= 64;

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/60 bg-white/75 backdrop-blur">
      <div className="flex items-center py-3">
        <div
          className="flex shrink-0 justify-center transition-[width] duration-300 ease-out"
          style={{ width: sidebarWidth }}
        >
          <Link
            href="/team"
            className="flex items-center justify-center"
            aria-label="OpenSRE home"
          >
            <OpenSreBrandLogo
              variant={collapsed ? 'spinner' : 'wordmark'}
              surface="topbar"
              priority
            />
          </Link>
        </div>
        <div className="flex min-w-0 flex-1 items-center gap-3 px-6">
          <span className="hidden text-[11px] uppercase tracking-[0.22em] text-slate-400 sm:inline">
            team console
          </span>
          <Button
            variant="primary"
            className="ml-auto"
            onClick={open}
            title="New Investigation (⌘I)"
          >
            <Plus className="h-3.5 w-3.5" />
            New Investigation
            <span className="ml-0.5 font-mono text-[11px] text-emerald-600/75">
              ⌘I
            </span>
          </Button>
        </div>
      </div>
    </header>
  );
}
