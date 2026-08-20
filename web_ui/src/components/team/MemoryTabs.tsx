'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { clsx } from 'clsx';

const TABS = [
  {
    label: 'Overview',
    href: '/team/memory',
    isActive: (pathname: string) =>
      pathname === '/team/memory' || pathname === '/team/memory/',
  },
  {
    label: 'Episodes',
    href: '/team/memory/episodes',
    isActive: (pathname: string) => pathname.startsWith('/team/memory/episodes'),
  },
  {
    label: 'Search',
    href: '/team/memory/search',
    isActive: (pathname: string) => pathname.startsWith('/team/memory/search'),
  },
  {
    label: 'Strategies',
    href: '/team/memory/strategies',
    isActive: (pathname: string) => pathname.startsWith('/team/memory/strategies'),
  },
] as const;

export function MemoryTabs() {
  const pathname = usePathname();

  return (
    <nav aria-label="Memory sections" className="border-b border-slate-200/80 -mt-2">
      <div className="flex gap-1 overflow-x-auto scrollbar-none">
        {TABS.map((tab) => {
          const active = tab.isActive(pathname);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={clsx(
                'shrink-0 px-3 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
                active
                  ? 'border-emerald-600 text-emerald-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700',
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
