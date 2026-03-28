import { NextRequest, NextResponse } from 'next/server';

const AGENT_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const alert_type = searchParams.get('alert_type') || '';
  const service_name = searchParams.get('service_name') || '';

  try {
    const params = new URLSearchParams();
    if (alert_type) params.set('alert_type', alert_type);
    if (service_name) params.set('service_name', service_name);
    const res = await fetch(`${AGENT_URL}/memory/strategies?${params}`);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ strategies: [] }, { status: 200 });
  }
}
