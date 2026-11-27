'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useIdentity } from '@/lib/useIdentity';
import { useLocale } from '@/lib/i18n/LocaleProvider';

export function RequireRole({
  role,
  children,
  fallbackHref = '/',
}: {
  role: 'admin' | 'team';
  children: React.ReactNode;
  fallbackHref?: string;
}) {
  const { t } = useLocale();
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
          <div className="text-sm font-semibold text-stone-900 dark:text-white">{t("Checking access…")}</div>
          <div className="text-sm text-stone-600 dark:text-stone-300 mt-2">
            {t("Verifying your token and permissions.")}
          </div>
        </div>
      </div>
    );
  }

  if (!identity) {
    return (
      <div className="p-8">
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 shadow-sm p-6 space-y-2">
          <div className="text-sm font-semibold text-stone-900 dark:text-white">{t("Sign-in required")}</div>
          <div className="text-sm text-stone-600 dark:text-stone-300">
            <Link href="/settings" className="underline">{t("Open Settings to paste an admin or team token and access this page.")}</Link>
          </div>
          {error ? <div className="text-xs text-clay">{t("Error:")}{' '}{error}</div> : null}
        </div>
      </div>
    );
  }

  if (identity.role !== role) {
    return (
      <div className="p-8">
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 shadow-sm p-6 space-y-2">
          <div className="text-sm font-semibold text-stone-900 dark:text-white">{t("Not authorized")}</div>
          <div className="text-sm text-stone-600 dark:text-stone-300">
            {t('This page requires {required} access. Your current role is {current}.', {
              required: t(role === 'admin' ? 'Admin' : 'Team'),
              current: t(identity.role === 'admin' ? 'Admin' : 'Team'),
            })}
          </div>
          <div className="text-sm">
            <Link href="/settings" className="underline">{t("Switch token in Settings")}</Link>
            <span className="text-stone-500"> · </span>
            <Link href={fallbackHref} className="underline">{t("Go back")}</Link>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}


