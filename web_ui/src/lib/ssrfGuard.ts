import dns from 'node:dns/promises';
import type { LookupOptions, LookupAddress } from 'node:dns';
import net from 'node:net';
import { Agent, fetch as undiciFetch } from 'undici';

/**
 * SSRF Protection Module for OpenSRE (Issue #19)
 *
 * Implements defenses against Server-Side Request Forgery & DNS Rebinding:
 * - Restricts protocols to HTTP and HTTPS only.
 * - Rejects URLs with embedded credentials (username/password).
 * - Blocks loopback, unspecified, link-local, multicast, CGNAT, and private network ranges
 *   for both IPv4 and IPv6 (including IPv4-compatible ::a.b.c.d, IPv4-mapped ::ffff:a.b.c.d,
 *   and NAT64 64:ff9b::a.b.c.d addresses).
 * - Always blocks cloud metadata addresses (e.g. 169.254.169.254, AWS, GCP, Alibaba, etc.),
 *   even when private connections are opted into.
 * - Resolves hostnames before fetching; rejects if ANY resolved address is disallowed.
 * - Pins validated IP addresses using an undici Agent with a custom connect.lookup to
 *   prevent DNS rebinding (TOCTOU) attacks while preserving hostname-based TLS SNI and cert checks.
 *
 * Opt-in:
 * Environment variable `ALLOW_PRIVATE_A2A_CONNECTIONS=true` permits private and loopback
 * network targets (e.g. local agents in development/on-prem setups).
 * Default is off (false).
 * Cloud metadata addresses remain strictly blocked even when this opt-in is active.
 */

export interface SSRFValidationResult {
  allowed: boolean;
  error?: string;
  hostname?: string;
  validatedAddresses?: LookupAddress[];
}

export interface SSRFValidationOptions {
  allowPrivate?: boolean;
  dnsLookup?: (hostname: string) => Promise<LookupAddress[]>;
}

export interface PinnedFetchOptions {
  url: string | URL;
  method?: string;
  headers?: Record<string, string>;
  body?: string | URLSearchParams;
  timeoutSeconds: number;
  validatedAddresses: LookupAddress[];
  redirect?: 'manual' | 'error' | 'follow';
  fetchFn?: typeof undiciFetch;
}

export type PinnedLookupCallback =
  | ((err: NodeJS.ErrnoException | null, address: string, family: number) => void)
  | ((err: NodeJS.ErrnoException | null, addresses: LookupAddress[]) => void);

/**
 * Check if the opt-in flag is enabled in the current environment.
 */
export function isPrivateConnectionAllowed(): boolean {
  return process.env.ALLOW_PRIVATE_A2A_CONNECTIONS === 'true';
}

/**
 * Parse an IPv4 string into 4 numeric octets.
 * Rejects leading zeros (octal notation) and non-numeric characters to prevent bypasses.
 */
export function parseIPv4(ip: string): [number, number, number, number] | null {
  const parts = ip.split('.');
  if (parts.length !== 4) return null;

  const octets: number[] = [];
  for (const part of parts) {
    if (!/^\d+$/.test(part)) return null;
    if (part.length > 1 && part.startsWith('0')) {
      // Reject octal notation like 0177.0.0.1
      return null;
    }
    const num = Number(part);
    if (num < 0 || num > 255) return null;
    octets.push(num);
  }

  return [octets[0], octets[1], octets[2], octets[3]];
}

/**
 * Parse and expand an IPv6 address into eight 16-bit integers (16 bytes).
 * Correctly handles '::' zero-compression and dotted-quad forms (e.g. ::127.0.0.1, ::ffff:192.168.1.1).
 */
