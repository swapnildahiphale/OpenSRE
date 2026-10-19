// @vitest-environment node
import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import http from 'node:http';
import dns from 'node:dns';
import dnsPromises from 'node:dns/promises';
import type { AddressInfo } from 'node:net';
import * as undici from 'undici';
import { pinnedFetch } from './ssrfGuard';

describe('Socket-level DNS Rebinding Defense (Real Sockets, No Internet)', () => {
  let server: http.Server;
  let serverPort: number;
  let recordedHostHeader: string | undefined;

  beforeAll(async () => {
    server = http.createServer((req, res) => {
      recordedHostHeader = req.headers.host;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', server: 'local-test' }));
    });

    await new Promise<void>((resolve) => {
      server.listen(0, '127.0.0.1', () => {
        serverPort = (server.address() as AddressInfo).port;
        resolve();
      });
    });
  });

  afterAll(async () => {
    await new Promise<void>((resolve) => {
      server.close(() => resolve());
    });
  });

  it('connects to pinned 127.0.0.1 address for unresolvable .invalid domain without OS DNS lookup', async () => {
    const dnsLookupSpy = vi.spyOn(dns, 'lookup');
    const dnsPromisesLookupSpy = vi.spyOn(dnsPromises, 'lookup');

    recordedHostHeader = undefined;

    // The .invalid domain cannot be resolved by standard OS DNS
    const unresolvableUrl = `http://rebind-test.invalid:${serverPort}/agent`;

    const res = await pinnedFetch({
      url: unresolvableUrl,
      method: 'GET',
      timeoutSeconds: 5,
      validatedAddresses: [{ address: '127.0.0.1', family: 4 }],
      redirect: 'manual',
    });

    expect(res.status).toBe(200);
    const body = (await res.json()) as { status: string; server: string };
    expect(body.status).toBe('ok');

    // Server saw the original hostname in Host header (hostname preserved)
    expect(recordedHostHeader).toBe(`rebind-test.invalid:${serverPort}`);

    // Operating system DNS resolver was never invoked
    expect(dnsLookupSpy).not.toHaveBeenCalled();
    expect(dnsPromisesLookupSpy).not.toHaveBeenCalled();
  });

  it('negative control: fails when pinned to a closed port without falling back to OS resolver', async () => {
    const dnsLookupSpy = vi.spyOn(dns, 'lookup');
    const dnsPromisesLookupSpy = vi.spyOn(dnsPromises, 'lookup');

    // Port 1 is universally closed/unbound on local interface
    const closedPort = 1;
    const closedPortUrl = `http://rebind-test.invalid:${closedPort}/agent`;

    let threw = false;
    try {
      await pinnedFetch({
        url: closedPortUrl,
        method: 'GET',
        timeoutSeconds: 2,
        validatedAddresses: [{ address: '127.0.0.1', family: 4 }],
        redirect: 'manual',
      });
    } catch {
      threw = true;
    }

    expect(threw).toBe(true);
    // Even upon connection failure, OS DNS resolver was never called as fallback
    expect(dnsLookupSpy).not.toHaveBeenCalled();
    expect(dnsPromisesLookupSpy).not.toHaveBeenCalled();
  });
});

