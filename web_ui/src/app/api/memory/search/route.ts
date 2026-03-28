import { NextRequest, NextResponse } from 'next/server';

const AGENT_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const res = await fetch(`${AGENT_URL}/memory/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ results: [] }, { status: 200 });
  }
}
