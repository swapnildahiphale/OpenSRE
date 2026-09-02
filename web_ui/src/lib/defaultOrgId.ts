/** Default org for local/self-hosted when identity has no org claim. */
export function defaultOrgId(): string {
  return (
    process.env.NEXT_PUBLIC_DEFAULT_ORG_ID?.trim() ||
    process.env.DEFAULT_ORG_ID?.trim() ||
    process.env.ORG_ID?.trim() ||
    "local"
  );
}
