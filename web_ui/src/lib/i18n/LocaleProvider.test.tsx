import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LanguageSelect } from '@/components/LanguageSelect';
import { formatRelativeTime } from '@/lib/formatRelativeTime';
import { LocaleProvider, useLocale } from './LocaleProvider';
import { LOCALE_STORAGE_KEY, resolveLocale, translate } from './locale';

function View() {
  const { t } = useLocale();
  return (
    <>
      <h1>{t('Settings')}</h1>
      <LanguageSelect id="language" />
    </>
  );
}

const renderView = () => render(<LocaleProvider><View /></LocaleProvider>);

afterEach(() => {
  localStorage.clear();
  document.documentElement.lang = 'en';
  vi.restoreAllMocks();
});

describe('the console language preference', () => {
  it('defaults unsupported values to English and retains literal interpolation values', () => {
    expect(resolveLocale('fr')).toBe('en');
    expect(translate('en', 'Continue with {provider}', { provider: 'Example & Co' }))
      .toBe('Continue with Example & Co');
    expect(translate('zh-CN', 'Continue with {provider}', { provider: 'Example & Co' }))
      .toBe('使用 Example & Co 登录');
  });

  it('switches the UI immediately, persists the choice, and switches back', () => {
    const first = renderView();
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeVisible();
    const language = screen.getByRole('combobox', { name: 'Language' });
    expect(screen.getByRole('option', { name: 'English' })).toHaveAttribute('lang', 'en');
    expect(screen.getByRole('option', { name: '简体中文' })).toHaveAttribute('lang', 'zh-CN');

    fireEvent.change(language, { target: { value: 'zh-CN' } });
    expect(screen.getByRole('heading', { name: '设置' })).toBeVisible();
    expect(document.documentElement.lang).toBe('zh-CN');
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('zh-CN');

    first.unmount();
    renderView();
    const restored = screen.getByRole('combobox', { name: '界面语言' });
    expect(restored).toHaveValue('zh-CN');
    fireEvent.change(restored, { target: { value: 'en' } });
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeVisible();
    expect(document.documentElement.lang).toBe('en');
  });

  it('applies language changes from another tab', () => {
    renderView();
    act(() => {
      localStorage.setItem(LOCALE_STORAGE_KEY, 'zh-CN');
      window.dispatchEvent(new StorageEvent('storage', {
        key: LOCALE_STORAGE_KEY,
        storageArea: localStorage,
        newValue: 'zh-CN',
      }));
    });
    expect(screen.getByRole('heading', { name: '设置' })).toBeVisible();
  });

  it('localizes relative time without changing the timestamp', () => {
    const now = Date.UTC(2026, 0, 1, 0, 10);
    vi.spyOn(Date, 'now').mockReturnValue(now);
    const fiveMinutesAgo = new Date(now - 5 * 60_000).toISOString();
    expect(formatRelativeTime(fiveMinutesAgo)).toBe('5m ago');
    expect(formatRelativeTime(fiveMinutesAgo, 'zh-CN')).toBe('5 分钟前');
  });
});
