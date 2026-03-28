import { NextRequest, NextResponse } from 'next/server';

const CONFIG_SERVICE_URL = process.env.CONFIG_SERVICE_URL || 'http://localhost:8080';

export async function POST(request: NextRequest) {
  const token = request.cookies.get('opensre_session_token')?.value;
  
  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const formData = await request.formData();
    
    const res = await fetch(`${CONFIG_SERVICE_URL}/api/v1/team/knowledge/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    });
    
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'Upload failed' }, { status: 500 });
  }
}
