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
  const url = `${CONFIG_SERVICE_URL}/api/v1/admin/orgs/${orgId}/unified-audit/export${searchParams ? '?' + searchParams : ''}`;

  try {
    const res = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!res.ok) {
      return NextResponse.json({ error: 'Failed to export' }, { status: res.status });
    }

    const csvContent = await res.text();
    
    return new NextResponse(csvContent, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': `attachment; filename="audit_export_${orgId}_${new Date().toISOString().split('T')[0]}.csv"`,
      },
    });
  } catch (error) {
    console.error('Audit export proxy error:', error);
    return NextResponse.json({ error: 'Failed to export audit log' }, { status: 502 });
  }
}

