'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useIdentity } from '@/lib/useIdentity';
import { applyTheme, getTheme } from '@/lib/theme';
import { Building2, Chrome, Lock, Shield } from 'lucide-react';
import { OnboardingWrapper } from './onboarding/OnboardingWrapper';
import { LoginHero } from './auth/LoginHero';
import { Button, Skeleton } from '@/components/ui-flow';

const PUBLIC_PATHS = ['/integrations/github/setup'];

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

  const isPublicPath = PUBLIC_PATHS.some((p) => pathname?.startsWith(p));

  useEffect(() => {
    applyTheme(getTheme());
  }, []);

  useEffect(() => {
    fetch('/api/sso/config?org_id=org1')
      .then((res) => res.json())
      .then((data) => {
        if (data.enabled) setSsoConfig(data);
        setLoadingSSO(false);
      })
      .catch(() => setLoadingSSO(false));
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
    } catch (e: unknown) {
      clearTimeout(timeoutId);
      const err = e as { name?: string; message?: string };
      if (err?.name === 'AbortError') {
        setSubmitError('Login request timed out. Please check your network connection and try again.');
      } else {
        setSubmitError(err?.message || String(e));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSSOLogin = () => {
    if (!ssoConfig) return;

    const redirectUri = `${window.location.origin}/api/auth/callback`;
    const state = btoa(JSON.stringify({ org_id: 'org1', returnTo: '/' }));
    const scopes = ssoConfig.scopes || 'openid email profile';
    let authUrl: string;

    if (ssoConfig.provider_type === 'google') {
      authUrl =
        `https://accounts.google.com/o/oauth2/v2/auth?` +
        `client_id=${ssoConfig.client_id}` +
        `&redirect_uri=${encodeURIComponent(redirectUri)}` +
        `&response_type=code` +
        `&scope=${encodeURIComponent(scopes)}` +
        `&state=${state}` +
        `&access_type=offline` +
        `&prompt=select_account`;
    } else if (ssoConfig.provider_type === 'azure') {
      const tenant = ssoConfig.tenant_id || 'common';
      authUrl =
        `https://login.microsoftonline.com/${tenant}/oauth2/v2.0/authorize?` +
        `client_id=${ssoConfig.client_id}` +
        `&redirect_uri=${encodeURIComponent(redirectUri)}` +
        `&response_type=code` +
        `&scope=${encodeURIComponent(scopes)}` +
        `&state=${state}` +
        `&response_mode=query`;
    } else {
      const issuer = ssoConfig.issuer?.replace(/\/$/, '');
      authUrl =
        `${issuer}/authorize?` +
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
        return <Chrome className="w-4 h-4 text-slate-600" />;
      case 'azure':
        return <Building2 className="w-4 h-4 text-slate-600" />;
      case 'okta':
        return <Lock className="w-4 h-4 text-slate-600" />;
      default:
        return <Shield className="w-4 h-4 text-slate-600" />;
    }
  };

  const hasSSO = ssoConfig?.enabled;

  if (isPublicPath) return <>{children}</>;
  if (canShowApp) return <OnboardingWrapper>{children}</OnboardingWrapper>;

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_0.9fr] bg-white text-slate-900">
      <LoginHero />

      <div className="flex items-center justify-center min-h-[50vh] lg:min-h-screen px-6 py-14 lg:px-12 xl:px-14 bg-[#f9fafb] border-l border-slate-200/60">
        <div className="w-full max-w-[440px]">
          <header className="mb-8">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400 mb-4">
              Team console
            </div>
            <h2 className="text-4xl md:text-[2.75rem] font-medium tracking-tight text-slate-900 leading-none">
              Sign in<span className="text-emerald-700">.</span>
            </h2>
            <p className="mt-4 text-sm text-slate-500 max-w-sm leading-relaxed">
              Use your org SSO, or paste an admin or team token.
            </p>
          </header>

          <div className="rounded-[2rem] border border-slate-200/70 bg-white p-7 md:p-8 shadow-[0_20px_40px_-15px_rgba(15,23,42,0.06)]">
            <div className="space-y-5">
              {loadingSSO ? (
                <div className="flex items-center justify-center py-4">
                  <Skeleton className="h-10 w-full rounded-full" />
                </div>
              ) : hasSSO && ssoConfig ? (
                <div className="space-y-2">
                  <label className="text-[11px] font-medium uppercase tracking-[0.18em] text-slate-400">
                    Single sign-on
                  </label>
                  <button
                    type="button"
                    onClick={handleSSOLogin}
                    className="w-full h-10 px-4 rounded-full text-[13.5px] font-medium bg-slate-100/60 text-slate-800 hover:bg-slate-100 flex items-center justify-center gap-2 transition active:translate-y-px"
                  >
                    {getProviderIcon(ssoConfig.provider_type)}
                    Continue with {ssoConfig.provider_name}
                  </button>
                </div>
              ) : null}

              <div className="space-y-2">
                <label
                  htmlFor="login-token"
                  className="text-[11px] font-medium uppercase tracking-[0.18em] text-slate-400"
                >
                  Token
                </label>
                <textarea
                  id="login-token"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  rows={3}
                  placeholder="tokid.toksecret or JWT"
                  className="w-full p-3.5 font-mono text-xs rounded-xl border border-slate-200/70 bg-slate-50/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-300 resize-none dark:bg-slate-900 dark:border-slate-600"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && token.trim() && !submitting) {
                      e.preventDefault();
                      login();
                    }
                  }}
                />
              </div>

              {helpText ? (
                <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200/80 rounded-xl p-3">
                  {helpText}
                </div>
              ) : null}
            </div>

            <div className="pt-6 mt-6 border-t border-slate-100">
              <Button
                type="button"
                variant="primary"
                className="w-full h-11 justify-center disabled:bg-slate-100 disabled:text-slate-400 disabled:opacity-100"
                onClick={login}
                disabled={submitting || !token.trim()}
              >
                {submitting ? 'Signing in…' : 'Continue'}
              </Button>
            </div>
          </div>

          <p className="text-center text-[11px] text-slate-400 mt-5">
            Tokens are stored in a secure session cookie.
          </p>
        </div>
      </div>
    </div>
  );
}