export function parseIPv6(ip: string): number[] | null {
  // Strip zone index if present (e.g. fe80::1%eth0)
  const zoneIndex = ip.indexOf('%');
  const cleanIp = zoneIndex !== -1 ? ip.slice(0, zoneIndex) : ip;

  // Check for embedded IPv4 at the end
  const lastColon = cleanIp.lastIndexOf(':');
  if (lastColon === -1) return null;

  const afterLastColon = cleanIp.slice(lastColon + 1);
  let ipv4Words: number[] | null = null;
  let ipv6Part = cleanIp;

  if (afterLastColon.includes('.')) {
    const octets = parseIPv4(afterLastColon);
    if (!octets) return null;
    ipv4Words = [
      (octets[0] << 8) | octets[1],
      (octets[2] << 8) | octets[3],
    ];
    // If the prefix ends in '::', e.g. ::127.0.0.1 or 64:ff9b::127.0.0.1
    ipv6Part = cleanIp[lastColon - 1] === ':' ? cleanIp.slice(0, lastColon + 1) : cleanIp.slice(0, lastColon);
  }

  const parts = ipv6Part.split('::');
  if (parts.length > 2) return null;

  const parseHexWords = (s: string): number[] => {
    if (!s) return [];
    return s.split(':').map((hex) => {
      if (!/^[0-9a-fA-F]{1,4}$/.test(hex)) return NaN;
      return parseInt(hex, 16);
    });
  };

  const leftWords = parseHexWords(parts[0]);
  if (leftWords.some(isNaN)) return null;

  const rightWords = parts.length === 2 ? parseHexWords(parts[1]) : [];
  if (rightWords.some(isNaN)) return null;

  const neededWords = 8 - (ipv4Words ? 2 : 0);
  if (parts.length === 1) {
    if (leftWords.length + (ipv4Words ? 2 : 0) !== 8) return null;
    return [...leftWords, ...(ipv4Words || [])];
  }

  const fillCount = neededWords - (leftWords.length + rightWords.length);
  if (fillCount < 0) return null;

  const fill = new Array(fillCount).fill(0);
  return [...leftWords, ...fill, ...rightWords, ...(ipv4Words || [])];
}

/**
 * Extract embedded IPv4 octets from IPv4-compatible (first 96 bits zero),
 * IPv4-mapped (::ffff:0:0/96), or NAT64 (64:ff9b::/96) IPv6 addresses.
 */
function extractEmbeddedIPv4(words: number[]): [number, number, number, number] | null {
  const isFirst96Zero = words.slice(0, 6).every((w) => w === 0);
  const isNotLoopbackOrUnspecified = !(words[6] === 0 && (words[7] === 0 || words[7] === 1));
  const isMapped = words.slice(0, 5).every((w) => w === 0) && words[5] === 0xffff;
  const isNat64 = words[0] === 0x0064 && words[1] === 0xff9b && words.slice(2, 6).every((w) => w === 0);

  if ((isFirst96Zero && isNotLoopbackOrUnspecified) || isMapped || isNat64) {
    return [
      (words[6] >> 8) & 0xff,
      words[6] & 0xff,
      (words[7] >> 8) & 0xff,
      words[7] & 0xff,
    ];
  }

  return null;
}

/**
 * Check if an IP address is a cloud metadata address.
 * Always blocked, regardless of ALLOW_PRIVATE_A2A_CONNECTIONS.
 */
export function isCloudMetadata(ip: string): boolean {
  // IPv4 check
  const octets = parseIPv4(ip);
  if (octets) {
    // 169.254.169.254 (AWS, GCP, Azure, DigitalOcean, OpenStack)
    // 169.254.170.2 (AWS ECS metadata)
    // 169.254.169.253 (AWS DNS)
    // Any 169.254.0.0/16 link-local metadata
    if (octets[0] === 169 && octets[1] === 254) {
      return true;
    }
    // Alibaba Cloud metadata: 100.100.100.200
    if (octets[0] === 100 && octets[1] === 100 && octets[2] === 100 && octets[3] === 200) {
      return true;
    }
    return false;
  }

  // IPv6 check
  const words = parseIPv6(ip);
  if (words) {
    const embedded = extractEmbeddedIPv4(words);
    if (embedded) {
      const embeddedIp = `${embedded[0]}.${embedded[1]}.${embedded[2]}.${embedded[3]}`;
      return isCloudMetadata(embeddedIp);
    }
    // AWS EC2 IPv6 metadata: fd00:ec2::254
    if (
      words[0] === 0xfd00 &&
      words[1] === 0x0ec2 &&
      words[2] === 0 &&
      words[3] === 0 &&
      words[4] === 0 &&
      words[5] === 0 &&
      words[6] === 0 &&
      words[7] === 0x0254
    ) {
      return true;
    }
  }

  return false;
}

/**
 * Check if an IPv4 address is disallowed according to SSRF rules.
 */
