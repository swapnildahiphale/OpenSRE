import { describe, it, expect } from 'vitest';
import { shouldCollapseTurnTree } from './turnCollapse';
import type { Turn } from './agentTimeline';

function turn(partial: Partial<Turn>): Turn {
  return { query: 'q', items: [], status: 'completed', ...partial };
}

describe('shouldCollapseTurnTree', () => {
  const turns = [
    turn({ runId: '1', status: 'completed' }),
    turn({ runId: '2', status: 'completed' }),
    turn({ runId: '3', status: 'running' }),
  ];

  it('collapses older completed turns', () => {
    expect(shouldCollapseTurnTree(turns[0], 0, turns)).toBe(true);
    expect(shouldCollapseTurnTree(turns[1], 1, turns)).toBe(true);
  });

  it('does not collapse the running turn', () => {
    expect(shouldCollapseTurnTree(turns[2], 2, turns)).toBe(false);
  });

  it('does not collapse latest completed when all idle', () => {
    const idle = [
      turn({ runId: '1', status: 'completed' }),
      turn({ runId: '2', status: 'completed' }),
    ];
    expect(shouldCollapseTurnTree(idle[0], 0, idle)).toBe(true);
    expect(shouldCollapseTurnTree(idle[1], 1, idle)).toBe(false);
  });

  it('does not collapse failed or interrupted', () => {
    const t = [
      turn({ status: 'failed' }),
      turn({ status: 'completed' }),
    ];
    expect(shouldCollapseTurnTree(t[0], 0, t)).toBe(false);
  });

  it('technicalDetails disables collapse', () => {
    expect(shouldCollapseTurnTree(turns[0], 0, turns, { technicalDetails: true })).toBe(false);
  });
});
