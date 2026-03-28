import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ orgId: string; remediationId: string }> }
) {
  const { orgId, remediationId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();

    const res = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/remediations/${remediationId}/review`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'X-Org-Id': orgId,
        },
        body: JSON.stringify(body),
      }
    );

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Failed to review remediation' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Failed to review remediation:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

