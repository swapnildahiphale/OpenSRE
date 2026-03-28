'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useIdentity } from '@/lib/useIdentity';

export function RequireRole({
  role,
  children,
  fallbackHref = '/',
}: {
  role: 'admin' | 'team';
  children: React.ReactNode;
  fallbackHref?: string;
}) {
  const router = useRouter();
  const { identity, loading, error } = useIdentity();

  useEffect(() => {
    if (loading) return;
    if (!identity) return;
    if (identity.role !== role) router.replace(fallbackHref);
  }, [fallbackHref, identity, loading, role, router]);

  if (loading) {
    return (
      <div className="p-8">
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 shadow-sm p-6">
          <div className="text-sm font-semibold text-stone-900 dark:text-white">Checking access…</div>
          <div className="text-sm text-stone-600 dark:text-stone-300 mt-2">
            Verifying your token and permissions.
          </div>
        </div>
      </div>
    );
  }

  if (!identity) {
    return (
      <div className="p-8">
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 shadow-sm p-6 space-y-2">
          <div className="text-sm font-semibold text-stone-900 dark:text-white">Sign-in required</div>
          <div className="text-sm text-stone-600 dark:text-stone-300">
            Paste an admin/team token in <Link href="/settings" className="underline">Settings</Link> to access this page.
          </div>
          {error ? <div className="text-xs text-clay">Error: {error}</div> : null}
        </div>
      </div>
    );
  }

  if (identity.role !== role) {
    return (
      <div className="p-8">
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 shadow-sm p-6 space-y-2">
          <div className="text-sm font-semibold text-stone-900 dark:text-white">Not authorized</div>
          <div className="text-sm text-stone-600 dark:text-stone-300">
            This page requires <strong>{role}</strong> access. Your current role is <strong>{identity.role}</strong>.
          </div>
          <div className="text-sm">
            <Link href="/settings" className="underline">Switch token in Settings</Link>
            <span className="text-stone-500"> · </span>
            <Link href={fallbackHref} className="underline">Go back</Link>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}


