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

  try {
    const res = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/admin/orgs/${orgId}/sso-config/public`,
      { cache: 'no-store' }
    );

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }

    return NextResponse.json({ enabled: false, org_id: orgId });
  } catch (e) {
    // If config service is down, just disable SSO
    return NextResponse.json({ enabled: false, org_id: orgId });
  }
}
