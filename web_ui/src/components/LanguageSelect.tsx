'use client';

import { useLocale } from '@/lib/i18n/LocaleProvider';
import { LOCALES, resolveLocale } from '@/lib/i18n/locale';

export function LanguageSelect({ id }: { id: string }) {
  const { locale, setLocale, t } = useLocale();

  return (
    <select
      id={id}
      aria-label={t('Language')}
      value={locale}
      onChange={(event) => setLocale(resolveLocale(event.target.value))}
      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
    >
      {LOCALES.map(({ id: value, label }) => (
        <option key={value} value={value} lang={value}>{label}</option>
      ))}
    </select>
  );
}
