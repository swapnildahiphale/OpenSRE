import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ orgId: string }> }
) {
  const { orgId } = await context.params;
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();

    const res = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/admin/orgs/${orgId}/nodes`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('Failed to create node:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ orgId: string }> }
) {
  const { orgId } = await context.params;
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const res = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/admin/orgs/${orgId}/nodes`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('Failed to fetch nodes:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
