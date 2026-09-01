/**
 * Login org for the SignInGate SSO button.
 * Server-only: WEB_UI_SSO_ORG_ID (Helm global.configService.orgId / compose local).
 */

export function sanitizeOrgId(raw: string | undefined | null): string {
  return (raw || '').replace(/[^a-zA-Z0-9_-]/g, '');
}

/** Post-login path. Rejects protocol-relative URLs and anything that is not a simple path. */
export function safeReturnTo(returnTo: string | undefined | null): string {
  if (!returnTo || !/^\/[a-zA-Z0-9/_-]*$/.test(returnTo)) return '/team';
  return returnTo;
}

export function resolveSsoOrgId(
  env: Record<string, string | undefined> = process.env,
): string {
  return sanitizeOrgId(env.WEB_UI_SSO_ORG_ID);
}

type OriginRequest = {
  headers: { get(name: string): string | null };
  nextUrl: { protocol: string; origin: string };
};

/**
 * Browser-facing origin for Entra redirect_uri and post-login redirects.
 *
 * Next.js in Docker/K8s sets HOSTNAME=0.0.0.0 so request.nextUrl.origin is
 * not the URL the user typed. Prefer WEB_UI_PUBLIC_BASE_URL, then forwarded
 * Host, and never send 0.0.0.0 to Entra.
 */
export function resolvePublicOrigin(
  request: OriginRequest,
  env: Record<string, string | undefined> = process.env,
): string {
  const fromEnv = (env.WEB_UI_PUBLIC_BASE_URL || '').trim().replace(/\/$/, '');
  if (fromEnv) return fromEnv;

  const proto =
    request.headers.get('x-forwarded-proto') ||
    request.nextUrl.protocol.replace(/:$/, '') ||
    'http';
  const host =
    request.headers.get('x-forwarded-host') || request.headers.get('host');
  if (host && !host.startsWith('0.0.0.0') && !host.startsWith('[::]')) {
    return `${proto}://${host}`;
  }

  return request.nextUrl.origin.replace('://0.0.0.0', '://localhost');
}
