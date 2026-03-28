import { NextRequest, NextResponse } from 'next/server';

interface A2ATestRequest {
  id: string;
  name: string;
  url: string;
  auth: {
    type: 'none' | 'bearer' | 'apikey' | 'oauth2';
    token?: string;
    apiKey?: string;
    headerName?: string;
    clientId?: string;
    clientSecret?: string;
    tokenUrl?: string;
  };
  timeout?: number;
}

export async function POST(request: NextRequest) {
  try {
    const config: A2ATestRequest = await request.json();

    // Validate required fields
    if (!config.url) {
      return NextResponse.json(
        { success: false, message: 'URL is required' },
        { status: 400 }
      );
    }

    // Prepare headers based on auth type
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (config.auth.type === 'bearer' && config.auth.token) {
      headers['Authorization'] = `Bearer ${config.auth.token}`;
    } else if (config.auth.type === 'apikey' && config.auth.apiKey) {
      const headerName = config.auth.headerName || 'X-API-Key';
      headers[headerName] = config.auth.apiKey;
    } else if (config.auth.type === 'oauth2') {
      // For OAuth2, we'd need to get a token first
      // For now, just test the token URL
      if (config.auth.tokenUrl) {
        try {
          const tokenRes = await fetch(config.auth.tokenUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
              grant_type: 'client_credentials',
              client_id: config.auth.clientId || '',
              client_secret: config.auth.clientSecret || '',
            }),
          });

          if (!tokenRes.ok) {
            return NextResponse.json(
              { success: false, message: 'OAuth2 token request failed' },
              { status: 400 }
            );
          }

          const tokenData = await tokenRes.json();
          if (tokenData.access_token) {
            headers['Authorization'] = `Bearer ${tokenData.access_token}`;
          }
        } catch (e) {
          return NextResponse.json(
            { success: false, message: `OAuth2 error: ${(e as Error).message}` },
            { status: 400 }
          );
        }
      }
    }

    // Test the A2A endpoint by sending a simple info request
    const testPayload = {
      jsonrpc: '2.0',
      id: 'test-' + Date.now(),
      method: 'agent/info',
      params: {},
    };

    const controller = new AbortController();
    const timeout = config.timeout || 10; // 10 second timeout for test
    const timeoutId = setTimeout(() => controller.abort(), timeout * 1000);

    try {
      const response = await fetch(config.url, {
        method: 'POST',
        headers,
        body: JSON.stringify(testPayload),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        return NextResponse.json(
          {
            success: false,
            message: `Connection failed: ${response.status} ${response.statusText}`,
          },
          { status: 200 }
        );
      }

      // Check content type
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const text = await response.text();
        return NextResponse.json({
          success: false,
          message: `Connected but received HTML/non-JSON response. The endpoint might not be an A2A agent. Content-Type: ${contentType || 'none'}`,
        });
      }

      const data = await response.json();

      // Check if it's a valid JSON-RPC response
      if (data.jsonrpc === '2.0' && (data.result || data.error)) {
        return NextResponse.json({
          success: true,
          message: data.error
            ? `Connected but received error: ${data.error.message || JSON.stringify(data.error)}`
            : 'Connection successful! Agent is reachable.',
          agentInfo: data.result,
        });
      } else {
        return NextResponse.json({
          success: false,
          message: 'Connected but response is not valid A2A JSON-RPC format',
        });
      }
    } catch (e) {
      clearTimeout(timeoutId);

      if ((e as Error).name === 'AbortError') {
        return NextResponse.json({
          success: false,
          message: 'Connection timeout',
        });
      }

      return NextResponse.json({
        success: false,
        message: `Connection error: ${(e as Error).message}`,
      });
    }
  } catch (error) {
    console.error('A2A test error:', error);
    return NextResponse.json(
      {
        success: false,
        message: `Test failed: ${(error as Error).message}`,
      },
      { status: 500 }
    );
  }
}
