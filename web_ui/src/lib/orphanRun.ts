import type { RunStatus } from '@/lib/agentTimeline';

export function isOrphanedRun(opts: {
  status: RunStatus;
  activeKnown: boolean;
  sessionAlive: boolean;
  isStreaming: boolean;
  consecutiveInactivePolls: number;
}): boolean {
  return (
    opts.status === 'running' &&
    opts.activeKnown &&
    !opts.sessionAlive &&
    !opts.isStreaming &&
    opts.consecutiveInactivePolls >= 2
  );
}
