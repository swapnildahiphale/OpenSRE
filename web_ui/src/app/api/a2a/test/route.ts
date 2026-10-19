import { NextRequest, NextResponse } from 'next/server';
import { validateTargetUrl, pinnedFetch } from '@/lib/ssrfGuard';

export const runtime = 'nodejs';

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

export interface A2ATestRequest {
  id?: string;
  name?: string;
  url?: string;
  auth?: A2AAuthConfig;
  timeout?: number;
}

interface JsonRpcResponse {
  jsonrpc?: string;
  id?: string | number | null;
  result?: unknown;
  error?: {
    code?: number;
    message?: string;
    data?: unknown;
  } | null;
}

interface OAuth2TokenResponse {
  access_token?: string;
  token_type?: string;
  expires_in?: number;
}

/**
 * Compatibility heuristic for A2A Agent Card / agent-info response shape.
 * As there is no single canonical contract across all A2A agents in the repository,
 * this rule validates that the remote endpoint identifies itself as a supported A2A agent
 * rather than a generic JSON-RPC endpoint.
 *
 * Rule:
 * 1. result must be a plain object (not null, not array).
 * 2. result.name must be a non-empty trimmed string (max 200 chars).
 * 3. At least one valid corroborating field must be present:
 *    - string version (non-empty trimmed string)
 *    - string protocolVersion (non-empty trimmed string)
 *    - string url that parses as http: or https:
 *    - non-empty plain-object capabilities
 *    - non-empty skills array of objects, each having a string id or name
 */
export function isSupportedA2AAgentResult(result: unknown): boolean {
  if (!result || typeof result !== 'object' || Array.isArray(result)) {
    return false;
  }

  const res = result as Record<string, unknown>;

  // Must have a non-empty trimmed string name (max 200 chars)
  if (typeof res.name !== 'string') {
    return false;
  }
  const trimmedName = res.name.trim();
  if (!trimmedName || trimmedName.length > 200) {
    return false;
  }

  // Corroborating fields:
  // 1. string version
  const hasValidVersion =
    typeof res.version === 'string' && res.version.trim().length > 0;

  // 2. string protocolVersion
  const hasValidProtocolVersion =
    typeof res.protocolVersion === 'string' && res.protocolVersion.trim().length > 0;

  // 3. string url that parses as http: or https:
  let hasValidUrl = false;
  if (typeof res.url === 'string' && res.url.trim().length > 0) {
    try {
      const parsed = new URL(res.url.trim());
      hasValidUrl = parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      hasValidUrl = false;
    }
  }

  // 4. non-empty plain-object capabilities
  const hasValidCapabilities =
    res.capabilities !== null &&
    typeof res.capabilities === 'object' &&
    !Array.isArray(res.capabilities) &&
    Object.keys(res.capabilities).length > 0;

  // 5. non-empty skills array of objects each with a string id or name
  let hasValidSkills = false;
  if (Array.isArray(res.skills) && res.skills.length > 0) {
    hasValidSkills = res.skills.every((skill) => {
      if (!skill || typeof skill !== 'object' || Array.isArray(skill)) {
        return false;
      }
      const s = skill as Record<string, unknown>;
      const hasId = typeof s.id === 'string' && s.id.trim().length > 0;
      const hasName = typeof s.name === 'string' && s.name.trim().length > 0;
      return hasId || hasName;
    });
  }

  return (
    hasValidVersion ||
    hasValidProtocolVersion ||
    hasValidUrl ||
    hasValidCapabilities ||
    hasValidSkills
  );
}