function isDisallowedIPv4(octets: [number, number, number, number], allowPrivate: boolean): boolean {
  const [a, b, c] = octets;

  // Cloud metadata is unconditionally blocked
  if (a === 169 && b === 254) return true; // Link-local / metadata
  if (a === 100 && b === 100 && c === 100 && octets[3] === 200) return true; // Alibaba metadata

  // Unspecified / current network (0.0.0.0/8)
  if (a === 0) return true;

  // Multicast (224.0.0.0/4)
  if (a >= 224 && a <= 239) return true;

  // Reserved / broadcast (240.0.0.0/4, includes 255.255.255.255)
  if (a >= 240) return true;

  // Loopback (127.0.0.0/8)
  if (a === 127) {
    return !allowPrivate;
  }

  // Private network ranges (RFC 1918)
  // 10.0.0.0/8
  if (a === 10) {
    return !allowPrivate;
  }
  // 172.16.0.0/12
  if (a === 172 && b >= 16 && b <= 31) {
    return !allowPrivate;
  }
  // 192.168.0.0/16
  if (a === 192 && b === 168) {
    return !allowPrivate;
  }

  // Carrier-grade NAT (100.64.0.0/10: 100.64.0.0 - 100.127.255.255)
  if (a === 100 && b >= 64 && b <= 127) {
    return !allowPrivate;
  }

  return false;
}

/**
 * Check if an IPv6 address is disallowed according to SSRF rules.
 */
function isDisallowedIPv6(words: number[], allowPrivate: boolean): boolean {
  // 1. Unspecified (::) is unconditionally blocked
  if (words.every((w) => w === 0)) return true;

  // 2. Loopback (::1)
  if (
    words[0] === 0 &&
    words[1] === 0 &&
    words[2] === 0 &&
    words[3] === 0 &&
    words[4] === 0 &&
    words[5] === 0 &&
    words[6] === 0 &&
    words[7] === 1
  ) {
    return !allowPrivate;
  }

  // 3. IPv4-compatible (first 96 bits zero), IPv4-mapped (::ffff:0:0/96), or NAT64 (64:ff9b::/96)
  const embedded = extractEmbeddedIPv4(words);
  if (embedded) {
    return isDisallowedIPv4(embedded, allowPrivate);
  }

  // 4. Cloud metadata: AWS EC2 IPv6 metadata: fd00:ec2::254
  if (
    words[0] === 0xfd00 &&
    words[1] === 0x0ec2 &&
    words[2] === 0 &&
    words[3] === 0 &&
    words[4] === 0 &&
    words[5] === 0 &&
    words[6] === 0 &&
    words[7] === 0x0254
  ) {
    return true;
  }

  // 5. Multicast (ff00::/8)
  if ((words[0] & 0xff00) === 0xff00) return true;

  // 6. Link-local unicast (fe80::/10: fe80:: - febf::)
  if ((words[0] & 0xffc0) === 0xfe80) return true;

  // 7. Unique local addresses (ULA) / Private IPv6 (fc00::/7: fc00:: - fdff::)
  if ((words[0] & 0xfe00) === 0xfc00) {
    return !allowPrivate;
  }

  // 8. Discard prefix (100::/64)
  if (words[0] === 0x0100 && words[1] === 0 && words[2] === 0 && words[3] === 0) {
    return true;
  }

  return false;
}

/**
 * Validate a single IP string (IPv4 or IPv6) against SSRF restrictions.
 */
export function isDisallowedIP(ip: string, allowPrivate = false): boolean {
  const octets = parseIPv4(ip);
  if (octets) {
    return isDisallowedIPv4(octets, allowPrivate);
  }

  const words = parseIPv6(ip);
  if (words) {
    return isDisallowedIPv6(words, allowPrivate);
  }

  // If it's not a valid IP, treat as disallowed for safety
  return true;
}

/**
 * Validate a target URL for SSRF vulnerabilities.
 * Checks protocol, credentials, IP literals, and resolves hostnames to verify all IP addresses.
 * Returns validation data including hostname and validated addresses for the transport layer.
 */
