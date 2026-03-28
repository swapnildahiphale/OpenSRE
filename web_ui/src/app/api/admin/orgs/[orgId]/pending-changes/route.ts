import { NextRequest, NextResponse } from 'next/server';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ orgId: string }> }
) {
  const { orgId } = await params;
  const token = request.cookies.get('opensre_session_token')?.value;
  
  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const searchParams = request.nextUrl.searchParams.toString();
    const url = `${CONFIG_SERVICE_URL}/api/v1/admin/orgs/${orgId}/pending-changes${searchParams ? `?${searchParams}` : ''}`;
    
    const res = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'Failed to fetch' }, { status: 500 });
  }
}

