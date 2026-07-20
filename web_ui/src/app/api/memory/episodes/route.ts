import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const AGENT_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const res = await fetch(`${AGENT_URL}/memory/episodes`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await res.json();
    const result = data?.result ?? data;
    return NextResponse.json({ episodes: result.episodes ?? [] });
  } catch {
    return NextResponse.json({ episodes: [] }, { status: 200 });
  }
}
