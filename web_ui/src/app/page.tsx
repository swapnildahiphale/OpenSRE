'use client';

import Link from 'next/link';
import { useIdentity } from '@/lib/useIdentity';
import { Shield, Network, Bot, Settings } from 'lucide-react';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const { identity, loading, error } = useIdentity();
  const router = useRouter();

  // No "home" for the enterprise product; route to role landing.
  useEffect(() => {
    if (loading) return;
    if (!identity) return;
    router.replace(identity.role === 'admin' ? '/admin' : '/team');
  }, [identity, loading, router]);

  return (
    <div className="p-8 space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">OpenSRE Config UI</h1>
        <p className="text-stone-500 dark:text-stone-400">
          Manage team configuration (team mode) and org structure / tokens (admin mode).
        </p>
      </div>

      <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 shadow-sm p-5 space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold text-stone-900 dark:text-white">Session</div>
            <div className="text-xs text-stone-500 mt-1">
              {loading
                ? 'Checking token…'
                : identity
                  ? `Role: ${identity.role} • Auth: ${identity.auth_kind} • Org: ${identity.org_id ?? '—'}`
                  : 'Not signed in'}
            </div>
          </div>
          <Link
            href="/settings"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-forest text-white hover:bg-forest-dark dark:bg-forest dark:text-white dark:hover:bg-forest-dark transition-colors"
          >
            <Settings className="w-4 h-4" />
            Token / Settings
          </Link>
        </div>

        {!loading && !identity && (
          <div className="text-sm text-stone-600 dark:text-stone-300">
            Paste an <strong>admin token</strong> or <strong>team token</strong> in <Link className="underline" href="/settings">Settings</Link>{' '}
            to enable the correct pages.
            {error ? <div className="mt-2 text-xs text-clay">Error: {error}</div> : null}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 shadow-sm p-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-stone-900 dark:text-white">
            <Bot className="w-4 h-4" /> Team mode
          </div>
          <p className="text-sm text-stone-600 dark:text-stone-300">
            View effective config + lineage and manage team overrides.
          </p>
          <Link
            href="/configuration"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-forest text-white hover:bg-forest-dark transition-colors"
          >
            Open Team Configuration
          </Link>
        </div>

        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 shadow-sm p-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-stone-900 dark:text-white">
            <Shield className="w-4 h-4" /> Admin mode
          </div>
          <p className="text-sm text-stone-600 dark:text-stone-300">
            Manage org tree, tokens, and security policies.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/admin/org-tree"
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-forest text-white hover:bg-forest-dark dark:bg-forest dark:text-white dark:hover:bg-forest-dark transition-colors"
            >
              <Network className="w-4 h-4" /> Org Tree
            </Link>
            <Link
              href="/settings"
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-forest text-white hover:bg-forest-dark dark:bg-forest dark:text-white dark:hover:bg-forest-dark transition-colors"
            >
              <Settings className="w-4 h-4" /> Settings
            </Link>
          </div>
        </div>

        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 shadow-sm p-5 space-y-3">
          <div className="text-sm font-semibold text-stone-900 dark:text-white">What should work</div>
          <ul className="text-sm text-stone-600 dark:text-stone-300 space-y-1">
            <li>- Team token: read/write via <code>/api/config/me/*</code></li>
            <li>- Admin token: org + tokens via <code>/api/v1/admin/*</code></li>
            <li>- No internet exposure: access via SSM tunnel only</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
