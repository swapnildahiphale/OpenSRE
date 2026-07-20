import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const AGENT_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

const EMPTY_OVERVIEW = {
  total_episodes: 0,
  resolved: 0,
  unresolved: 0,
  resolution_rate: 0,
  episodes_this_week: 0,
  issue_type_counts: [],
  recent_episodes: [],
  strategy_count: 0,
  latest_strategies: [],
};

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const res = await fetch(`${AGENT_URL}/memory/overview`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await res.json();
    const result = data?.result ?? data;
    return NextResponse.json({
      total_episodes: result.total_episodes ?? 0,
      resolved: result.resolved ?? 0,
      unresolved: result.unresolved ?? 0,
      resolution_rate: result.resolution_rate ?? 0,
      episodes_this_week: result.episodes_this_week ?? 0,
      issue_type_counts: result.issue_type_counts ?? [],
      recent_episodes: result.recent_episodes ?? [],
      strategy_count: result.strategy_count ?? 0,
      latest_strategies: result.latest_strategies ?? [],
    });
  } catch {
    return NextResponse.json(EMPTY_OVERVIEW, { status: 200 });
  }
}
