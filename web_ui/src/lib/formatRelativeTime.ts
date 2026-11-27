import { DEFAULT_LOCALE, translate, type Locale } from './i18n/locale';

export function formatRelativeTime(timestamp: string, locale: Locale = DEFAULT_LOCALE): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (minutes < 1) return translate(locale, 'just now');
  if (minutes < 60) return translate(locale, '{count}m ago', { count: minutes });
  if (hours < 24) return translate(locale, '{count}h ago', { count: hours });
  return translate(locale, '{count}d ago', { count: days });
}
