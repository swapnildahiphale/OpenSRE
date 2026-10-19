import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { LookupAddress } from 'node:dns';
import * as undici from 'undici';
import {
  parseIPv4,
  parseIPv6,
  isCloudMetadata,
  isDisallowedIP,
  validateTargetUrl,
  createPinnedLookup,
  pinnedFetch,
} from './ssrfGuard';

describe('SSRF Guard Module', () => {
  describe('IP parser and cloud metadata checks', () => {
    it('parses valid IPv4 and rejects octal / invalid octets', () => {
      expect(parseIPv4('127.0.0.1')).toEqual([127, 0, 0, 1]);
      expect(parseIPv4('192.168.1.50')).toEqual([192, 168, 1, 50]);
      expect(parseIPv4('0177.0.0.1')).toBeNull(); // Reject octal
      expect(parseIPv4('256.0.0.1')).toBeNull();
      expect(parseIPv4('1.2.3')).toBeNull();
      expect(parseIPv4('1.2.3.4.5')).toBeNull();
      expect(parseIPv4('abc.def.ghi.jkl')).toBeNull();
    });

    it('parses IPv6 addresses including compressed and dotted-quad forms', () => {
      expect(parseIPv6('::1')).toEqual([0, 0, 0, 0, 0, 0, 0, 1]);
      expect(parseIPv6('::')).toEqual([0, 0, 0, 0, 0, 0, 0, 0]);
      expect(parseIPv6('::127.0.0.1')).toEqual([0, 0, 0, 0, 0, 0, 0x7f00, 1]);
      expect(parseIPv6('::ffff:127.0.0.1')).toEqual([0, 0, 0, 0, 0, 0xffff, 0x7f00, 1]);
      expect(parseIPv6('64:ff9b::127.0.0.1')).toEqual([0x0064, 0xff9b, 0, 0, 0, 0, 0x7f00, 1]);
      expect(parseIPv6('fe80::1')).toEqual([0xfe80, 0, 0, 0, 0, 0, 0, 1]);
    });

    it('detects cloud metadata addresses across IPv4, IPv6, mapped, and compatible forms', () => {
      expect(isCloudMetadata('169.254.169.254')).toBe(true);
      expect(isCloudMetadata('169.254.170.2')).toBe(true);
      expect(isCloudMetadata('100.100.100.200')).toBe(true);
      expect(isCloudMetadata('::169.254.169.254')).toBe(true);
      expect(isCloudMetadata('::ffff:169.254.169.254')).toBe(true);
      expect(isCloudMetadata('64:ff9b::169.254.169.254')).toBe(true);
      expect(isCloudMetadata('fd00:ec2::254')).toBe(true);
      expect(isCloudMetadata('93.184.216.34')).toBe(false);
      expect(isCloudMetadata('8.8.8.8')).toBe(false);
      expect(isCloudMetadata('::127.0.0.1')).toBe(false);
    });
  });

  describe('isDisallowedIP', () => {
    it('blocks loopback addresses by default', () => {
      expect(isDisallowedIP('127.0.0.1')).toBe(true);
      expect(isDisallowedIP('127.1.2.3')).toBe(true);
      expect(isDisallowedIP('::1')).toBe(true);
      expect(isDisallowedIP('::ffff:127.0.0.1')).toBe(true);
      expect(isDisallowedIP('::127.0.0.1')).toBe(true);
    });

    it('blocks RFC 1918 private IPv4 ranges by default', () => {
      expect(isDisallowedIP('10.0.0.1')).toBe(true);
      expect(isDisallowedIP('10.254.1.1')).toBe(true);
      expect(isDisallowedIP('172.16.0.1')).toBe(true);
      expect(isDisallowedIP('172.31.255.255')).toBe(true);
      expect(isDisallowedIP('192.168.1.1')).toBe(true);
      expect(isDisallowedIP('::ffff:10.0.0.1')).toBe(true);
      expect(isDisallowedIP('::ffff:192.168.1.1')).toBe(true);
    });

    it('blocks IPv4-compatible IPv6 addresses (::a.b.c.d) by default', () => {
      expect(isDisallowedIP('::127.0.0.1')).toBe(true);
      expect(isDisallowedIP('::10.0.0.1')).toBe(true);
      expect(isDisallowedIP('::192.168.1.1')).toBe(true);
      expect(isDisallowedIP('::169.254.169.254')).toBe(true);
    });

    it('allows public IPv4-compatible IPv6 addresses', () => {
      expect(isDisallowedIP('::93.184.216.34')).toBe(false);
      expect(isDisallowedIP('::8.8.8.8')).toBe(false);
    });

    it('blocks link-local, multicast, and unspecified addresses', () => {
      expect(isDisallowedIP('0.0.0.0')).toBe(true);
      expect(isDisallowedIP('::')).toBe(true);
      expect(isDisallowedIP('169.254.1.1')).toBe(true);
      expect(isDisallowedIP('fe80::1')).toBe(true);
      expect(isDisallowedIP('224.0.0.1')).toBe(true);
      expect(isDisallowedIP('ff02::1')).toBe(true);
      expect(isDisallowedIP('255.255.255.255')).toBe(true);
    });

    it('allows public IP addresses', () => {
      expect(isDisallowedIP('93.184.216.34')).toBe(false);
      expect(isDisallowedIP('8.8.8.8')).toBe(false);
      expect(isDisallowedIP('1.1.1.1')).toBe(false);
      expect(isDisallowedIP('2606:4700:4700::1111')).toBe(false);
    });

    it('allows private and loopback when allowPrivate=true, but STILL BLOCKS metadata', () => {
      expect(isDisallowedIP('127.0.0.1', true)).toBe(false);
      expect(isDisallowedIP('::1', true)).toBe(false);
      expect(isDisallowedIP('10.0.0.1', true)).toBe(false);
      expect(isDisallowedIP('192.168.1.1', true)).toBe(false);
      expect(isDisallowedIP('::ffff:127.0.0.1', true)).toBe(false);
      expect(isDisallowedIP('::127.0.0.1', true)).toBe(false);
      expect(isDisallowedIP('::10.0.0.1', true)).toBe(false);
      expect(isDisallowedIP('::192.168.1.1', true)).toBe(false);

      // Cloud metadata MUST STILL BE BLOCKED even with allowPrivate=true
      expect(isDisallowedIP('169.254.169.254', true)).toBe(true);
      expect(isDisallowedIP('::ffff:169.254.169.254', true)).toBe(true);
      expect(isDisallowedIP('::169.254.169.254', true)).toBe(true);
      expect(isDisallowedIP('64:ff9b::169.254.169.254', true)).toBe(true);
      expect(isDisallowedIP('100.100.100.200', true)).toBe(true);
      expect(isDisallowedIP('fd00:ec2::254', true)).toBe(true);
    });
  });

  describe('validateTargetUrl', () => {
    beforeEach(() => {
      delete process.env.ALLOW_PRIVATE_A2A_CONNECTIONS;
    });

    afterEach(() => {
      delete process.env.ALLOW_PRIVATE_A2A_CONNECTIONS;
    });

    it('rejects URLs with credentials', async () => {
      const res = await validateTargetUrl('http://admin:secret@example.com/agent');
      expect(res.allowed).toBe(false);
      expect(res.error).toBe('Target address is not allowed.');
    });

    it('rejects non-HTTP/HTTPS schemes', async () => {
      const resFtp = await validateTargetUrl('ftp://example.com/agent');
      expect(resFtp.allowed).toBe(false);

      const resFile = await validateTargetUrl('file:///etc/passwd');
      expect(resFile.allowed).toBe(false);
    });

    it('rejects loopback and private IP literals by default including IPv4-compatible', async () => {
      expect((await validateTargetUrl('http://127.0.0.1:8000/agent')).allowed).toBe(false);
      expect((await validateTargetUrl('http://[::1]:8000/agent')).allowed).toBe(false);
      expect((await validateTargetUrl('http://[::127.0.0.1]:8000/agent')).allowed).toBe(false);
      expect((await validateTargetUrl('http://[::10.0.0.1]:8000/agent')).allowed).toBe(false);
      expect((await validateTargetUrl('http://[::192.168.1.1]:8000/agent')).allowed).toBe(false);
      expect((await validateTargetUrl('http://[::169.254.169.254]:8000/agent')).allowed).toBe(false);
      expect((await validateTargetUrl('http://10.0.0.5:8000/agent')).allowed).toBe(false);
      expect((await validateTargetUrl('http://192.168.1.10:8000/agent')).allowed).toBe(false);
      expect((await validateTargetUrl('http://169.254.169.254/latest/meta-data')).allowed).toBe(false);
    });

    it('returns hostname and validatedAddresses for allowed targets', async () => {
      const mockLookup = vi.fn().mockResolvedValue([
        { address: '93.184.216.34', family: 4 },
      ]);

      const res = await validateTargetUrl('https://agent.example.com/rpc', {
        dnsLookup: mockLookup,
      });

      expect(res.allowed).toBe(true);
      expect(res.hostname).toBe('agent.example.com');
      expect(res.validatedAddresses).toEqual([{ address: '93.184.216.34', family: 4 }]);
    });

    it('resolves hostname and rejects if it resolves to private IP', async () => {
      const mockLookup = vi.fn().mockResolvedValue([
        { address: '192.168.1.100', family: 4 },
      ]);

      const res = await validateTargetUrl('https://internal.corp/agent', {
        dnsLookup: mockLookup,
      });

      expect(res.allowed).toBe(false);
      expect(res.error).toBe('Target address is not allowed.');
      expect(mockLookup).toHaveBeenCalledWith('internal.corp');
    });

    it('rejects if ANY resolved address is disallowed (dual-stack / round-robin)', async () => {
      const mockLookup = vi.fn().mockResolvedValue([
        { address: '93.184.216.34', family: 4 },
        { address: '127.0.0.1', family: 4 }, // Disallowed
      ]);

      const res = await validateTargetUrl('https://dual.example.com/agent', {
        dnsLookup: mockLookup,
      });

      expect(res.allowed).toBe(false);
      expect(res.error).toBe('Target address is not allowed.');
    });

    it('respects ALLOW_PRIVATE_A2A_CONNECTIONS=true but still blocks metadata', async () => {
      process.env.ALLOW_PRIVATE_A2A_CONNECTIONS = 'true';

      const mockLookupPrivate = vi.fn().mockResolvedValue([
        { address: '127.0.0.1', family: 4 },
      ]);
      const resPrivate = await validateTargetUrl('http://localhost:8000/agent', {
        dnsLookup: mockLookupPrivate,
      });
      expect(resPrivate.allowed).toBe(true);

      const mockLookupMetadata = vi.fn().mockResolvedValue([
        { address: '169.254.169.254', family: 4 },
      ]);
      const resMetadata = await validateTargetUrl('http://metadata.google.internal/computeMetadata', {
        dnsLookup: mockLookupMetadata,
      });
      expect(resMetadata.allowed).toBe(false);
      expect(resMetadata.error).toBe('Target address is not allowed.');
    });
  });

  describe('DNS Rebinding & Pinned Transport', () => {
    it('createPinnedLookup returns validated addresses without calling OS resolver', () => {
      const validated: LookupAddress[] = [{ address: '93.184.216.34', family: 4 }];
      const lookup = createPinnedLookup(validated);

      // Call shape 1: with { all: true }
      let resultAll: LookupAddress[] | null = null;
      lookup('rebind.example.com', { all: true }, (err: NodeJS.ErrnoException | null, addresses: LookupAddress[]) => {
        expect(err).toBeNull();
        resultAll = addresses;
      });
      expect(resultAll).toEqual(validated);

      // Call shape 2: without all: true
      let resultSingle: LookupAddress | null = null;
      lookup('rebind.example.com', {}, (err: NodeJS.ErrnoException | null, address: string, family: number) => {
        expect(err).toBeNull();
        resultSingle = { address, family };
      });
      expect(resultSingle).toEqual({ address: '93.184.216.34', family: 4 });
    });

    it('prevents DNS rebinding: OS resolver is called once; pinned lookup ignores subsequent DNS changes', async () => {
      let callCount = 0;
      // First call returns public IP; hostile second call returns loopback 127.0.0.1
      const mockDnsLookup = vi.fn().mockImplementation(async () => {
        callCount++;
        if (callCount === 1) {
          return [{ address: '93.184.216.34', family: 4 }];
        }
        return [{ address: '127.0.0.1', family: 4 }];
      });

      const validation = await validateTargetUrl('https://hostile-rebinding.example.com/agent', {
        dnsLookup: mockDnsLookup,
      });

      expect(validation.allowed).toBe(true);
      expect(mockDnsLookup).toHaveBeenCalledTimes(1);

      // Now create pinned lookup using validation.validatedAddresses
      const pinnedLookup = createPinnedLookup(validation.validatedAddresses!);

      // Any subsequent lookup invoked by the transport layer only returns the pre-validated address
      let returnedAddresses: LookupAddress[] | null = null;
      pinnedLookup(
        'hostile-rebinding.example.com',
        { all: true },
        (_err: NodeJS.ErrnoException | null, addresses: LookupAddress[]) => {
          returnedAddresses = addresses;
        }
      );

      expect(returnedAddresses).toEqual([{ address: '93.184.216.34', family: 4 }]);
      // The OS resolver was NOT called again!
      expect(mockDnsLookup).toHaveBeenCalledTimes(1);
    });

    it('pinnedFetch executes with undici Agent dispatcher and original hostname URL', async () => {
      let capturedUrl = '';
      let capturedDispatcher: unknown = null;
      let capturedMethod = '';
      let capturedRedirect = '';

      const mockUndiciFetch = vi.fn().mockImplementation(async (url: string | URL, opts?: { method?: string; dispatcher?: unknown; redirect?: string }) => {
        capturedUrl = String(url);
        capturedDispatcher = opts?.dispatcher;
        capturedMethod = opts?.method || '';
        capturedRedirect = opts?.redirect || '';
        return new Response(JSON.stringify({ status: 'ok' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      });

      const validatedAddresses: LookupAddress[] = [{ address: '93.184.216.34', family: 4 }];
      const res = await pinnedFetch({
        url: 'https://agent.example.com/rpc',
        method: 'POST',
        headers: { 'X-Custom': 'test' },
        body: JSON.stringify({ hello: 'world' }),
        timeoutSeconds: 5,
        validatedAddresses,
        fetchFn: mockUndiciFetch as unknown as typeof undici.fetch,
      });

      expect(res.status).toBe(200);
      // Original hostname URL preserved (no IP substituted)
      expect(capturedUrl).toBe('https://agent.example.com/rpc');
      expect(capturedMethod).toBe('POST');
      expect(capturedRedirect).toBe('manual');
      // Dispatcher is an undici Agent
      expect(capturedDispatcher).toBeInstanceOf(undici.Agent);
    });
  });
});
