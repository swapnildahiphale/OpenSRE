import { NextRequest, NextResponse } from 'next/server';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function GET(request: NextRequest) {
  const token = request.cookies.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const res = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/team/template`,
      {
        headers: { 'Authorization': `Bearer ${token}` },
      }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'Failed to fetch current template' }, { status: 500 });
  }
}

export async function DELETE(request: NextRequest) {
  const token = request.cookies.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const res = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/team/template`,
      {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'Failed to deactivate template' }, { status: 500 });
  }
}
