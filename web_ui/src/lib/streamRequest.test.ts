import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { buildStreamBody, isResumable, canContinueConversation, abandonRun, pickLatestSdkSessionId } from './streamRequest';

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

describe('pickLatestSdkSessionId', () => {
  it('picks the running row id when it is last and set', () => {
    expect(pickLatestSdkSessionId([
      { sdkSessionId: 'sess-old' },
      { sdkSessionId: 'sess-running' },
    ])).toBe('sess-running');
  });

  it('skips a trailing null and uses the previous id', () => {
    expect(pickLatestSdkSessionId([
      { sdkSessionId: 'sess-completed' },
      { sdkSessionId: null },
    ])).toBe('sess-completed');
  });

  it('returns null when every row is null or empty', () => {
    expect(pickLatestSdkSessionId([
      { sdkSessionId: null },
      { sdkSessionId: '' },
    ])).toBe(null);
    expect(pickLatestSdkSessionId([])).toBe(null);
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

describe('canContinueConversation orphan follow-up', () => {
  it('true when threadId is set and isLive is false (no sdk session)', () => {
    expect(canContinueConversation({
      sessionId: null,
      sessionAlive: false,
      threadId: 'thread-1',
      isLive: false,
    })).toBe(true);
  });

  it('true when live even without session id', () => {
    expect(canContinueConversation({
      sessionId: null,
      threadId: 'thread-1',
      isLive: true,
    })).toBe(true);
  });

  it('false when no threadId and neither cold nor warm resume', () => {
    expect(canContinueConversation({
      sessionId: null,
      sessionAlive: false,
    })).toBe(false);
  });

  it('does not treat omitted isLive as false (no accidental unlock)', () => {
    expect(canContinueConversation({
      sessionId: null,
      sessionAlive: false,
      threadId: 'thread-1',
    })).toBe(false);
  });
});

describe('abandonRun', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('succeeds on 200', async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200 });
    await abandonRun('run-1');
    expect(fetchMock).toHaveBeenCalledWith('/api/team/agent-runs/run-1/abandon', {
      method: 'POST',
    });
  });

  it('succeeds silently on 409', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 409 });
    await abandonRun('run-1');
  });

  it('throws on other errors', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Agent run not found' }),
    });
    await expect(abandonRun('run-1')).rejects.toThrow('Agent run not found');
  });
});
