import { describe, expect, it } from 'vitest';
import { buildCustomOidcAuthorizationUrl } from './oidcAuthorization';

describe('buildCustomOidcAuthorizationUrl', () => {
  const parameters = {
    client_id: 'opensre',
    redirect_uri: 'http://localhost:3002/api/auth/callback',
    response_type: 'code',
    scope: 'openid email profile',
    state: 'example-state+/=',
  };

  it('uses the advertised Casdoor-style path and preserves existing query parameters', () => {
    const url = new URL(buildCustomOidcAuthorizationUrl(
      'https://identity.example.com/login/oauth/authorize?tenant=demo&client_id=old',
      parameters,
    ));
    expect(url.pathname).toBe('/login/oauth/authorize');
    expect(url.searchParams.get('tenant')).toBe('demo');
    for (const [key, value] of Object.entries(parameters)) {
      expect(url.searchParams.getAll(key)).toEqual([value]);
    }
  });

  it.each([undefined, '/authorize', 'http://identity.example.com/authorize',
    'https://user@identity.example.com/authorize', 'https://identity.example.com/authorize#hash',
  ])('rejects an unusable endpoint (%s)', (endpoint) => {
    expect(() => buildCustomOidcAuthorizationUrl(endpoint, parameters)).toThrow();
  });
});
