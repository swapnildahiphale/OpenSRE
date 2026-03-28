import { NextRequest, NextResponse } from 'next/server';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const token = request.cookies.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const { id } = await params;
    const body = await request.json();

    const res = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/team/templates/${id}/apply`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'Failed to apply template' }, { status: 500 });
  }
}
