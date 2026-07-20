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
    <nav
      aria-label="Memory sections"
      className="border-b border-stone-200 dark:border-stone-700 -mx-1"
    >
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
                  ? 'border-forest text-forest dark:text-forest-light'
                  : 'border-transparent text-stone-500 hover:text-stone-700 dark:hover:text-stone-300',
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
