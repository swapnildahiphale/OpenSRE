import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const AGENT_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ strategyId: string }> },
) {
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { strategyId } = await params;

  try {
    const body = await request.json();
    const res = await fetch(`${AGENT_URL}/memory/strategies/${encodeURIComponent(strategyId)}`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(
        { success: false, error: data?.detail ?? 'Failed to update strategy' },
        { status: res.status },
      );
    }

    const result = data?.result ?? data;
    return NextResponse.json({ success: true, ...result });
  } catch {
    return NextResponse.json(
      { success: false, error: 'Failed to update strategy' },
      { status: 500 },
    );
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ strategyId: string }> },
) {
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { strategyId } = await params;

  try {
    const res = await fetch(`${AGENT_URL}/memory/strategies/${encodeURIComponent(strategyId)}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(
        { success: false, error: data?.detail ?? 'Failed to delete strategy' },
        { status: res.status },
      );
    }

    const result = data?.result ?? data;
    return NextResponse.json({ success: true, ...result });
  } catch {
    return NextResponse.json(
      { success: false, error: 'Failed to delete strategy' },
      { status: 500 },
    );
  }
}
