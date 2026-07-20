import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const AGENT_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const res = await fetch(`${AGENT_URL}/memory/search`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: body.query ?? body.prompt,
        limit: body.limit ?? 5,
      }),
    });
    const data = await res.json();
    const result = data?.result ?? data;
    return NextResponse.json({ results: result.episodes ?? [] });
  } catch {
    return NextResponse.json({ results: [] }, { status: 200 });
  }
}
