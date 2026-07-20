export interface ThreadEpisode {
  correlation_id: string;
  summary?: string | null;
  issue_description?: string | null;
  issue_type?: string | null;
  services?: string[];
  resolved?: boolean;
}

export interface ThreadRunSlice {
  status: 'running' | 'completed' | 'failed' | 'timeout' | 'interrupted';
  triggerMessage?: string | null;
  outputJson?: Record<string, unknown> | null;
  errorMessage?: string | null;
}

const MAX_LEN = 120;

function truncate(text: string, max = MAX_LEN): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

function rootCauseFromJson(outputJson?: Record<string, unknown> | null): string | null {
  const rc = outputJson?.root_cause;
  return typeof rc === 'string' && rc.trim() ? rc.trim() : null;
}

export function pickThreadSummary(
  episode: ThreadEpisode | undefined,
  latestRun: ThreadRunSlice,
  firstRun: ThreadRunSlice,
): string {
  if (episode?.summary?.trim()) return truncate(episode.summary);
  if (episode?.issue_description?.trim()) return truncate(episode.issue_description);

  const rootCause = rootCauseFromJson(latestRun.outputJson);
  if (rootCause) return truncate(rootCause);

  if (
    (latestRun.status === 'failed' || latestRun.status === 'timeout') &&
    latestRun.errorMessage?.trim()
  ) {
    return truncate(latestRun.errorMessage);
  }

  if (firstRun.triggerMessage?.trim()) return truncate(firstRun.triggerMessage);

  if (latestRun.status === 'running') return 'Investigation in progress…';

  return 'Investigation';
}

export function buildEpisodeMap(
  episodes: ThreadEpisode[],
): Map<string, ThreadEpisode> {
  const map = new Map<string, ThreadEpisode>();
  for (const ep of episodes) {
    if (ep.correlation_id) map.set(ep.correlation_id, ep);
  }
  return map;
}
