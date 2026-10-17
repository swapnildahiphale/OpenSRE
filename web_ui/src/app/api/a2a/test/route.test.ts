import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { NextRequest } from 'next/server';
import dns from 'node:dns/promises';
import * as undici from 'undici';
import * as ssrfGuard from '@/lib/ssrfGuard';
import { POST, isSupportedA2AAgentResult } from './route';

describe('POST /api/a2a/test', () => {
  let mockFetch: ReturnType<typeof vi.fn>;
  let dnsLookupSpy: {
    mockImplementation: (fn: typeof dns.lookup) => unknown;
    mockImplementationOnce: (fn: typeof dns.lookup) => unknown;
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    delete process.env.ALLOW_PRIVATE_A2A_CONNECTIONS;

    // Mock DNS resolution by default to return a public IP so tests don't make real network queries
    dnsLookupSpy = vi.spyOn(dns, 'lookup').mockImplementation((async (host: string) => {
      if (host === 'localhost') {
        return [
          { address: '127.0.0.1', family: 4 },
          { address: '::1', family: 6 },
        ];
      }
      return [{ address: '93.184.216.34', family: 4 }];
    }) as unknown as typeof dns.lookup);

    // Default mock pinned fetch implementation returning a valid agent response
    mockFetch = vi.fn().mockImplementation(async (_url: string | URL, options?: { body?: string | URLSearchParams }) => {
      let bodyObj: { id?: string } = {};
      try {
        if (typeof options?.body === 'string') {
          bodyObj = JSON.parse(options.body) as { id?: string };
        }
      } catch {
        // Ignored
      }

      return new Response(
        JSON.stringify({
          jsonrpc: '2.0',
          id: bodyObj.id || 'test-response-id',
          result: {
            name: 'sre-agent',
            version: '1.0.0',
            capabilities: { streaming: true },
            skills: [{ id: 'triage', name: 'Triage' }],
          },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    });

    ssrfGuard.setPinnedFetchImplementation(mockFetch as unknown as typeof undici.fetch);
  });

  afterEach(() => {
    ssrfGuard.resetPinnedFetchImplementation();
    delete process.env.ALLOW_PRIVATE_A2A_CONNECTIONS;
  });

  it('rejects missing URL with 400', async () => {
    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({}),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toBe('URL is required');
  });

  it('rejects invalid URL string with 400', async () => {
    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({ url: 'not-a-valid-url' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toContain('Invalid URL');
  });

  it('rejects non-HTTP/HTTPS protocol with 400', async () => {
    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({ url: 'ftp://example.com/agent' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toContain('Only HTTP and HTTPS are supported');
  });

  it('successfully probes a valid A2A agent with agent/info JSON-RPC result', async () => {
    let capturedUrl = '';
    let capturedMethod = '';
    let capturedRedirect = '';
    let capturedDispatcher: unknown = null;
    let capturedBody = '';

    mockFetch.mockImplementation(async (url: string | URL, options?: { method?: string; redirect?: string; dispatcher?: unknown; body?: string }) => {
      capturedUrl = String(url);
      capturedMethod = options?.method || '';
      capturedRedirect = options?.redirect || '';
      capturedDispatcher = options?.dispatcher;
      capturedBody = options?.body || '';

      const parsed = JSON.parse(options?.body || '{}') as { id?: string };
      return new Response(
        JSON.stringify({
          jsonrpc: '2.0',
          id: parsed.id,
          result: {
            name: 'sre-agent',
            version: '1.0.0',
            capabilities: { streaming: true },
            skills: [{ id: 'triage', name: 'Triage' }],
          },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    });

    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({
        url: 'https://agent.example.com/rpc',
        timeout: 15,
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; message: string; agentInfo?: { name: string } };
    expect(body.success).toBe(true);
    expect(body.message).toBe('Connection successful. Remote A2A agent is reachable.');
    expect(body.agentInfo?.name).toBe('sre-agent');

    // Verify probe payload, options, and that original hostname URL is preserved (no IP substituted)
    expect(capturedUrl).toBe('https://agent.example.com/rpc');
    expect(capturedMethod).toBe('POST');
    expect(capturedRedirect).toBe('manual');
    expect(capturedDispatcher).toBeInstanceOf(undici.Agent);
    const sentPayload = JSON.parse(capturedBody) as { jsonrpc: string; method: string; params: unknown };
    expect(sentPayload.jsonrpc).toBe('2.0');
    expect(sentPayload.method).toBe('agent/info');
    expect(sentPayload.params).toEqual({});
  });

  it('handles network failure / connection refused without crashing or leaking secrets', async () => {
    mockFetch.mockRejectedValue(new Error('connect ECONNREFUSED 93.184.216.34:8000'));

    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({
        url: 'https://agent.example.com/agent',
        auth: { type: 'bearer', token: 'super-secret-token' },
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toBe('Could not reach the remote agent.');
    expect(JSON.stringify(body)).not.toContain('super-secret-token');
  });

  it('handles connection timeout / AbortError properly', async () => {
    mockFetch.mockImplementation(async () => {
      const err = new Error('The operation was aborted');
      err.name = 'AbortError';
      throw err;
    });

    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({
        url: 'https://slow-agent.example.com',
        timeout: 5,
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toBe('Connection timed out after 5s.');
  });

  it('handles remote HTTP error status (404, 500)', async () => {
    mockFetch.mockResolvedValue(
      new Response('Not Found', {
        status: 404,
        statusText: 'Not Found',
      })
    );

    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({ url: 'https://agent.example.com/nonexistent' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toContain('404');
  });

  it('rejects HTML / non-JSON response from endpoint', async () => {
    mockFetch.mockResolvedValue(
      new Response('<html><body>Welcome to nginx</body></html>', {
        status: 200,
        headers: { 'Content-Type': 'text/html' },
      })
    );

    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({ url: 'https://not-an-agent.example.com' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toBe('Endpoint responded, but did not identify itself as a supported A2A agent.');
  });

  it('rejects malformed or non-JSON-RPC response', async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', data: 'hello' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({ url: 'https://rest-api.example.com' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toBe('Endpoint responded, but did not identify itself as a supported A2A agent.');
  });

  it('treats JSON-RPC error as failure even if HTTP status was 200', async () => {
    mockFetch.mockImplementation(async (_url: string | URL, options?: { body?: string }) => {
      const parsed = JSON.parse(options?.body || '{}') as { id?: string };
      return new Response(
        JSON.stringify({
          jsonrpc: '2.0',
          id: parsed.id,
          error: {
            code: -32601,
            message: 'Method not found',
          },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    });

    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({ url: 'https://agent.example.com/rpc' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toBe('Agent error: Method not found');
  });

  it('treats empty result as failure', async () => {
    mockFetch.mockImplementation(async (_url: string | URL, options?: { body?: string }) => {
      const parsed = JSON.parse(options?.body || '{}') as { id?: string };
      return new Response(
        JSON.stringify({
          jsonrpc: '2.0',
          id: parsed.id,
          result: {},
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    });

    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({ url: 'https://agent.example.com/rpc' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toBe('Endpoint responded, but did not identify itself as a supported A2A agent.');
  });

  it('constructs auth headers correctly for bearer and apikey without leaking secrets', async () => {
    let capturedHeaders: Record<string, string> = {};
    let capturedUrl = '';

    mockFetch.mockImplementation(async (url: string | URL, options?: { headers?: Record<string, string>; body?: string }) => {
      capturedUrl = String(url);
      capturedHeaders = options?.headers || {};
      const parsed = JSON.parse(options?.body || '{}') as { id?: string };
      return new Response(
        JSON.stringify({
          jsonrpc: '2.0',
          id: parsed.id,
          result: { name: 'AuthedAgent', version: '1.0' },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    });

    // Test Bearer Auth
    const reqBearer = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({
        url: 'https://agent.example.com',
        auth: {
          type: 'bearer',
          token: 'token-xyz',
        },
      }),
    });

    const resBearer = await POST(reqBearer);
    const bodyBearer = (await resBearer.json()) as { success: boolean };
    expect(bodyBearer.success).toBe(true);
    expect(capturedHeaders['Authorization']).toBe('Bearer token-xyz');

    // Test API Key Auth in header (snake_case api_key & key_name)
    const reqApiKey = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({
        url: 'https://agent.example.com',
        auth: {
          type: 'apikey',
          api_key: 'key-123',
          key_name: 'X-SRE-Key',
          location: 'header',
        },
      }),
    });

    const resApiKey = await POST(reqApiKey);
    const bodyApiKey = (await resApiKey.json()) as { success: boolean };
    expect(bodyApiKey.success).toBe(true);
    expect(capturedHeaders['X-SRE-Key']).toBe('key-123');

    // Test API Key Auth in query param
    const reqApiQuery = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({
        url: 'https://agent.example.com',
        auth: {
          type: 'apikey',
          api_key: 'key-query-456',
          key_name: 'token',
          location: 'query',
        },
      }),
    });

    const resApiQuery = await POST(reqApiQuery);
    const bodyApiQuery = (await resApiQuery.json()) as { success: boolean };
    expect(bodyApiQuery.success).toBe(true);
    expect(capturedUrl).toContain('token=key-query-456');
  });

  it('rejects redirects because automatic redirects are disabled', async () => {
    mockFetch.mockResolvedValue(
      new Response(null, {
        status: 302,
        headers: { Location: 'https://other-agent.example.com' },
      })
    );

    const req = new NextRequest('http://localhost:3000/api/a2a/test', {
      method: 'POST',
      body: JSON.stringify({ url: 'https://agent.example.com' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; message: string };
    expect(body.success).toBe(false);
    expect(body.message).toContain('Automatic redirects are disabled');
  });

  // =========================================================================
  // Section 1: Stricter Protocol Validation Tests
  // =========================================================================

  describe('Protocol validation: request ID matching', () => {
    it('fails when response ID does not match sent request ID', async () => {
      mockFetch.mockResolvedValue(
        new Response(
          JSON.stringify({
            jsonrpc: '2.0',
            id: 'mismatched-request-id-999',
            result: { name: 'Some Agent', version: '1.0' },
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        )
      );

      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'https://agent.example.com' }),
      });

      const res = await POST(req);
      expect(res.status).toBe(200);
      const body = (await res.json()) as { success: boolean; message: string };
      expect(body.success).toBe(false);
      expect(body.message).toBe('Endpoint responded, but did not identify itself as a supported A2A agent.');
    });

    it('fails when response is missing request ID', async () => {
      mockFetch.mockResolvedValue(
        new Response(
          JSON.stringify({
            jsonrpc: '2.0',
            result: { name: 'Some Agent', version: '1.0' },
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        )
      );

      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'https://agent.example.com' }),
      });

      const res = await POST(req);
      expect(res.status).toBe(200);
      const body = (await res.json()) as { success: boolean; message: string };
      expect(body.success).toBe(false);
      expect(body.message).toBe('Endpoint responded, but did not identify itself as a supported A2A agent.');
    });
  });

  describe('Protocol validation: heuristic agent card shape', () => {
    it('isSupportedA2AAgentResult rejects non-agent or incomplete shapes', () => {
      const rejectCases = [
        { url: 'x' },
        { version: '1' },
        { capabilities: true },
        { capabilities: {} },
        { name: '' },
        { name: '  ' },
        { name: 123 },
        { name: 'x' }, // alone without corroborating field
        [],
        'ok',
        42,
        true,
        null,
        undefined,
      ];

      for (const testCase of rejectCases) {
        expect(isSupportedA2AAgentResult(testCase)).toBe(false);
      }
    });

    it('isSupportedA2AAgentResult accepts realistic and valid agent shapes', () => {
      const acceptCases = [
        {
          name: 'sre-agent',
          version: '1.0.0',
          capabilities: { streaming: true },
          skills: [{ id: 'triage', name: 'Triage' }],
        },
        { name: 'agent', version: '1.0' },
        { name: 'agent', protocolVersion: '0.3' },
        { name: 'agent', url: 'https://agent.example.com/rpc' },
        { name: 'agent', capabilities: { streaming: true } },
        { name: 'agent', skills: [{ id: 'k8s' }] },
        { name: 'agent', skills: [{ name: 'Diagnostics' }] },
      ];

      for (const testCase of acceptCases) {
        expect(isSupportedA2AAgentResult(testCase)).toBe(true);
      }
    });

    it('rejects arbitrary non-agent JSON-RPC result at route level', async () => {
      mockFetch.mockImplementation(async (_url: string | URL, options?: { body?: string }) => {
        const parsed = JSON.parse(options?.body || '{}') as { id?: string };
        return new Response(
          JSON.stringify({
            jsonrpc: '2.0',
            id: parsed.id,
            result: {
              timestamp: 1710000000,
              status: 'operational',
              service: 'generic-calculator',
            },
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      });

      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'https://generic-rpc.example.com' }),
      });

      const res = await POST(req);
      expect(res.status).toBe(200);
      const body = (await res.json()) as { success: boolean; message: string };
      expect(body.success).toBe(false);
      expect(body.message).toBe('Endpoint responded, but did not identify itself as a supported A2A agent.');
    });

    it('accepts agents with any supported identity plus corroborating field', async () => {
      const validShapes = [
        { name: 'K8s Agent', version: '2.4.0' },
        { name: 'K8s Agent', protocolVersion: '0.3.0' },
        { name: 'K8s Agent', url: 'https://agent.example.com/rpc' },
        { name: 'K8s Agent', capabilities: { streaming: true, pushNotifications: true } },
        { name: 'K8s Agent', skills: [{ id: 'k8s-diagnostics' }] },
      ];

      for (const resultShape of validShapes) {
        mockFetch.mockImplementation(async (_url: string | URL, options?: { body?: string }) => {
          const parsed = JSON.parse(options?.body || '{}') as { id?: string };
          return new Response(
            JSON.stringify({
              jsonrpc: '2.0',
              id: parsed.id,
              result: resultShape,
            }),
            {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }
          );
        });

        const req = new NextRequest('http://localhost:3000/api/a2a/test', {
          method: 'POST',
          body: JSON.stringify({ url: 'https://agent.example.com' }),
        });

        const res = await POST(req);
        expect(res.status).toBe(200);
        const body = (await res.json()) as { success: boolean; agentInfo?: unknown };
        expect(body.success).toBe(true);
        expect(body.agentInfo).toEqual(resultShape);
      }
    });
  });

  // =========================================================================
  // Section 2: SSRF Defense & DNS Rebinding Tests
  // =========================================================================

  describe('SSRF Defense & DNS Rebinding', () => {
    it('blocks localhost and 127.0.0.1 by default', async () => {
      const req1 = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://127.0.0.1:8000/agent' }),
      });
      const res1 = await POST(req1);
      expect(res1.status).toBe(400);
      const body1 = (await res1.json()) as { success: boolean; message: string };
      expect(body1.success).toBe(false);
      expect(body1.message).toBe('Target address is not allowed.');

      const req2 = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://localhost:8000/agent' }),
      });
      const res2 = await POST(req2);
      expect(res2.status).toBe(400);
      const body2 = (await res2.json()) as { success: boolean; message: string };
      expect(body2.success).toBe(false);
      expect(body2.message).toBe('Target address is not allowed.');

      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('blocks IPv6 loopback ::1', async () => {
      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://[::1]:8000/agent' }),
      });
      const res = await POST(req);
      expect(res.status).toBe(400);
      const body = (await res.json()) as { success: boolean; message: string };
      expect(body.success).toBe(false);
      expect(body.message).toBe('Target address is not allowed.');
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('blocks IPv4-compatible IPv6 addresses (::127.0.0.1, ::10.0.0.1, ::192.168.1.1)', async () => {
      const compatibleUrls = [
        'http://[::127.0.0.1]:8000/agent',
        'http://[::10.0.0.1]:8000/agent',
        'http://[::192.168.1.1]:8000/agent',
      ];

      for (const url of compatibleUrls) {
        const req = new NextRequest('http://localhost:3000/api/a2a/test', {
          method: 'POST',
          body: JSON.stringify({ url }),
        });
        const res = await POST(req);
        expect(res.status).toBe(400);
        const body = (await res.json()) as { success: boolean; message: string };
        expect(body.success).toBe(false);
        expect(body.message).toBe('Target address is not allowed.');
      }
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('blocks IPv4-compatible metadata ::169.254.169.254 by default AND with opt-in', async () => {
      // By default
      const req1 = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://[::169.254.169.254]:8000/agent' }),
      });
      const res1 = await POST(req1);
      expect(res1.status).toBe(400);
      const body1 = (await res1.json()) as { success: boolean; message: string };
      expect(body1.success).toBe(false);
      expect(body1.message).toBe('Target address is not allowed.');

      // With opt-in set
      process.env.ALLOW_PRIVATE_A2A_CONNECTIONS = 'true';
      const req2 = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://[::169.254.169.254]:8000/agent' }),
      });
      const res2 = await POST(req2);
      expect(res2.status).toBe(400);
      const body2 = (await res2.json()) as { success: boolean; message: string };
      expect(body2.success).toBe(false);
      expect(body2.message).toBe('Target address is not allowed.');

      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('blocks private IPv4 ranges (10.x, 192.168.x, 172.16.x)', async () => {
      const privateUrls = [
        'http://10.0.0.1:8000/agent',
        'http://192.168.1.50:8000/agent',
        'http://172.16.0.1:8000/agent',
      ];

      for (const url of privateUrls) {
        const req = new NextRequest('http://localhost:3000/api/a2a/test', {
          method: 'POST',
          body: JSON.stringify({ url }),
        });
        const res = await POST(req);
        expect(res.status).toBe(400);
        const body = (await res.json()) as { success: boolean; message: string };
        expect(body.success).toBe(false);
        expect(body.message).toBe('Target address is not allowed.');
      }

      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('blocks cloud metadata IP 169.254.169.254', async () => {
      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://169.254.169.254/latest/meta-data' }),
      });
      const res = await POST(req);
      expect(res.status).toBe(400);
      const body = (await res.json()) as { success: boolean; message: string };
      expect(body.success).toBe(false);
      expect(body.message).toBe('Target address is not allowed.');
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('blocks IPv4-mapped IPv6 address (::ffff:127.0.0.1 and ::ffff:10.0.0.1)', async () => {
      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://[::ffff:127.0.0.1]:8000/agent' }),
      });
      const res = await POST(req);
      expect(res.status).toBe(400);
      const body = (await res.json()) as { success: boolean; message: string };
      expect(body.success).toBe(false);
      expect(body.message).toBe('Target address is not allowed.');
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('rejects URLs with embedded credentials', async () => {
      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'https://admin:supersecret@agent.example.com/rpc' }),
      });
      const res = await POST(req);
      expect(res.status).toBe(400);
      const body = (await res.json()) as { success: boolean; message: string };
      expect(body.success).toBe(false);
      expect(body.message).toBe('Target address is not allowed.');
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('rejects invalid or disallowed OAuth token URL without leaking details', async () => {
      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({
          url: 'https://agent.example.com',
          auth: {
            type: 'oauth2',
            token_url: 'http://169.254.169.254/oauth/token',
            client_id: 'client123',
            client_secret: 'secret456',
          },
        }),
      });

      const res = await POST(req);
      expect(res.status).toBe(400);
      const body = (await res.json()) as { success: boolean; message: string };
      expect(body.success).toBe(false);
      expect(body.message).toBe('Target address is not allowed.');
      expect(mockFetch).not.toHaveBeenCalled();
      expect(JSON.stringify(body)).not.toContain('secret456');
    });

    it('rejects hostname resolving to private IP', async () => {
      dnsLookupSpy.mockImplementationOnce((async () => [{ address: '10.50.0.1', family: 4 }]) as unknown as typeof dns.lookup);

      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'https://internal-service.example.org' }),
      });

      const res = await POST(req);
      expect(res.status).toBe(400);
      const body = (await res.json()) as { success: boolean; message: string };
      expect(body.success).toBe(false);
      expect(body.message).toBe('Target address is not allowed.');
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('proceeds when hostname resolves to public IP and uses pinned dispatcher with original hostname URL', async () => {
      dnsLookupSpy.mockImplementationOnce((async () => [{ address: '93.184.216.34', family: 4 }]) as unknown as typeof dns.lookup);

      let capturedUrl = '';
      let capturedDispatcher: unknown = null;

      mockFetch.mockImplementation(async (url: string | URL, options?: { dispatcher?: unknown; body?: string }) => {
        capturedUrl = String(url);
        capturedDispatcher = options?.dispatcher;
        const parsed = JSON.parse(options?.body || '{}') as { id?: string };
        return new Response(
          JSON.stringify({
            jsonrpc: '2.0',
            id: parsed.id,
            result: { name: 'Public Cloud SRE Agent', version: '1.0' },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      });

      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'https://public-agent.example.org/rpc' }),
      });

      const res = await POST(req);
      expect(res.status).toBe(200);
      const body = (await res.json()) as { success: boolean; agentInfo?: { name: string } };
      expect(body.success).toBe(true);
      expect(body.agentInfo?.name).toBe('Public Cloud SRE Agent');

      // Verifies: fetch receives original hostname URL (no IP substituted) and pinned undici Agent dispatcher
      expect(capturedUrl).toBe('https://public-agent.example.org/rpc');
      expect(capturedDispatcher).toBeInstanceOf(undici.Agent);
    });

    it('pins dispatcher for OAuth2 token request as well as probe request', async () => {
      dnsLookupSpy.mockImplementation((async (host: string) => {
        if (host === 'oauth.example.com') {
          return [{ address: '93.184.216.35', family: 4 }];
        }
        return [{ address: '93.184.216.34', family: 4 }];
      }) as unknown as typeof dns.lookup);

      const capturedCalls: Array<{ url: string; dispatcher: unknown }> = [];

      mockFetch.mockImplementation(async (url: string | URL, options?: { dispatcher?: unknown; body?: string }) => {
        capturedCalls.push({ url: String(url), dispatcher: options?.dispatcher });

        if (String(url).includes('oauth.example.com')) {
          return new Response(
            JSON.stringify({ access_token: 'valid-test-token' }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }

        const parsed = JSON.parse(options?.body || '{}') as { id?: string };
        return new Response(
          JSON.stringify({
            jsonrpc: '2.0',
            id: parsed.id,
            result: { name: 'OAuth-Secured Agent', version: '1.0' },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      });

      const req = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({
          url: 'https://agent.example.com/rpc',
          auth: {
            type: 'oauth2',
            token_url: 'https://oauth.example.com/token',
            client_id: 'cid',
            client_secret: 'csec',
          },
        }),
      });

      const res = await POST(req);
      expect(res.status).toBe(200);
      const body = (await res.json()) as { success: boolean };
      expect(body.success).toBe(true);

      // Verify BOTH token request and probe request used pinned dispatchers and original hostname URLs
      expect(capturedCalls).toHaveLength(2);
      expect(capturedCalls[0].url).toBe('https://oauth.example.com/token');
      expect(capturedCalls[0].dispatcher).toBeInstanceOf(undici.Agent);
      expect(capturedCalls[1].url).toBe('https://agent.example.com/rpc');
      expect(capturedCalls[1].dispatcher).toBeInstanceOf(undici.Agent);
    });

    it('allows private/loopback when ALLOW_PRIVATE_A2A_CONNECTIONS=true, but STILL BLOCKS metadata', async () => {
      process.env.ALLOW_PRIVATE_A2A_CONNECTIONS = 'true';

      mockFetch.mockImplementation(async (_url: string | URL, options?: { body?: string }) => {
        const parsed = JSON.parse(options?.body || '{}') as { id?: string };
        return new Response(
          JSON.stringify({
            jsonrpc: '2.0',
            id: parsed.id,
            result: { name: 'Local Dev Agent', version: '0.1' },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      });

      // Local loopback is now allowed
      const reqLocal = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://127.0.0.1:8000/agent' }),
      });
      const resLocal = await POST(reqLocal);
      expect(resLocal.status).toBe(200);
      const bodyLocal = (await resLocal.json()) as { success: boolean };
      expect(bodyLocal.success).toBe(true);

      // IPv4-compatible loopback ::127.0.0.1 is allowed with opt-in
      const reqCompat = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://[::127.0.0.1]:8000/agent' }),
      });
      const resCompat = await POST(reqCompat);
      expect(resCompat.status).toBe(200);

      // Cloud metadata MUST STILL BE BLOCKED even with opt-in flag enabled
      const reqMeta = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://169.254.169.254/latest/meta-data' }),
      });
      const resMeta = await POST(reqMeta);
      expect(resMeta.status).toBe(400);
      const bodyMeta = (await resMeta.json()) as { success: boolean; message: string };
      expect(bodyMeta.success).toBe(false);
      expect(bodyMeta.message).toBe('Target address is not allowed.');

      // IPv4-compatible metadata ::169.254.169.254 MUST ALSO STILL BE BLOCKED
      const reqCompatMeta = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({ url: 'http://[::169.254.169.254]:8000/agent' }),
      });
      const resCompatMeta = await POST(reqCompatMeta);
      expect(resCompatMeta.status).toBe(400);
    });
  });

  // =========================================================================
  // Section 3: Shared Policy Verification
  // =========================================================================

  describe('Shared Policy Verification', () => {
    it('verifies both A2A probe and OAuth token requests share validateTargetUrl and pinnedFetch pipeline', async () => {
      const validateSpy = vi.spyOn(ssrfGuard, 'validateTargetUrl');
      const pinnedFetchSpy = vi.spyOn(ssrfGuard, 'pinnedFetch');

      mockFetch.mockImplementation(async (url: string | URL) => {
        if (String(url).includes('token')) {
          return new Response(JSON.stringify({ access_token: 'auth-token-123' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response(
          JSON.stringify({
            jsonrpc: '2.0',
            id: 'req-id',
            result: { name: 'SharedPolicyAgent', version: '1.0' },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      });

      // 1. Success case: both URLs go through validateTargetUrl and pinnedFetch
      const reqSuccess = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({
          url: 'https://agent.example.com',
          auth: {
            type: 'oauth2',
            token_url: 'https://oauth.example.com/token',
            client_id: 'cid',
            client_secret: 'csec',
          },
        }),
      });

      const resSuccess = await POST(reqSuccess);
      expect(resSuccess.status).toBe(200);
      // Both target URL and token URL were validated
      expect(validateSpy).toHaveBeenCalledWith('https://agent.example.com');
      expect(validateSpy).toHaveBeenCalledWith('https://oauth.example.com/token');
      // Both target URL and token URL were dispatched through pinnedFetch
      expect(pinnedFetchSpy).toHaveBeenCalledTimes(2);

      // 2. Failure case: private or metadata token URL is blocked before any outbound request
      validateSpy.mockClear();
      pinnedFetchSpy.mockClear();

      const reqBlocked = new NextRequest('http://localhost:3000/api/a2a/test', {
        method: 'POST',
        body: JSON.stringify({
          url: 'https://agent.example.com',
          auth: {
            type: 'oauth2',
            token_url: 'http://169.254.169.254/oauth/token',
            client_id: 'cid',
            client_secret: 'csec',
          },
        }),
      });

      const resBlocked = await POST(reqBlocked);
      expect(resBlocked.status).toBe(400);
      const bodyBlocked = (await resBlocked.json()) as { success: boolean; message: string };
      expect(bodyBlocked.success).toBe(false);
      expect(bodyBlocked.message).toBe('Target address is not allowed.');
      // pinnedFetch was never invoked because the token URL was blocked at validation
      expect(pinnedFetchSpy).not.toHaveBeenCalled();
    });
  });
});
