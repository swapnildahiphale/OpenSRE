import { NextResponse } from 'next/server';

const AGENT_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const res = await fetch(`${AGENT_URL}/memory/stats`);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json(
      { total_episodes: 0, resolved_episodes: 0, unresolved_episodes: 0, strategies_count: 0 },
      { status: 200 }
    );
  }
}
