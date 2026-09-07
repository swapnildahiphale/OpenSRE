import { describe, it, expect } from 'vitest';
import { isOrphanedRun } from './orphanRun';

const base = {
  status: 'running' as const,
  activeKnown: true,
  sessionAlive: false,
  isStreaming: false,
  consecutiveInactivePolls: 2,
};

describe('isOrphanedRun', () => {
  it('true when running, probe known, session dead, not streaming, two inactive polls', () => {
    expect(isOrphanedRun(base)).toBe(true);
  });

  it('false when consecutiveInactivePolls is 1 (rolling-restart grace)', () => {
    expect(isOrphanedRun({ ...base, consecutiveInactivePolls: 1 })).toBe(false);
  });

  it('false when consecutiveInactivePolls is 0', () => {
    expect(isOrphanedRun({ ...base, consecutiveInactivePolls: 0 })).toBe(false);
  });

  it('false when activeKnown is false (fetch not yet 200 / treat as live)', () => {
    expect(isOrphanedRun({ ...base, activeKnown: false })).toBe(false);
  });

  it('false when session is alive', () => {
    expect(isOrphanedRun({ ...base, sessionAlive: true })).toBe(false);
  });

  it('false when streaming (streaming wins)', () => {
    expect(isOrphanedRun({ ...base, isStreaming: true })).toBe(false);
  });

  it('false when status is not running', () => {
    expect(isOrphanedRun({ ...base, status: 'completed' })).toBe(false);
    expect(isOrphanedRun({ ...base, status: 'interrupted' })).toBe(false);
    expect(isOrphanedRun({ ...base, status: 'timeout' })).toBe(false);
  });
});
