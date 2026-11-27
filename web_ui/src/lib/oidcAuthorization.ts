/** Build the browser redirect from the provider's advertised endpoint. */
export function buildCustomOidcAuthorizationUrl(
  endpoint: string | undefined,
  parameters: Record<string, string>,
): string {
  if (!endpoint) throw new Error('Missing OIDC authorization endpoint');
  const url = new URL(endpoint);
  if (url.protocol !== 'https:' || url.username || url.password || url.hash) {
    throw new Error('Invalid OIDC authorization endpoint');
  }
  for (const [name, value] of Object.entries(parameters)) {
    url.searchParams.set(name, value);
  }
  return url.href;
}
