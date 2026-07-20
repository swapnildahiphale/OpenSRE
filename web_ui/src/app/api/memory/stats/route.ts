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
    const res = await fetch(`${AGENT_URL}/memory/stats`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await res.json();
    const result = data?.result ?? data;
    return NextResponse.json({
      total_episodes: result.total_episodes ?? 0,
      resolved: result.resolved ?? 0,
      issue_types: result.issue_types ?? [],
    });
  } catch {
    return NextResponse.json(
      { total_episodes: 0, resolved: 0, issue_types: [] },
      { status: 200 }
    );
  }
}
