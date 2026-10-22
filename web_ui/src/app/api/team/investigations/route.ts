import { NextRequest, NextResponse } from 'next/server';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function GET(request: NextRequest) {
  const token = request.cookies.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const page = request.nextUrl.searchParams.get('page') || '1';
    const pageSize = request.nextUrl.searchParams.get('page_size') || '20';
    const qs = new URLSearchParams({ page, page_size: pageSize });
    const res = await fetch(
      `${CONFIG_SERVICE_URL}/api/v1/team/investigations?${qs.toString()}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    );

    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      return NextResponse.json(
        { error: text || `Request failed with status ${res.status}` },
        { status: res.status >= 400 ? res.status : 500 },
      );
    }
    return NextResponse.json(data, { status: res.status });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Failed to fetch';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
