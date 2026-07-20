import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || process.env.ORCHESTRATOR_URL || 'http://localhost:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ threadId: string }> },
) {
  const { threadId } = await params;
  const token = request.cookies.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const upstreamRes = await fetch(`${AGENT_SERVICE_URL}/threads/${threadId}/active`, {
      headers: {
        'X-OpenSRE-Team-Token': token,
        'Authorization': `Bearer ${token}`,
      },
      cache: 'no-store',
    });

    const text = await upstreamRes.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      return NextResponse.json(
        { error: text || `Upstream error: ${upstreamRes.status}` },
        { status: upstreamRes.status >= 400 ? upstreamRes.status : 500 },
      );
    }
    return NextResponse.json(data, { status: upstreamRes.status });
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : 'Failed to check thread session';
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}
