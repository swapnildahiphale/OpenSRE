import { describe, it, expect } from 'vitest';
import { splitLatestThought, earlierThoughtCount } from './thinkingDisplay';
import type { ThoughtItem } from './agentTimeline';

function thought(text: string, seq = 0): ThoughtItem {
  return { kind: 'thought', seq, ts: '2026-01-01T00:00:00Z', text, depth: 0 };
}

describe('splitLatestThought', () => {
  it('returns nulls for empty list', () => {
    expect(splitLatestThought([])).toEqual({ latest: null, earlier: [] });
  });

  it('single thought is latest with no earlier', () => {
    const t = thought('only');
    expect(splitLatestThought([t])).toEqual({ latest: t, earlier: [] });
  });

  it('latest is last item; earlier are prior in order', () => {
    const a = thought('a', 1);
    const b = thought('b', 2);
    const c = thought('c', 3);
    expect(splitLatestThought([a, b, c])).toEqual({ latest: c, earlier: [a, b] });
  });
});

describe('earlierThoughtCount', () => {
  it('counts earlier only', () => {
    expect(earlierThoughtCount([thought('a'), thought('b')])).toBe(1);
    expect(earlierThoughtCount([thought('a')])).toBe(0);
  });
});