export async function POST(request: NextRequest) {
  try {
    let config: A2ATestRequest;
    try {
      config = await request.json();
    } catch {
      return NextResponse.json(
        { success: false, message: 'Invalid JSON request body' },
        { status: 400 }
      );
    }

    // Validate required URL field
    if (!config || typeof config !== 'object' || !config.url || typeof config.url !== 'string' || !config.url.trim()) {
      return NextResponse.json(
        { success: false, message: 'URL is required' },
        { status: 400 }
      );
    }

    const trimmedUrl = config.url.trim();

    // Check basic URL validity and protocol upfront
    let targetUrl: URL;
    try {
      targetUrl = new URL(trimmedUrl);
    } catch {
      return NextResponse.json(
        { success: false, message: 'Invalid URL. Must be a valid HTTP or HTTPS URL.' },
        { status: 400 }
      );
    }

    if (targetUrl.protocol !== 'http:' && targetUrl.protocol !== 'https:') {
      return NextResponse.json(
        { success: false, message: 'Invalid URL protocol. Only HTTP and HTTPS are supported.' },
        { status: 400 }
      );
    }

    // SSRF validation (blocks loopback, private, link-local, multicast, metadata, credentials)
    const ssrfCheck = await validateTargetUrl(trimmedUrl);
    if (!ssrfCheck.allowed || !ssrfCheck.validatedAddresses?.length) {
      return NextResponse.json(
        { success: false, message: ssrfCheck.error || 'Target address is not allowed.' },
        { status: 400 }
      );
    }

    // Bounded timeout: default 10 seconds, clamped to 1–30 seconds
    const rawTimeout = typeof config.timeout === 'number' && !Number.isNaN(config.timeout) ? config.timeout : 10;
    const timeoutSeconds = Math.max(1, Math.min(30, Math.floor(rawTimeout)));

    // Prepare headers based on auth type
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    };

    const auth = config.auth || { type: 'none' };
    const authType = auth.type || 'none';

    if (authType === 'bearer') {
      if (auth.token) {
        headers['Authorization'] = `Bearer ${auth.token}`;
      }
    } else if (authType === 'apikey') {
      const apiKey = auth.api_key || auth.apiKey;
      if (apiKey) {
        const location = auth.location || 'header';
        const keyName = auth.key_name || auth.headerName || 'X-API-Key';
        if (location === 'query') {
          targetUrl.searchParams.set(keyName, apiKey);
        } else {
          headers[keyName] = apiKey;
        }
      }
    } else if (authType === 'oauth2') {
      const tokenUrl = auth.token_url || auth.tokenUrl;
      const clientId = auth.client_id || auth.clientId;
      const clientSecret = auth.client_secret || auth.clientSecret;
      const scope = auth.scope;

      if (!tokenUrl || typeof tokenUrl !== 'string' || !tokenUrl.trim()) {
        return NextResponse.json(
          { success: false, message: 'OAuth2 configuration error: token URL is required' },
          { status: 200 }
        );
      }

      // Validate OAuth2 token URL against SSRF and protocol requirements
      const tokenSsrfCheck = await validateTargetUrl(tokenUrl.trim());
      if (!tokenSsrfCheck.allowed || !tokenSsrfCheck.validatedAddresses?.length) {
        return NextResponse.json(
          { success: false, message: 'Target address is not allowed.' },
          { status: 400 }
        );
      }

      const tokenParams = new URLSearchParams({
        grant_type: 'client_credentials',
        client_id: clientId || '',
        client_secret: clientSecret || '',
      });
      if (scope) {
        tokenParams.set('scope', scope);
      }

      try {
        const tokenRes = await pinnedFetch({
          url: tokenUrl.trim(),
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            Accept: 'application/json',
          },
          body: tokenParams,
          timeoutSeconds,
          validatedAddresses: tokenSsrfCheck.validatedAddresses,
          redirect: 'manual',
        });

        if (!tokenRes.ok) {
          return NextResponse.json(
            { success: false, message: `OAuth2 token request failed with status ${tokenRes.status}` },
            { status: 200 }
          );
        }

        const tokenData = (await tokenRes.json()) as OAuth2TokenResponse;
        if (!tokenData || typeof tokenData !== 'object' || !tokenData.access_token) {
          return NextResponse.json(
            { success: false, message: 'OAuth2 token response missing access_token' },
            { status: 200 }
          );
        }

        headers['Authorization'] = `Bearer ${tokenData.access_token}`;
      } catch (e) {
        if ((e as Error).name === 'AbortError') {
          return NextResponse.json(
            { success: false, message: `Connection timed out after ${timeoutSeconds}s.` },
            { status: 200 }
          );
        }
        return NextResponse.json(
          { success: false, message: 'OAuth2 authentication error: failed to obtain token' },
          { status: 200 }
        );
      }
    }

    // Generate request ID and keep it for response verification
    const requestId = `test-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

    // Test the A2A endpoint by sending an agent/info JSON-RPC request
    const testPayload = {
      jsonrpc: '2.0',
      id: requestId,
      method: 'agent/info',
      params: {},
    };

    try {
      const response = await pinnedFetch({
        url: targetUrl.toString(),
        method: 'POST',
        headers,
        body: JSON.stringify(testPayload),
        timeoutSeconds,
        validatedAddresses: ssrfCheck.validatedAddresses,
        redirect: 'manual',
      });

      // Controlled handling of redirects (automatic redirects disabled)
      if (response.status >= 300 && response.status < 400) {
        return NextResponse.json(
          {
            success: false,
            message: `Remote endpoint returned a redirect (${response.status}). Automatic redirects are disabled.`,
          },
          { status: 200 }
        );
      }

      // HTTP failure check
      if (!response.ok) {
        return NextResponse.json(
          {
            success: false,
            message: response.statusText
              ? `Connection failed: ${response.status} ${response.statusText}`
              : `Connection failed: ${response.status}`,
          },
          { status: 200 }
        );
      }

      // Check content-type
      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        return NextResponse.json(
          {
            success: false,
            message: 'Endpoint responded, but did not identify itself as a supported A2A agent.',
          },
          { status: 200 }
        );
      }

      let data: JsonRpcResponse | null = null;
      try {
        data = (await response.json()) as JsonRpcResponse;
      } catch {
        return NextResponse.json(
          {
            success: false,
            message: 'Endpoint responded, but did not identify itself as a supported A2A agent.',
          },
          { status: 200 }
        );
      }

      // Check if it's a valid JSON-RPC 2.0 response object
      if (!data || typeof data !== 'object' || Array.isArray(data) || data.jsonrpc !== '2.0') {
        return NextResponse.json(
          {
            success: false,
            message: 'Endpoint responded, but did not identify itself as a supported A2A agent.',
          },
          { status: 200 }
        );
      }

      // Strict request ID verification: response.id must match the sent request ID
      if (data.id === undefined || data.id === null || data.id !== requestId) {
        return NextResponse.json(
          {
            success: false,
            message: 'Endpoint responded, but did not identify itself as a supported A2A agent.',
          },
          { status: 200 }
        );
      }

      // Treat JSON-RPC error as failure even if HTTP status was 200
      if (data.error) {
        const errorMsg =
          typeof data.error.message === 'string' && data.error.message.trim()
            ? data.error.message
            : 'Endpoint returned a JSON-RPC error';
        return NextResponse.json(
          {
            success: false,
            message: `Agent error: ${errorMsg}`,
          },
          { status: 200 }
        );
      }

      // Stricter agent card check: result must be a non-array object with recognisable identity/capability field
      if (!isSupportedA2AAgentResult(data.result)) {
        return NextResponse.json(
          {
            success: false,
            message: 'Endpoint responded, but did not identify itself as a supported A2A agent.',
          },
          { status: 200 }
        );
      }

      return NextResponse.json(
        {
          success: true,
          message: 'Connection successful. Remote A2A agent is reachable.',
          agentInfo: data.result,
        },
        { status: 200 }
      );
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        return NextResponse.json(
          {
            success: false,
            message: `Connection timed out after ${timeoutSeconds}s.`,
          },
          { status: 200 }
        );
      }

      return NextResponse.json(
        {
          success: false,
          message: 'Could not reach the remote agent.',
        },
        { status: 200 }
      );
    }
  } catch {
    return NextResponse.json(
      {
        success: false,
        message: 'Internal server error while testing connection',
      },
      { status: 500 }
    );
  }
}
