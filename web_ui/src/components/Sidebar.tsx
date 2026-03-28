'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ShieldCheck,
  Menu,
  X,
  Network,
  Server,
  BookOpen,
  Brain,
  GitPullRequest,
  Bot,
  Cog,
  LayoutDashboard,
  Key,
} from 'lucide-react';
import { clsx } from 'clsx';
import { LogoFull } from './Logo';
import { useState } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { AccountMenu } from './AccountMenu';

// Navigation for team users
const teamNavigation = [
  { name: 'Dashboard', href: '/team', icon: LayoutDashboard },
  { name: 'Agent Topology', href: '/team/agents', icon: Bot },
  { name: 'Tools & MCPs', href: '/team/tools', icon: Server },
  { name: 'Knowledge Base', href: '/team/knowledge', icon: BookOpen },
  { name: 'Memory', href: '/team/memory', icon: Brain },
  { name: 'Proposed Changes', href: '/team/pending-changes', icon: GitPullRequest },
  { name: 'Agent Runs', href: '/team/agent-runs', icon: Bot },
  { name: 'Settings', href: '/settings', icon: ShieldCheck },
];

// Navigation for admin users
const adminNavigation = [
  { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
  { name: 'Org Tree', href: '/admin/org-tree', icon: Network },
  { name: 'Org Configurations', href: '/admin/config', icon: Cog },
  { name: 'Token Management', href: '/admin/token-management', icon: Key },
  { name: 'Settings', href: '/settings', icon: ShieldCheck },
];

// Navigation when not logged in
const guestNavigation = [
  { name: 'Sign In', href: '/settings', icon: ShieldCheck },
];

export function Sidebar() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const { identity } = useIdentity();
  const nav =
    identity?.role === 'admin'
      ? adminNavigation
      : identity?.role === 'team'
        ? teamNavigation
        : guestNavigation;

  return (
    <>
      {/* Mobile Menu Button */}
      <button 
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-stone-50 dark:bg-stone-800 rounded-md shadow-md border border-stone-200 dark:border-stone-700"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Sidebar Container */}
      <div className={clsx(
        "fixed inset-y-0 left-0 z-40 w-64 bg-stone-900 border-r border-stone-800 transform transition-transform duration-200 ease-in-out lg:translate-x-0",
        isOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="flex flex-col h-full">
          {/* Logo Area */}
          <div className="h-32 flex items-center px-6 border-b border-stone-800">
            <LogoFull />
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
            {nav.map((item) => {
              const isActive = pathname.startsWith(item.href) && item.href !== '/' ? true : pathname === item.href;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={clsx(
                    "flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors group",
                    isActive
                      ? "bg-forest text-white"
                      : "text-stone-400 hover:bg-white/5"
                  )}
                >
                  <item.icon className={clsx("w-5 h-5 mr-3 transition-colors", isActive ? "text-white" : "text-stone-500 group-hover:text-stone-400")} />
                  {item.name}
                </Link>
              );
            })}
          </nav>

          {/* User / Footer */}
          <div className="p-4 border-t border-stone-800">
            <AccountMenu />
          </div>
        </div>
      </div>
      
      {/* Overlay for mobile */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-30 bg-black/20 backdrop-blur-sm lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}
    </>
  );
}
