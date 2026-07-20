import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import {
  trimQueuedMessages,
  visibleBackgroundWaiting,
  shouldSynthesizeStreamEnd,
  shouldFinalizeStream,
  useAgentStream,
} from './useAgentStream';
import { applyEvent, initialTimelineState } from './agentTimeline';

vi.mock('./streamRequest', () => ({
  buildStreamBody: vi.fn((input: { message: string }) => ({ message: input.message })),
  interruptThread: vi.fn().mockResolvedValue(undefined),
}));

function sseResponse(...events: Record<string, unknown>[]) {
  const encoder = new TextEncoder();
  const lines = events
    .map((event) => `data: ${JSON.stringify(event)}\n\n`)
    .join('');
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(lines));
      controller.close();
    },
  });
  return {
    ok: true,
    body: stream,
  };
}

describe('trimQueuedMessages', () => {
  it('returns empty array when pendingCount is 0 (slice(-0) guard)', () => {
    expect(trimQueuedMessages(['a', 'b', 'c'], 'd', 0)).toEqual([]);
  });

  it('returns empty array when pendingCount is negative', () => {
    expect(trimQueuedMessages(['a'], 'b', -1)).toEqual([]);
  });

  it('appends message and keeps all when pendingCount covers the full list', () => {
    expect(trimQueuedMessages(['a', 'b'], 'c', 10)).toEqual(['a', 'b', 'c']);
  });

  it('trims to last pendingCount entries when server reports fewer than local', () => {
    expect(trimQueuedMessages(['a', 'b', 'c'], 'd', 2)).toEqual(['c', 'd']);
  });

  it('handles an empty previous array', () => {
    expect(trimQueuedMessages([], 'first', 1)).toEqual(['first']);
  });

  it('returns single-item array when pendingCount is 1', () => {
    expect(trimQueuedMessages(['old'], 'new', 1)).toEqual(['new']);
  });
});

describe('visibleBackgroundWaiting', () => {
  it('returns null when waiting is null', () => {
    expect(visibleBackgroundWaiting(null)).toBeNull();
  });

  it('returns null when pendingCount is 0 (internal gate may still be set)', () => {
    expect(
      visibleBackgroundWaiting({
        pendingCount: 0,
        pendingTaskIds: [],
        label: 'Waiting on 1 background agent(s)…',
      }),
    ).toBeNull();
  });

  it('returns the waiting state when pendingCount is positive', () => {
    const waiting = {
      pendingCount: 2,
      pendingTaskIds: ['a', 'b'],
      label: 'Waiting on 2 background agent(s)…',
    };
    expect(visibleBackgroundWaiting(waiting)).toBe(waiting);
  });
});

describe('shouldSynthesizeStreamEnd', () => {
  it('returns false while backgroundWaiting gates stream end', () => {
    let s = initialTimelineState;
    s = applyEvent(s, {
      type: 'background_waiting',
      data: { pending_count: 1, pending_task_ids: ['bg-1'], label: 'Waiting…' },
    });
    s = applyEvent(s, {
      type: 'task_notification',
      data: { task_id: 'bg-1', status: 'completed', summary: 'ok' },
    });
    expect(s.backgroundWaiting?.pendingCount).toBe(0);
    expect(shouldSynthesizeStreamEnd(s)).toBe(false);
    expect(shouldFinalizeStream(s)).toBe(false);
  });
});

describe('useAgentStream stop', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('clears isStreaming after stop when SSE ended with backgroundWaiting still set', async () => {
    fetchMock.mockResolvedValue(
      sseResponse({
        type: 'run_started',
        data: { run_id: 'run-1' },
        thread_id: 'thread-1',
      }, {
        type: 'background_waiting',
        data: {
          pending_count: 1,
          pending_task_ids: ['bg-1'],
          label: 'Waiting on 1 background agent(s)…',
        },
      }),
    );

    const { result } = renderHook(() => useAgentStream());

    await act(async () => {
      await result.current.sendMessage('investigate pods');
    });

    expect(result.current.isStreaming).toBe(true);
    expect(result.current.runStatus).toBe('running');

    vi.useFakeTimers();
    try {
      await act(async () => {
        const stopPromise = result.current.stop();
        await vi.advanceTimersByTimeAsync(5100);
        await stopPromise;
      });
    } finally {
      vi.useRealTimers();
    }

    expect(result.current.isStreaming).toBe(false);
    expect(result.current.runStatus).toBe('interrupted');
  });
});
