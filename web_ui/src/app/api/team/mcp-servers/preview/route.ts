import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * POST /api/team/mcp-servers/preview
 *
 * Preview an MCP server before adding it - discover available tools
 */
export async function POST(req: NextRequest) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get('opensre_session_token')?.value;

    if (!token) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await req.json();

    const configServiceUrl = process.env.CONFIG_SERVICE_URL || 'http://opensre-config-service.opensre.svc.cluster.local:8080';
    const response = await fetch(`${configServiceUrl}/api/v1/team/mcp-servers/preview`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        data,
        { status: response.status }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Error previewing MCP server:', error);
    return NextResponse.json(
      { error: 'Failed to preview MCP server', success: false },
      { status: 500 }
    );
  }
}
