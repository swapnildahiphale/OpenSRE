import { describe, expect, it } from 'vitest';
import { resolvePublicOrigin, resolveSsoOrgId, safeReturnTo, sanitizeOrgId } from './ssoLoginOrg';

describe('resolveSsoOrgId', () => {
  it('uses WEB_UI_SSO_ORG_ID', () => {
    expect(resolveSsoOrgId({ WEB_UI_SSO_ORG_ID: 'acme' })).toBe('acme');
  });

  it('returns empty when unset so SSO stays off', () => {
    expect(resolveSsoOrgId({})).toBe('');
  });
});

describe('sanitizeOrgId', () => {
  it('strips path-traversal characters', () => {
    expect(sanitizeOrgId('../acme')).toBe('acme');
  });
});

describe('safeReturnTo', () => {
  it('allows /team', () => {
    expect(safeReturnTo('/team')).toBe('/team');
  });

  it('rejects open redirects and HTML', () => {
    expect(safeReturnTo('https://evil.example')).toBe('/team');
    expect(safeReturnTo('//evil.example')).toBe('/team');
    expect(safeReturnTo('/team"><script>')).toBe('/team');
  });
});

function fakeRequest(headers: Record<string, string>, origin = 'http://0.0.0.0:3000') {
  return {
    headers: { get: (name: string) => headers[name] ?? null },
    nextUrl: { protocol: 'http:', origin },
  };
}

describe('resolvePublicOrigin', () => {
  it('prefers WEB_UI_PUBLIC_BASE_URL', () => {
    expect(
      resolvePublicOrigin(fakeRequest({ host: 'localhost:3002' }), {
        WEB_UI_PUBLIC_BASE_URL: 'https://opensre.example.com/',
      }),
    ).toBe('https://opensre.example.com');
  });

  it('uses Host instead of 0.0.0.0 bind address', () => {
    expect(
      resolvePublicOrigin(
        fakeRequest({ host: 'localhost:3002' }, 'http://0.0.0.0:3000'),
        {},
      ),
    ).toBe('http://localhost:3002');
  });
});
