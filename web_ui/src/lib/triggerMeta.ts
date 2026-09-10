/** Channel label, plus actor when the first run recorded one. */
export function formatTriggerMeta(
  source?: string | null,
  actor?: string | null,
): string {
  const channel = (source ?? 'web_ui').replace(/_/g, ' ');
  const name = actor?.trim();
  return name ? `${channel} · ${name}` : channel;
}
