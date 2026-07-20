import { NextRequest } from 'next/server';

export const runtime = 'nodejs';

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || process.env.ORCHESTRATOR_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  const token = request.cookies.get('opensre_session_token')?.value;

  if (!token) {
    return new Response(JSON.stringify({ error: 'Not authenticated' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  try {
    const body = await request.json();
    const { thread_id, text } = body;

    if (!thread_id) {
      return new Response(JSON.stringify({ error: 'Missing thread_id' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (!text || typeof text !== 'string' || !text.trim()) {
      return new Response(JSON.stringify({ error: 'Missing text' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const upstreamRes = await fetch(
      `${AGENT_SERVICE_URL}/threads/${encodeURIComponent(thread_id)}/queue-message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-OpenSRE-Team-Token': token,
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ text }),
      },
    );

    if (!upstreamRes.ok) {
      const errorText = await upstreamRes.text();
      return new Response(JSON.stringify({ error: errorText || `Upstream error: ${upstreamRes.status}` }), {
        status: upstreamRes.status,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const data = await upstreamRes.json();
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : 'Failed to queue message';
    return new Response(JSON.stringify({ error: errorMessage }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
