import type { ThoughtItem } from './agentTimeline';

/** Latest thought is the last in seq order; earlier are everything before it. */
export function splitLatestThought(thoughts: ThoughtItem[]): {
  latest: ThoughtItem | null;
  earlier: ThoughtItem[];
} {
  if (thoughts.length === 0) return { latest: null, earlier: [] };
  if (thoughts.length === 1) return { latest: thoughts[0], earlier: [] };
  return {
    latest: thoughts[thoughts.length - 1],
    earlier: thoughts.slice(0, -1),
  };
}

export function earlierThoughtCount(thoughts: ThoughtItem[]): number {
  return Math.max(0, thoughts.length - 1);
}
