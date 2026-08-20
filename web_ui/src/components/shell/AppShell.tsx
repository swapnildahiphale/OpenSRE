'use client';

import { useCallback, useEffect, useSyncExternalStore, type ReactNode } from 'react';
import { TopBar } from './TopBar';
import { TeamSidebar } from './TeamSidebar';
import { useInvestigationLauncher } from './InvestigationLauncherContext';
import { NewInvestigationDrawer } from '@/components/NewInvestigationDrawer';

const SIDEBAR_STORAGE_KEY = 'opensre-ui:sb';

const sidebarCollapsedListeners = new Set<() => void>();

function notifySidebarCollapsedListeners() {
  sidebarCollapsedListeners.forEach((listener) => listener());
}

function isEditableTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable;
}

function subscribeSidebarCollapsed(onStoreChange: () => void) {
  sidebarCollapsedListeners.add(onStoreChange);
  const handler = (e: StorageEvent) => {
    if (e.key === SIDEBAR_STORAGE_KEY) onStoreChange();
  };
  window.addEventListener('storage', handler);
  return () => {
    sidebarCollapsedListeners.delete(onStoreChange);
    window.removeEventListener('storage', handler);
  };
}

function getSidebarCollapsedSnapshot(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'collapsed';
  } catch {
    return false;
  }
}

function ShellInner({ children }: { children: ReactNode }) {
  const { isOpen, open, close, onComplete } = useInvestigationLauncher();
  const collapsed = useSyncExternalStore(
    subscribeSidebarCollapsed,
    getSidebarCollapsedSnapshot,
    () => false,
  );

  const setCollapsed = useCallback((next: boolean | ((prev: boolean) => boolean)) => {
    const value = typeof next === 'function' ? next(getSidebarCollapsedSnapshot()) : next;
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, value ? 'collapsed' : 'expanded');
    } catch {
      /* ignore */
    }
    notifySidebarCollapsedListeners();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'i') {
        if (isEditableTarget(e.target)) return;
        e.preventDefault();
        open();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const sidebarWidth = collapsed ? 64 : 230;

  return (
    <>
      <TopBar sidebarWidth={sidebarWidth} />
      <div className="flex min-h-[calc(100dvh-57px)]">
        <TeamSidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
        />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
      <NewInvestigationDrawer open={isOpen} onClose={close} onComplete={onComplete} />
    </>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  // Consumes InvestigationLauncherProvider from RootChrome (no nested provider).
  return <ShellInner>{children}</ShellInner>;
}
