export interface A2AAuthConfig {
  type?: 'none' | 'bearer' | 'apikey' | 'oauth2';
  token?: string;
  api_key?: string;
  apiKey?: string;
  location?: 'header' | 'query';
  key_name?: string;
  headerName?: string;
  token_url?: string;
  tokenUrl?: string;
  client_id?: string;
  clientId?: string;
  client_secret?: string;
  clientSecret?: string;
  scope?: string;
}

export interface A2ATestConnectionOptions {
  id?: string;
  name?: string;
  url?: string;
  auth?: A2AAuthConfig;
  timeout?: number;
}

export interface A2ATestResult {
  success: boolean;
  message: string;
  agentInfo?: unknown;
}

export async function testA2AConnection(
  config: A2ATestConnectionOptions
): Promise<A2ATestResult> {
  const url = config.url?.trim();
  if (!url) {
    return {
      success: false,
      message: 'URL is required',
    };
  }

  try {
    const res = await fetch('/api/a2a/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });

    let data: Record<string, unknown> | null = null;
    try {
      data = (await res.json()) as Record<string, unknown>;
    } catch {
      return {
        success: false,
        message: 'Endpoint responded, but did not identify itself as a supported A2A agent.',
      };
    }

    if (data && typeof data === 'object') {
      const isSuccess = data.success === true;
      return {
        success: isSuccess,
        message:
          typeof data.message === 'string' && data.message.trim()
            ? data.message
            : isSuccess
              ? 'Connection successful. Remote A2A agent is reachable.'
              : 'Connection failed',
        agentInfo: data.agentInfo,
      };
    }

    return {
      success: false,
      message: 'Invalid response from connection test endpoint',
    };
  } catch (err) {
    return {
      success: false,
      message: (err as Error).message || 'Could not reach the remote agent.',
    };
  }
}
