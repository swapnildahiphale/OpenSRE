import { NextRequest, NextResponse } from 'next/server';

const RAPTOR_API_URL = process.env.RAPTOR_API_URL || 'http://localhost:8000';

/**
 * POST /api/team/knowledge/tree/documents
 * Add documents to a knowledge tree
 */
export async function POST(request: NextRequest) {
  const token = request.cookies.get('opensre_session_token')?.value;

  if (!token) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    const contentType = request.headers.get('content-type') || '';

    let content: string;
    let treeName: string | null = null;

    if (contentType.includes('multipart/form-data')) {
      // Handle file upload
      const formData = await request.formData();
      const file = formData.get('file') as File | null;
      treeName = formData.get('tree') as string | null;

      if (!file) {
        return NextResponse.json({ error: 'No file provided' }, { status: 400 });
      }

      // Extract text content from file
      const fileContent = await file.text();
      const fileName = file.name;

      // Simple preprocessing based on file type
      if (fileName.endsWith('.md') || fileName.endsWith('.txt')) {
        content = fileContent;
      } else {
        // For other files, just use the raw text
        content = fileContent;
      }

      // Add filename as metadata
      content = `# Document: ${fileName}\n\n${content}`;
    } else {
      // Handle JSON body
      const body = await request.json();
      content = body.content;
      treeName = body.tree;

      if (!content) {
        return NextResponse.json({ error: 'No content provided' }, { status: 400 });
      }
    }

    // Send to RAPTOR API
    const res = await fetch(`${RAPTOR_API_URL}/api/v1/tree/documents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        content,
        tree: treeName || undefined,
        similarity_threshold: 0.25,
        auto_rebuild_upper: true,
        save: true,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to add document' }));
      return NextResponse.json(
        { error: err.detail || err.error || 'Failed to add document' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    console.error('RAPTOR API error:', e);
    return NextResponse.json(
      { error: e?.message || 'Failed to add document' },
      { status: 500 }
    );
  }
}
