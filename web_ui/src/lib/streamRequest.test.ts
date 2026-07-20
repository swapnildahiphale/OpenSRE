import { describe, it, expect } from 'vitest';
import { buildStreamBody, isResumable, canContinueConversation } from './streamRequest';

describe('buildStreamBody', () => {
  it('includes only message when nothing else set', () => {
    expect(buildStreamBody({ message: 'hi' })).toEqual({ message: 'hi' });
  });
  it('includes thread_id, resume_session_id and agent_name when present', () => {
    expect(buildStreamBody({
      message: 'go', threadId: 'thread-1', resumeSessionId: 'sess-1', agentName: 'planner',
    })).toEqual({
      message: 'go', thread_id: 'thread-1', resume_session_id: 'sess-1', agent_name: 'planner',
    });
  });
  it('omits resume_session_id when threadId is absent', () => {
    expect(buildStreamBody({ message: 'go', resumeSessionId: 'sess-1' }))
      .toEqual({ message: 'go' });
  });
});

describe('isResumable', () => {
  it('true for a non-empty session id', () => { expect(isResumable('sess-1')).toBe(true); });
  it('false for null/undefined/empty', () => {
    expect(isResumable(null)).toBe(false);
    expect(isResumable(undefined)).toBe(false);
    expect(isResumable('')).toBe(false);
  });
});

describe('canContinueConversation', () => {
  it('true when sdk session id is present', () => {
    expect(canContinueConversation({ sessionId: 'sess-1' })).toBe(true);
  });
  it('true when in-process session is alive', () => {
    expect(canContinueConversation({ sessionAlive: true })).toBe(true);
  });
  it('false when neither cold nor warm resume is available', () => {
    expect(canContinueConversation({ sessionId: null, sessionAlive: false })).toBe(false);
  });
});
