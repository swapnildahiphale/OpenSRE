import zhCN from './zh-CN.json';

export const LOCALES = [
  { id: 'en', label: 'English' },
  { id: 'zh-CN', label: '简体中文' },
] as const;

export type Locale = (typeof LOCALES)[number]['id'];
export type Message = keyof typeof zhCN;
export const DEFAULT_LOCALE: Locale = 'en';
export const LOCALE_STORAGE_KEY = 'opensre.locale';

export function resolveLocale(value: unknown): Locale {
  return value === 'zh-CN' ? 'zh-CN' : DEFAULT_LOCALE;
}

export function translate(
  locale: Locale,
  message: Message,
  values: Record<string, string | number> = {},
): string {
  const template = locale === 'zh-CN' ? zhCN[message] ?? message : message;
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    Object.hasOwn(values, key) ? String(values[key]) : match,
  );
}
