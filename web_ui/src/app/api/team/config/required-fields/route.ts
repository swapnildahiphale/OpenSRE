import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function GET(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get('team_token')?.value;
  const orgId = cookieStore.get('team_org_id')?.value;
  const teamNodeId = cookieStore.get('team_node_id')?.value;

  if (!token || !orgId || !teamNodeId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const res = await fetch(`${CONFIG_SERVICE_URL}/api/v1/config/me/required-fields`, {
      headers: {
        'X-Org-Id': orgId,
        'X-Team-Node-Id': teamNodeId,
        Authorization: `Bearer ${token}`,
      },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('Failed to fetch required fields:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

