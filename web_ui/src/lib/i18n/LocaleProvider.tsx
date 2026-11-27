'use client';

import { createContext, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from 'react';
import { DEFAULT_LOCALE, LOCALE_STORAGE_KEY, resolveLocale, translate, type Locale } from './locale';

const localeEvent = 'opensre:locale-change';
let volatileLocale: Locale = DEFAULT_LOCALE;

function getLocale(): Locale {
  try {
    return resolveLocale(window.localStorage.getItem(LOCALE_STORAGE_KEY));
  } catch {
    return volatileLocale;
  }
}

function getDefaultLocale(): Locale {
  return DEFAULT_LOCALE;
}

function subscribe(update: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.storageArea === window.localStorage && (event.key === LOCALE_STORAGE_KEY || event.key === null)) {
      update();
    }
  };
  window.addEventListener('storage', onStorage);
  window.addEventListener(localeEvent, update);
  return () => {
    window.removeEventListener('storage', onStorage);
    window.removeEventListener(localeEvent, update);
  };
}

function setLocale(locale: Locale) {
  volatileLocale = locale;
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // Switching still works for this tab when browser storage is unavailable.
  }
  window.dispatchEvent(new Event(localeEvent));
}

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (message: Parameters<typeof translate>[1], values?: Parameters<typeof translate>[2]) => string;
};

const LocaleContext = createContext<LocaleContextValue>({
  locale: DEFAULT_LOCALE,
  setLocale: () => {},
  t: translate.bind(null, DEFAULT_LOCALE),
});

export function LocaleProvider({ children }: { children: ReactNode }) {
  // Start with English for SSR and hydration, then read the browser preference.
  const locale = useSyncExternalStore(subscribe, getLocale, getDefaultLocale);
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  const value = useMemo(() => ({ locale, setLocale, t: translate.bind(null, locale) }), [locale]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  return useContext(LocaleContext);
}
