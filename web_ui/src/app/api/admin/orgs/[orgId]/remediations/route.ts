import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ orgId: string }> }
) {
  const { orgId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const status = searchParams.get('status');
  const urgency = searchParams.get('urgency');

  let url = `${CONFIG_SERVICE_URL}/api/v1/remediations?org_id=${orgId}`;
  if (status) url += `&status=${status}`;
  if (urgency) url += `&urgency=${urgency}`;

  try {
    const res = await fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Org-Id': orgId,
      },
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch remediations' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Failed to fetch remediations:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ orgId: string }> }
) {
  const { orgId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();

    const res = await fetch(`${CONFIG_SERVICE_URL}/api/v1/remediations`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'X-Org-Id': orgId,
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Failed to create remediation' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data, { status: 201 });
  } catch (error) {
    console.error('Failed to create remediation:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

