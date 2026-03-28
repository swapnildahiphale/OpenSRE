import { NextRequest, NextResponse } from 'next/server';

const RAPTOR_API_URL = process.env.RAPTOR_API_URL || 'http://localhost:8000';

/**
 * GET /api/team/knowledge/tree/nodes/[nodeId]/children
 * Get children of a node for lazy loading in the visualization
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ nodeId: string }> }
) {
  const token = request.cookies.get('opensre_session_token')?.value;
  
  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const { nodeId } = await params;
  const { searchParams } = new URL(request.url);
  const tree = searchParams.get('tree') || 'mega_ultra_v2';

  try {
    const res = await fetch(
      `${RAPTOR_API_URL}/api/v1/tree/nodes/${encodeURIComponent(nodeId)}/children?tree=${encodeURIComponent(tree)}`,
      {
        headers: { 'Accept': 'application/json' },
        cache: 'no-store',
      }
    );
    
    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ error: err }, { status: res.status });
    }
    
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    console.error('RAPTOR API error:', e);
    return NextResponse.json({ error: e?.message || 'Failed to fetch children' }, { status: 500 });
  }
}

