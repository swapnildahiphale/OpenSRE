import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const AGENT_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ episodeId: string }> },
) {
  const token = (await cookies()).get('opensre_session_token')?.value;
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  const { episodeId } = await params;
  const res = await fetch(
    `${AGENT_URL}/memory/episodes/${encodeURIComponent(episodeId)}/reextract`,
    { method: 'POST', headers: { Authorization: `Bearer ${token}` } },
  );
  const data = await res.json();
  if (!res.ok) {
    return NextResponse.json(
      { success: false, error: data?.detail ?? 'Retry failed' },
      { status: res.status },
    );
  }
  return NextResponse.json({ success: true, episode: data?.result ?? data });
}
