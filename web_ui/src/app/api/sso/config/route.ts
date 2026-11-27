import { NextRequest, NextResponse } from 'next/server';
import { resolveSsoOrgId, sanitizeOrgId } from '@/lib/ssoLoginOrg';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

// Public endpoint - no auth required
// Returns SSO config for login page
export async function GET(request: NextRequest) {
  const orgId =
    sanitizeOrgId(request.nextUrl.searchParams.get('org_id')) || resolveSsoOrgId();

  if (!orgId) {
    return NextResponse.json({ enabled: false });
  }

  const discoveryQuery = request.nextUrl.searchParams.get('discover') === '1' ? '?discover=true' : '';
  try {
    const res = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/admin/orgs/${orgId}/sso-config/public${discoveryQuery}`,
      { cache: 'no-store' }
    );

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Report discovery failure on a login attempt, but keep token login available.
  }

  if (discoveryQuery) {
    return NextResponse.json({ error: 'Unable to discover OIDC configuration' }, { status: 502 });
  }
  return NextResponse.json({ enabled: false, org_id: orgId });
}