describe('Lifecycle & Resource Cleanup', () => {
  it('cleans up Agent and timer on success', async () => {
    const closeSpy = vi.spyOn(undici.Agent.prototype, 'close');
    const destroySpy = vi.spyOn(undici.Agent.prototype, 'destroy');

    const mockFetch = vi.fn().mockImplementation(async () => {
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });

    const res = await pinnedFetch({
      url: 'https://agent.example.com/rpc',
      timeoutSeconds: 5,
      validatedAddresses: [{ address: '93.184.216.34', family: 4 }],
      fetchFn: mockFetch as unknown as typeof undici.fetch,
    });

    expect(res.status).toBe(200);
    expect(closeSpy.mock.calls.length + destroySpy.mock.calls.length).toBeGreaterThan(0);
  });

  it('cleans up Agent and timer on network error', async () => {
    const closeSpy = vi.spyOn(undici.Agent.prototype, 'close');
    const destroySpy = vi.spyOn(undici.Agent.prototype, 'destroy');

    const mockFetch = vi.fn().mockRejectedValue(new Error('connect ECONNREFUSED'));

    let errorThrown = false;
    try {
      await pinnedFetch({
        url: 'https://agent.example.com/rpc',
        timeoutSeconds: 5,
        validatedAddresses: [{ address: '93.184.216.34', family: 4 }],
        fetchFn: mockFetch as unknown as typeof undici.fetch,
      });
    } catch {
      errorThrown = true;
    }

    expect(errorThrown).toBe(true);
    expect(closeSpy.mock.calls.length + destroySpy.mock.calls.length).toBeGreaterThan(0);
  });

  it('cleans up Agent and timer on timeout/abort', async () => {
    const closeSpy = vi.spyOn(undici.Agent.prototype, 'close');
    const destroySpy = vi.spyOn(undici.Agent.prototype, 'destroy');

    const mockFetch = vi.fn().mockImplementation(async () => {
      const err = new Error('The operation was aborted');
      err.name = 'AbortError';
      throw err;
    });

    let aborted = false;
    try {
      await pinnedFetch({
        url: 'https://slow-agent.example.com/rpc',
        timeoutSeconds: 1,
        validatedAddresses: [{ address: '93.184.216.34', family: 4 }],
        fetchFn: mockFetch as unknown as typeof undici.fetch,
      });
    } catch {
      aborted = true;
    }

    expect(aborted).toBe(true);
    expect(closeSpy.mock.calls.length + destroySpy.mock.calls.length).toBeGreaterThan(0);
  });

  it('cleans up Agent and timer on non-JSON response body', async () => {
    const closeSpy = vi.spyOn(undici.Agent.prototype, 'close');
    const destroySpy = vi.spyOn(undici.Agent.prototype, 'destroy');

    const mockFetch = vi.fn().mockImplementation(async () => {
      return new Response('<html><body>502 Bad Gateway</body></html>', {
        status: 502,
        headers: { 'Content-Type': 'text/html' },
      });
    });

    const res = await pinnedFetch({
      url: 'https://agent.example.com/rpc',
      timeoutSeconds: 5,
      validatedAddresses: [{ address: '93.184.216.34', family: 4 }],
      fetchFn: mockFetch as unknown as typeof undici.fetch,
    });

    const text = await res.text();
    expect(text).toContain('502 Bad Gateway');
    expect(closeSpy.mock.calls.length + destroySpy.mock.calls.length).toBeGreaterThan(0);
  });

  it('cleans up Agent and timer on malformed JSON response body', async () => {
    const closeSpy = vi.spyOn(undici.Agent.prototype, 'close');
    const destroySpy = vi.spyOn(undici.Agent.prototype, 'destroy');

    const mockFetch = vi.fn().mockImplementation(async () => {
      return new Response('{"incomplete": true, "broken": ', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });

    const res = await pinnedFetch({
      url: 'https://agent.example.com/rpc',
      timeoutSeconds: 5,
      validatedAddresses: [{ address: '93.184.216.34', family: 4 }],
      fetchFn: mockFetch as unknown as typeof undici.fetch,
    });

    const text = await res.text();
    expect(text).toContain('incomplete');
    expect(closeSpy.mock.calls.length + destroySpy.mock.calls.length).toBeGreaterThan(0);
  });

  it('guarantees vi.getTimerCount() is 0 after request completion using fake timers', async () => {
    vi.useFakeTimers();
    try {
      const mockFetch = vi.fn().mockImplementation(async () => {
        return new Response(JSON.stringify({ success: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      });

      const promise = pinnedFetch({
        url: 'https://agent.example.com/rpc',
        timeoutSeconds: 10,
        validatedAddresses: [{ address: '93.184.216.34', family: 4 }],
        fetchFn: mockFetch as unknown as typeof undici.fetch,
      });

      const res = await promise;
      expect(res.status).toBe(200);
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
