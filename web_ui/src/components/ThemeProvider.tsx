'use client';

import { useEffect } from 'react';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const applyTheme = (theme: string) => {
      const root = document.documentElement;
      if (theme === 'dark') {
        root.classList.add('dark');
        root.style.colorScheme = 'dark';
      } else {
        root.classList.remove('dark');
        root.style.colorScheme = 'light';
      }
    };

    // Apply theme immediately
    const theme = localStorage.getItem('theme') || 'light';
    applyTheme(theme);

    // Watch for changes to localStorage (from other tabs/windows)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'theme' && e.newValue) {
        applyTheme(e.newValue);
      }
    };

    window.addEventListener('storage', handleStorageChange);

    // Watch for hydration removing the class and force it back
    // Only needed during initial hydration, then disconnect
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          // Re-read from localStorage each time to get latest value
          const currentTheme = localStorage.getItem('theme') || 'light';
          const hasDark = document.documentElement.classList.contains('dark');
          const shouldHaveDark = currentTheme === 'dark';

          if (hasDark !== shouldHaveDark) {
            applyTheme(currentTheme);
          }
        }
      });
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    });

    // Disconnect after 500ms - hydration should be done by then
    const timeoutId = setTimeout(() => {
      observer.disconnect();
    }, 500);

    return () => {
      clearTimeout(timeoutId);
      observer.disconnect();
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  return <>{children}</>;
}