export async function validateTargetUrl(
  urlString: string,
  options?: SSRFValidationOptions
): Promise<SSRFValidationResult> {
  const allowPrivate = options?.allowPrivate ?? isPrivateConnectionAllowed();

  if (!urlString || typeof urlString !== 'string' || !urlString.trim()) {
    return { allowed: false, error: 'URL is required' };
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(urlString.trim());
  } catch {
    return { allowed: false, error: 'Target address is not allowed.' };
  }

  // Only allow http and https protocols
  if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
    return { allowed: false, error: 'Target address is not allowed.' };
  }

  // Reject URLs containing credentials (username or password)
  if (parsedUrl.username || parsedUrl.password) {
    return { allowed: false, error: 'Target address is not allowed.' };
  }

  // Clean hostname (strip IPv6 brackets if present, e.g. [::1])
  const hostname = parsedUrl.hostname.trim();
  const cleanHost = hostname.replace(/^\[|\]$/g, '');

  if (!cleanHost) {
    return { allowed: false, error: 'Target address is not allowed.' };
  }

  // Check if hostname is an IP literal
  const ipFamily = net.isIP(cleanHost);
  if (ipFamily !== 0) {
    if (isDisallowedIP(cleanHost, allowPrivate)) {
      return { allowed: false, error: 'Target address is not allowed.' };
    }
    return {
      allowed: true,
      hostname: cleanHost,
      validatedAddresses: [{ address: cleanHost, family: ipFamily }],
    };
  }

  // Hostname must be resolved via DNS
  const defaultLookup = async (host: string) => {
    return await dns.lookup(host, { all: true });
  };
  const lookupFn = options?.dnsLookup || defaultLookup;

  let resolved: LookupAddress[];
  try {
    resolved = await lookupFn(cleanHost);
  } catch {
    return { allowed: false, error: 'Target address is not allowed.' };
  }

  if (!resolved || resolved.length === 0) {
    return { allowed: false, error: 'Target address is not allowed.' };
  }

  // Reject if ANY resolved address is disallowed
  for (const entry of resolved) {
    if (isDisallowedIP(entry.address, allowPrivate)) {
      return { allowed: false, error: 'Target address is not allowed.' };
    }
  }

  return {
    allowed: true,
    hostname: cleanHost,
    validatedAddresses: resolved,
  };
}

/**
 * Creates a custom DNS lookup function for undici.Agent connect.lookup that
 * only returns the pre-validated IP addresses and never calls the OS resolver.
 *
 * Security Guarantee:
 * By keeping the original hostname in the URL while overriding address resolution
 * in connect.lookup, HTTPS hostname/SNI and certificate validation are strictly
 * preserved against the host while IP address selection is securely pinned,
 * eliminating DNS rebinding (TOCTOU) vulnerabilities.
 */
export function createPinnedLookup(
  validatedAddresses: LookupAddress[]
) {
  return function pinnedLookup(
    _hostname: string,
    options: LookupOptions | PinnedLookupCallback | null | undefined,
    callback?: PinnedLookupCallback
  ): void {
    const cb = typeof callback === 'function' ? callback : typeof options === 'function' ? options : null;
    const opts = typeof options === 'object' && options !== null ? options : {};

    if (!cb) return;

    if (opts.all) {
      (cb as (err: NodeJS.ErrnoException | null, addresses: LookupAddress[]) => void)(null, validatedAddresses);
    } else {
      const first = validatedAddresses[0];
      (cb as (err: NodeJS.ErrnoException | null, address: string, family: number) => void)(
        null,
        first ? first.address : '',
        first ? first.family : 4
      );
    }
  };
}

// Configurable transport fetch implementation (defaults to undici.fetch)
export let pinnedFetchImplementation: typeof undiciFetch = undiciFetch;

export function setPinnedFetchImplementation(fn: typeof undiciFetch): void {
  pinnedFetchImplementation = fn;
}

export function resetPinnedFetchImplementation(): void {
  pinnedFetchImplementation = undiciFetch;
}

/**
 * Single shared transport helper used for all outbound A2A probe and OAuth2 token requests.
 * Connects exclusively to the pre-validated addresses via undici Agent with custom lookup,
 * preventing DNS rebinding (TOCTOU) while preserving hostname-based TLS SNI and cert verification.
 */
export async function pinnedFetch(options: PinnedFetchOptions): Promise<Response> {
  const agent = new Agent({
    connect: {
      lookup: createPinnedLookup(options.validatedAddresses),
    },
  });

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeoutSeconds * 1000);

  const fetchImpl = options.fetchFn || pinnedFetchImplementation;

  try {
    const rawRes = await fetchImpl(options.url.toString(), {
      method: options.method || 'GET',
      headers: options.headers,
      body: options.body,
      dispatcher: agent,
      signal: controller.signal,
      redirect: options.redirect || 'manual',
    });

    // Fully read body inside timeout scope before agent cleanup
    const bodyText = await rawRes.text();
    return new Response(bodyText, {
      status: rawRes.status,
      statusText: rawRes.statusText,
      headers: rawRes.headers as unknown as HeadersInit,
    });
  } finally {
    clearTimeout(timeoutId);
    await agent.close().catch(() => agent.destroy());
  }
}
