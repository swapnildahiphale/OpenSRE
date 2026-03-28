import { NextRequest, NextResponse } from 'next/server';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://opensre-config-service:8080';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ orgId: string }> }
) {
  const { orgId } = await params;
  const token = request.cookies.get('opensre_session_token')?.value;
  
  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Forward query params
  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${CONFIG_SERVICE_URL}/api/v1/admin/orgs/${orgId}/unified-audit${searchParams ? '?' + searchParams : ''}`;

  try {
    const res = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('Audit API proxy error:', error);
    return NextResponse.json({ error: 'Failed to fetch audit events' }, { status: 502 });
  }
}

