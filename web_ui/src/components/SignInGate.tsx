'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useIdentity } from '@/lib/useIdentity';
import { applyTheme, getTheme, setTheme, type ThemeMode } from '@/lib/theme';
import { X, KeyRound, Shield, Chrome, Building2, Loader2, Lock } from 'lucide-react';
import { OnboardingWrapper } from './onboarding/OnboardingWrapper';

// Paths that bypass authentication (public pages)
const PUBLIC_PATHS = [
  '/integrations/github/setup',
];

interface OrgSSOConfig {
  enabled: boolean;
  provider_type: string;
  provider_name: string;
  issuer?: string;
  client_id?: string;
  tenant_id?: string;
  scopes?: string;
}

export function SignInGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { identity, loading, error, refresh } = useIdentity();
  const [token, setToken] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [ssoConfig, setSsoConfig] = useState<OrgSSOConfig | null>(null);
  const [loadingSSO, setLoadingSSO] = useState(true);
  const [theme, setThemeState] = useState<ThemeMode>('light');

  const isPublicPath = PUBLIC_PATHS.some(p => pathname?.startsWith(p));

  useEffect(() => {
    const t = getTheme();
    setThemeState(t);
    applyTheme(t);
  }, []);

  // Load org SSO config
  useEffect(() => {
    fetch('/api/sso/config?org_id=org1')
      .then((res) => res.json())
      .then((data) => {
        if (data.enabled) {
          setSsoConfig(data);
        }
        setLoadingSSO(false);
      })
      .catch(() => {
        setLoadingSSO(false);
      });
  }, []);

  const canShowApp = !loading && !!identity;

  const helpText = useMemo(() => {
    if (submitError) return submitError;
    if (error) return error;
    return null;
  }, [error, submitError]);

  const login = async () => {
    setSubmitting(true);
    setSubmitError(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    try {
      const res = await fetch('/api/session/login', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ token: token.trim() }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
      await refresh();
    } catch (e: any) {
      clearTimeout(timeoutId);
      if (e?.name === 'AbortError') {
        setSubmitError('Login request timed out. Please check your network connection and try again.');
      } else {
        setSubmitError(e?.message || String(e));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSSOLogin = () => {
    if (!ssoConfig) return;

    // Build the OIDC authorization URL
    let authUrl: string;
    const redirectUri = `${window.location.origin}/api/auth/callback`;
    const state = btoa(JSON.stringify({ org_id: 'org1', returnTo: '/' }));
    const scopes = ssoConfig.scopes || 'openid email profile';

    if (ssoConfig.provider_type === 'google') {
      authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
        `client_id=${ssoConfig.client_id}` +
        `&redirect_uri=${encodeURIComponent(redirectUri)}` +
        `&response_type=code` +
        `&scope=${encodeURIComponent(scopes)}` +
        `&state=${state}` +
        `&access_type=offline` +
        `&prompt=select_account`;
    } else if (ssoConfig.provider_type === 'azure') {
      const tenant = ssoConfig.tenant_id || 'common';
      authUrl = `https://login.microsoftonline.com/${tenant}/oauth2/v2.0/authorize?` +
        `client_id=${ssoConfig.client_id}` +
        `&redirect_uri=${encodeURIComponent(redirectUri)}` +
        `&response_type=code` +
        `&scope=${encodeURIComponent(scopes)}` +
        `&state=${state}` +
        `&response_mode=query`;
    } else {
      // Generic OIDC
      const issuer = ssoConfig.issuer?.replace(/\/$/, '');
      authUrl = `${issuer}/authorize?` +
        `client_id=${ssoConfig.client_id}` +
        `&redirect_uri=${encodeURIComponent(redirectUri)}` +
        `&response_type=code` +
        `&scope=${encodeURIComponent(scopes)}` +
        `&state=${state}`;
    }

    window.location.href = authUrl;
  };

  const getProviderIcon = (providerType: string) => {
    switch (providerType) {
      case 'google':
        return <Chrome className="w-4 h-4" />;
      case 'azure':
        return <Building2 className="w-4 h-4" />;
      case 'okta':
        return <Lock className="w-4 h-4" />;
      default:
        return <Shield className="w-4 h-4" />;
    }
  };

  const hasSSO = ssoConfig?.enabled;

  if (isPublicPath) return <>{children}</>;
  if (canShowApp) return <OnboardingWrapper>{children}</OnboardingWrapper>;

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50 dark:bg-stone-900 p-6">
      <div className="w-full max-w-lg bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-2xl shadow-xl overflow-hidden">
        <div className="p-6 border-b border-stone-200 dark:border-stone-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-forest text-white flex items-center justify-center">
              <KeyRound className="w-5 h-5" />
            </div>
            <div>
              <div className="text-base font-semibold text-stone-900 dark:text-white">Sign in to OpenSRE</div>
              <div className="text-xs text-stone-500">
                {hasSSO
                  ? 'Use SSO or paste a token to continue.'
                  : 'Paste an admin token or team token to continue.'}
              </div>
            </div>
          </div>

          <button
            className="p-2 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-700"
            onClick={() => {
              setToken('');
              setSubmitError(null);
            }}
            title="Clear"
          >
            <X className="w-4 h-4 text-stone-400" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* SSO Button */}
          {loadingSSO ? (
            <div className="flex items-center justify-center py-2">
              <Loader2 className="w-5 h-5 animate-spin text-stone-400" />
            </div>
          ) : hasSSO && ssoConfig ? (
            <div className="space-y-2">
              <div className="text-xs font-medium text-stone-500 uppercase tracking-wide">Single Sign-On</div>
              <button
                onClick={handleSSOLogin}
                className="w-full px-4 py-2.5 text-sm font-semibold bg-stone-100 dark:bg-stone-700 text-stone-900 dark:text-white rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700 flex items-center justify-center gap-2 transition-colors"
              >
                {getProviderIcon(ssoConfig.provider_type)}
                Continue with {ssoConfig.provider_name}
              </button>
              <div className="flex items-center gap-3 py-2">
                <div className="flex-1 border-t border-stone-200 dark:border-stone-600" />
                <span className="text-xs text-stone-400">or</span>
                <div className="flex-1 border-t border-stone-200 dark:border-stone-600" />
              </div>
            </div>
          ) : null}

          {/* Token Login */}
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">Token</label>
            <textarea
              value={token}
              onChange={(e) => setToken(e.target.value)}
              rows={3}
              placeholder="tokid.toksecret or JWT"
              className="w-full p-3 font-mono text-xs rounded-lg border border-stone-200 dark:border-stone-600 bg-stone-50 dark:bg-stone-900 focus:outline-none focus:ring-2 focus:ring-forest"
            />
          </div>

          {helpText ? (
            <div className="text-sm text-clay bg-clay-light/10 dark:bg-clay/20 border border-clay-light/30 dark:border-clay/30 rounded-lg p-3">
              {helpText}
            </div>
          ) : null}

          <div className="flex items-center justify-between gap-3 pt-2">
            <button
              onClick={() => {
                const next: ThemeMode = theme === 'dark' ? 'light' : 'dark';
                setThemeState(next);
                setTheme(next);
              }}
              className="px-3 py-2 text-sm font-medium bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700"
            >
              Theme: {theme === 'dark' ? 'Dark' : 'Light'}
            </button>

            <button
              onClick={login}
              disabled={submitting || !token.trim()}
              className="px-4 py-2 text-sm font-semibold bg-forest text-white rounded-lg hover:bg-forest-dark disabled:opacity-70"
            >
              {submitting ? 'Signing in...' : 'Continue'}
            </button>
          </div>
        </div>

        <div className="p-4 bg-stone-50 dark:bg-stone-900/30 border-t border-stone-200 dark:border-stone-700 text-xs text-stone-500">
          Enterprise default: tokens are stored in a secure session cookie (not localStorage).
        </div>
      </div>
    </div>
  );
}
