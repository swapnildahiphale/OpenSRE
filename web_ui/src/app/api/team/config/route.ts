import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function GET(request: NextRequest) {
  const cookieStore = await cookies();
  // The session token is set by SignInGate login flow
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // Use v2 API - token contains identity, no extra headers needed
    const res = await fetch(`${CONFIG_SERVICE_URL}/api/v1/config/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!res.ok) {
      const text = await res.text();
      console.error('Config service error:', res.status, text);
      return NextResponse.json({ error: text }, { status: res.status });
    }

    const data = await res.json();

    // v2 API returns {effective_config: {...}, ...}, extract the config
    const config = data.effective_config || data;

    // Return effective config
    return NextResponse.json(config, { status: res.status });
  } catch (error) {
    console.error('Failed to fetch team config:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function PATCH(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();

    // Use v2 API - wrap body in {config: ...} format
    const payload = {
      config: body,
    };

    const res = await fetch(`${CONFIG_SERVICE_URL}/api/v1/config/me`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const text = await res.text();
      console.error('Config service error:', res.status, text);
      return NextResponse.json({ error: text }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('Failed to update team config:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

