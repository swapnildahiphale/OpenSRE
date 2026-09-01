import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import crypto from 'crypto';
import { resolvePublicOrigin, resolveSsoOrgId, safeReturnTo, sanitizeOrgId } from '@/lib/ssoLoginOrg';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b));
}

/**
 * OAuth callback handler.
 * Exchanges the auth code for tokens, validates the user, and creates a session.
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const error = searchParams.get('error');
  const publicOrigin = resolvePublicOrigin(request);

  if (error) {
    return NextResponse.redirect(new URL(`/?error=${encodeURIComponent(error)}`, publicOrigin));
  }

  if (!code) {
    return NextResponse.redirect(new URL('/?error=no_code', publicOrigin));
  }

  // Validate OIDC state against cookie to prevent CSRF
  const cookieStore = await cookies();
  const savedState = cookieStore.get('ifx_oidc_state')?.value;

  if (savedState) {
    // OIDC flow: state must match the cookie set during /api/auth/login
    if (!state || !timingSafeEqual(state, savedState)) {
      return NextResponse.redirect(new URL('/?error=invalid_state', publicOrigin));
    }
  } else if (!state) {
    // No state cookie and no state param — reject
    return NextResponse.redirect(new URL('/?error=missing_state', publicOrigin));
  }

  // Parse state for SSO flow metadata (org_id, returnTo).
  // For OIDC flow (random state), this parse will fail and we use defaults.
  let stateData = { org_id: resolveSsoOrgId(), returnTo: '/team' };
  if (state && !savedState) {
    // Only parse state as JSON for the SSO flow (no OIDC cookie)
    try {
      stateData = JSON.parse(atob(state));
    } catch {
      // ignore parse failure — use env org fallback
    }
  }

  try {
    // Get org SSO config from config service
    // Sanitize org_id to prevent path traversal
    const orgId = sanitizeOrgId(stateData.org_id);
    if (!orgId) {
      return NextResponse.redirect(new URL('/?error=invalid_org', publicOrigin));
    }

    const ssoConfigRes = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/admin/orgs/${orgId}/sso-config/public`
    );

    if (!ssoConfigRes.ok) {
      return NextResponse.redirect(new URL('/?error=sso_not_configured', publicOrigin));
    }

    const ssoConfig = await ssoConfigRes.json();

    if (!ssoConfig.enabled) {
      return NextResponse.redirect(new URL('/?error=sso_disabled', publicOrigin));
    }

    const redirectUri = `${publicOrigin}/api/auth/callback`;

    // Include PKCE verifier if available (set by /api/auth/login)
    const codeVerifier = cookieStore.get('ifx_oidc_verifier')?.value;

    // Exchange code for token via config service
    const exchangeRes = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/auth/sso/exchange`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          org_id: orgId,
          code,
          redirect_uri: redirectUri,
          ...(codeVerifier ? { code_verifier: codeVerifier } : {}),
        }),
      }
    );

    if (!exchangeRes.ok) {
      const err = await exchangeRes.json().catch(() => ({}));
      console.error('Token exchange failed:', err);
      const detail = typeof err.detail === 'string' ? err.detail.slice(0, 180) : '';
      return NextResponse.redirect(new URL(`/?error=exchange_failed&detail=${encodeURIComponent(detail)}`, publicOrigin));
    }

    const exchangeData = await exchangeRes.json();

    // Chrome often drops Set-Cookie on a 302 that follows a cross-site Entra
    // redirect. Return 200 HTML that sets the cookie, then bounce to /team.
    const dest = safeReturnTo(stateData.returnTo);
    const secure = (process.env.WEB_UI_COOKIE_SECURE || '0').trim() === '1';
    const html = `<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0;url=${dest}"><title>Signing in</title></head><body>Signing in…<script>location.replace(${JSON.stringify(dest)});</script></body></html>`;
    const res = new NextResponse(html, {
      status: 200,
      headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' },
    });
    res.cookies.set({
      name: 'opensre_session_token',
      value: exchangeData.session_token,
      httpOnly: true,
      sameSite: 'lax',
      secure,
      path: '/',
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });

    // Clean up temporary OIDC cookies
    res.cookies.delete('ifx_oidc_state');
    res.cookies.delete('ifx_oidc_verifier');
    res.cookies.delete('ifx_oidc_require_role');

    return res;

  } catch (err) {
    console.error('SSO callback error:', err);
    return NextResponse.redirect(new URL('/?error=callback_error', publicOrigin));
  }
}
