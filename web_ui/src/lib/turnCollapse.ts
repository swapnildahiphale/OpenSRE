import type { Turn } from './agentTimeline';

export function shouldCollapseTurnTree(
  turn: Turn,
  index: number,
  turns: Turn[],
  opts?: { technicalDetails?: boolean },
): boolean {
  if (opts?.technicalDetails) return false;
  if (turn.status === 'running') return false;
  if (turn.status === 'failed' || turn.status === 'interrupted') return false;
  if (index === turns.length - 1) return false;
  return turn.status === 'completed';
}
