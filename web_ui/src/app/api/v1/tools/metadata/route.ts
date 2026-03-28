import { NextRequest, NextResponse } from 'next/server';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function GET(request: NextRequest) {
  try {
    // Proxy request to config service
    const url = new URL(request.url);
    const searchParams = url.searchParams;

    const queryString = searchParams.toString();
    const backendUrl = `${CONFIG_SERVICE_URL}/api/v1/tools/metadata${queryString ? `?${queryString}` : ''}`;

    const res = await fetch(backendUrl);

    if (!res.ok) {
      const text = await res.text();
      console.error('Config service error:', res.status, text);
      return NextResponse.json({ error: text }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('Failed to fetch tool metadata:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
