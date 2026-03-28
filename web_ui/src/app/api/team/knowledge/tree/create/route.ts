import { NextRequest, NextResponse } from 'next/server';

const RAPTOR_API_URL = process.env.RAPTOR_API_URL || 'http://localhost:8000';

/**
 * POST /api/team/knowledge/tree/create
 * Creates a new knowledge tree
 */
export async function POST(request: NextRequest) {
  const token = request.cookies.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { tree_name, description } = body;

    if (!tree_name) {
      return NextResponse.json({ error: 'tree_name is required' }, { status: 400 });
    }

    // Validate tree name format
    if (!/^[a-zA-Z0-9_-]+$/.test(tree_name)) {
      return NextResponse.json({
        error: 'Tree name can only contain letters, numbers, hyphens, and underscores'
      }, { status: 400 });
    }

    const res = await fetch(`${RAPTOR_API_URL}/api/v1/trees`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ tree_name, description }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create tree' }));
      return NextResponse.json(
        { error: err.detail || err.error || 'Failed to create tree' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data, { status: 201 });
  } catch (e: any) {
    console.error('RAPTOR API error:', e);
    return NextResponse.json(
      { error: e?.message || 'Failed to create tree' },
      { status: 500 }
    );
  }
}
