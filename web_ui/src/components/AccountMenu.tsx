'use client';

import { useEffect, useState } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { applyTheme, getTheme, setTheme, type ThemeMode } from '@/lib/theme';
import { ChevronUp, LogOut, Settings, Languages, Moon, Sun, KeyRound } from 'lucide-react';
import Link from 'next/link';
import { clearAuthToken } from '@/lib/authToken';

export function AccountMenu() {
  const { identity, refresh } = useIdentity();
  const [open, setOpen] = useState(false);
  const [theme, setThemeState] = useState<ThemeMode>('light');

  useEffect(() => {
    const t = getTheme();
    setThemeState(t);
    applyTheme(t);
  }, []);


  const logout = async () => {
    await fetch('/api/session/logout', { method: 'POST' }).catch(() => {});
    // Backwards-compat cleanup: ensure any legacy localStorage token is removed so logout is reliable.
    clearAuthToken();
    setOpen(false);
    // Redirect to home page after logout
    window.location.href = '/';
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-2 px-2 py-2 rounded-lg hover:bg-white/5 transition-colors"
      >
        <div className="min-w-0 text-left">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-wider text-stone-500 font-medium">Org</span>
            <span className="text-sm font-semibold text-white truncate">
              {identity?.org_id ?? '—'}
            </span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[10px] uppercase tracking-wider text-stone-500 font-medium">
              {identity?.role === 'admin' ? 'Role' : 'Team'}
            </span>
            <span className="text-xs text-forest-light font-medium truncate">
              {identity?.role === 'admin' ? 'Admin' : identity?.team_node_id ?? '—'}
            </span>
          </div>
        </div>
        <ChevronUp className="w-4 h-4 text-stone-500" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute bottom-12 left-0 z-40 w-60 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl shadow-xl overflow-hidden">
            <div className="p-2">
              <button
                onClick={() => {
                  const next: ThemeMode = theme === 'dark' ? 'light' : 'dark';
                  setThemeState(next);
                  setTheme(next);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700"
              >
                {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                Theme: {theme === 'dark' ? 'Dark' : 'Light'}
              </button>

              <button
                className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 opacity-70"
                disabled
                title="Language selection coming soon"
              >
                <Languages className="w-4 h-4" />
                Language (soon)
              </button>

              <Link
                href="/settings"
                onClick={() => setOpen(false)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700"
              >
                <Settings className="w-4 h-4" />
                Preferences
              </Link>

              <button
                onClick={logout}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg hover:bg-clay-light/10 dark:hover:bg-clay/20 text-clay"
              >
                <LogOut className="w-4 h-4" />
                Log out
              </button>
            </div>

            <div className="border-t border-stone-200 dark:border-stone-700 p-2 bg-stone-50 dark:bg-stone-900/30">
              <div className="text-[11px] text-stone-500 flex items-center gap-2 px-2">
                <KeyRound className="w-3 h-3" />
                Switch token via logout → sign in
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}


