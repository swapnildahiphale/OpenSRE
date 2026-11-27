import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsPage from '@/app/settings/page';
import { LocaleProvider } from '@/lib/i18n/LocaleProvider';
import { LOCALE_STORAGE_KEY } from '@/lib/i18n/locale';
import { SignInGate } from './SignInGate';

const { useIdentity, apiFetch, router, searchParams } = vi.hoisted(() => ({
  useIdentity: vi.fn(),
  apiFetch: vi.fn(),
  router: { push: vi.fn() },
  searchParams: new URLSearchParams(),
}));
vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => router,
  useSearchParams: () => searchParams,
}));
vi.mock('@/lib/useIdentity', () => ({ useIdentity }));
vi.mock('@/lib/apiClient', () => ({ apiFetch }));
vi.mock('@/lib/useOnboarding', () => ({ useOnboarding: () => ({ resetOnboarding: vi.fn() }) }));
vi.mock('./auth/LoginHero', () => ({ LoginHero: () => null }));
vi.mock('@/components/onboarding/ContinueOnboardingButton', () => ({ ContinueOnboardingButton: () => null }));

beforeEach(() => {
  localStorage.clear();
  apiFetch.mockImplementation(async (path: string) => ({
    ok: true,
    json: async () => path === '/api/config/me/org-settings' ? { telemetry_enabled: true } : {},
  }));
});

afterEach(() => {
  localStorage.clear();
  document.documentElement.lang = 'en';
  vi.unstubAllGlobals();
});

describe('language controls on real console pages', () => {
  it('translates the signed-out form and preserves the provider name and token input', async () => {
    useIdentity.mockReturnValue({ identity: null, loading: false, error: null });
    vi.stubGlobal('fetch', vi.fn(async () => ({
      json: async () => ({ enabled: true, org_id: 'local', provider_name: 'Example Identity' }),
    })));
    render(<LocaleProvider><SignInGate><p>Signed in content</p></SignInGate></LocaleProvider>);

    expect(await screen.findByRole('button', { name: 'Continue with Example Identity' })).toBeVisible();
    fireEvent.change(screen.getByRole('textbox', { name: 'Token' }), { target: { value: 'test-value' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Language' }), { target: { value: 'zh-CN' } });

    expect(screen.getByRole('button', { name: '使用 Example Identity 登录' })).toBeVisible();
    expect(screen.getByRole('textbox', { name: '令牌' })).toHaveValue('test-value');
    expect(screen.queryByText('Signed in content')).not.toBeInTheDocument();
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('zh-CN');
  });

  it('switches settings without changing the selected tab or calling a preference API', async () => {
    useIdentity.mockReturnValue({ identity: { role: 'admin', org_id: 'local' }, loading: false });
    render(<LocaleProvider><SettingsPage /></LocaleProvider>);
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/config/me'));

    const requestsBefore = apiFetch.mock.calls.length;
    fireEvent.change(screen.getByRole('combobox', { name: 'Language' }), { target: { value: 'zh-CN' } });

    expect(screen.getByRole('combobox', { name: '界面语言' })).toHaveValue('zh-CN');
    expect(screen.getByRole('button', { name: '常规' })).toBeVisible();
    expect(screen.getByRole('button', { name: '安全策略' })).toBeVisible();
    expect(apiFetch).toHaveBeenCalledTimes(requestsBefore);
  });
});
