import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { testA2AConnection } from './a2aClient';

describe('testA2AConnection client helper', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('validates URL locally before sending request', async () => {
    const fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy;

    const result = await testA2AConnection({ url: '' });
    expect(result.success).toBe(false);
    expect(result.message).toBe('URL is required');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('handles successful connection test', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          message: 'Connection successful. Remote A2A agent is reachable.',
          agentInfo: { name: 'RemoteBot' },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      )
    );

    const result = await testA2AConnection({
      url: 'https://agent.example.com',
      auth: { type: 'none' },
    });

    expect(result.success).toBe(true);
    expect(result.message).toBe('Connection successful. Remote A2A agent is reachable.');
    expect(result.agentInfo).toEqual({ name: 'RemoteBot' });
  });

  it('uses data.success and treats HTTP 200 failure as failure', async () => {
    // Crucial check: remote failed, API returns 200 with success: false
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: false,
          message: 'Agent error: Method not found',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      )
    );

    const result = await testA2AConnection({
      url: 'https://agent.example.com',
    });

    expect(result.success).toBe(false);
    expect(result.message).toBe('Agent error: Method not found');
  });

  it('handles timeout error response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: false,
          message: 'Connection timed out after 10s.',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      )
    );

    const result = await testA2AConnection({
      url: 'https://slow-agent.example.com',
    });

    expect(result.success).toBe(false);
    expect(result.message).toBe('Connection timed out after 10s.');
  });

  it('handles client network failure / fetch rejection', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Network request failed'));

    const result = await testA2AConnection({
      url: 'https://agent.example.com',
    });

    expect(result.success).toBe(false);
    expect(result.message).toBe('Network request failed');
  });

  it('handles malformed non-JSON response from server', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response('Bad Gateway', {
        status: 502,
        headers: { 'Content-Type': 'text/plain' },
      })
    );

    const result = await testA2AConnection({
      url: 'https://agent.example.com',
    });

    expect(result.success).toBe(false);
    expect(result.message).toBe('Endpoint responded, but did not identify itself as a supported A2A agent.');
  });
});
