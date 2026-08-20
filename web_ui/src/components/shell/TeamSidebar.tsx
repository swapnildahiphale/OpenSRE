'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ShieldCheck,
  BookOpen,
  ScrollText,
  Brain,
  GitPullRequest,
  Bot,
  Server,
  LayoutDashboard,
  ListChecks,
  ChevronLeft,
} from 'lucide-react';
import { clsx } from 'clsx';
import { AccountMenu } from '@/components/AccountMenu';

const teamNavigation = [
  { name: 'Dashboard', href: '/team', icon: LayoutDashboard },
  { name: 'Investigations', href: '/team/agent-runs', icon: ListChecks },
  { name: 'Agent Topology', href: '/team/agents', icon: Bot },
  { name: 'Tools & MCPs', href: '/team/tools', icon: Server },
  { name: 'Knowledge Base', href: '/team/knowledge', icon: BookOpen },
  { name: 'Team Context', href: '/team/context', icon: ScrollText },
  { name: 'Memory', href: '/team/memory', icon: Brain },
  { name: 'Proposed Changes', href: '/team/pending-changes', icon: GitPullRequest },
  { name: 'Settings', href: '/settings', icon: ShieldCheck },
];

function isNavActive(pathname: string, href: string): boolean {
  if (href === '/team') {
    return pathname === '/team' || pathname === '/team/';
  }
  return pathname === href || pathname.startsWith(href + '/');
}

type Props = {
  collapsed: boolean;
  onToggle: () => void;
};

export function TeamSidebar({ collapsed, onToggle }: Props) {
  const pathname = usePathname();
  const width = collapsed ? 64 : 230;

  return (
    <aside
      className="relative sticky top-[57px] h-[calc(100dvh-57px)] shrink-0 border-r border-slate-200/60 bg-white/40 px-3 py-6 pb-28 backdrop-blur transition-[width] duration-300 ease-out"
      style={{ width }}
    >
      <div className="mb-6 flex items-center justify-between px-3">
        {!collapsed && (
          <span className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
            workspace
          </span>
        )}
        <button
          type="button"
          onClick={onToggle}
          className={clsx(
            'rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700',
            collapsed && 'mx-auto',
          )}
          aria-label="Toggle sidebar"
        >
          <ChevronLeft
            className={clsx(
              'h-3.5 w-3.5 transition-transform',
              collapsed && 'rotate-180',
            )}
          />
        </button>
      </div>

      <nav className="space-y-1 px-1">
        {teamNavigation.map((item) => {
          const isActive = isNavActive(pathname, item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              title={collapsed ? item.name : undefined}
              className={clsx(
                'relative flex items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors',
                isActive
                  ? 'bg-emerald-100/55 text-emerald-700'
                  : 'text-slate-600 hover:bg-slate-100/70 hover:text-slate-900',
                collapsed && 'justify-center px-2',
              )}
            >
              <span
                className={clsx(
                  'absolute -left-[10px] top-1/2 h-[18px] w-[3px] -translate-y-1/2 rounded-sm bg-emerald-500 transition-opacity',
                  isActive ? 'opacity-100' : 'opacity-0',
                )}
                aria-hidden
              />
              <item.icon className="h-[18px] w-[18px] shrink-0" />
              {!collapsed && (
                <span className="truncate text-sm font-medium">{item.name}</span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="absolute bottom-4 left-3 right-3">
        <div className="rounded-xl bg-slate-900/90 p-2">
          <AccountMenu />
        </div>
      </div>
    </aside>
  );
}
