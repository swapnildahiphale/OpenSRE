'use client';

import { useState, useCallback, useRef, type MutableRefObject } from 'react';
import {
  applyEvent,
  initialTimelineState,
  withUserMessage,
  type TimelineState,
  type TimelineItem,
  type BackgroundWaitingState,
} from '@/lib/agentTimeline';
import { queueMessage } from '@/lib/queueMessage';
import { buildStreamBody, interruptThread } from '@/lib/streamRequest';

const STOP_WAIT_MS = 5000;
const STOP_POLL_MS = 50;

interface UseAgentStreamOptions {
  agentName?: string;
  threadId?: string;          // resume an existing conversation (detail page)
  resumeSessionId?: string;   // its stored SDK session id (cold-revive)
  onComplete?: (output: string) => void;
  onError?: (error: string) => void;
}

function isTerminalRunStatus(status: TimelineState['runStatus']): boolean {
  return status === 'completed' || status === 'failed' || status === 'interrupted' || status === 'timeout';
}

/** Exported for unit tests — whether stream end should push a synthetic result. */
export function shouldSynthesizeStreamEnd(state: TimelineState): boolean {
  return !isTerminalRunStatus(state.runStatus) && !state.backgroundWaiting;
}

/** Exported for unit tests — whether stream-end callbacks / busy UX may finalize. */
export function shouldFinalizeStream(state: TimelineState): boolean {
  return isTerminalRunStatus(state.runStatus);
}

/** UI-only — hide the waiting label once all background tasks have notified. */
export function visibleBackgroundWaiting(
  waiting: BackgroundWaitingState | null,
): BackgroundWaitingState | null {
  if (!waiting || waiting.pendingCount <= 0) return null;
  return waiting;
}

function waitForStopResolution(
  stateRef: MutableRefObject<TimelineState>,
  deadlineMs: number,
): Promise<void> {
  return new Promise((resolve) => {
    const start = Date.now();
    const tick = () => {
      if (isTerminalRunStatus(stateRef.current.runStatus)) {
        resolve();
        return;
      }
      if (Date.now() - start >= deadlineMs) {
        resolve();
        return;
      }
      setTimeout(tick, STOP_POLL_MS);
    };
    tick();
  });
}

/** Exported for unit testing. Pure — no side effects. */
export function trimQueuedMessages(prev: string[], added: string, pendingCount: number): string[] {
  const next = [...prev, added];
  if (pendingCount <= 0) return [];
  return pendingCount >= next.length ? next : next.slice(-pendingCount);
}

export function useAgentStream(options: UseAgentStreamOptions = {}) {
  const { agentName, threadId, resumeSessionId, onComplete, onError } = options;
  const [state, setState] = useState<TimelineState>(initialTimelineState);
  const [isStreaming, setIsStreaming] = useState(false);
  const [queuedMessages, setQueuedMessages] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const stoppingRef = useRef(false);
  const stateRef = useRef<TimelineState>(initialTimelineState);
  // Conversation continuity: once a run starts, every SSE event carries the
  // backend thread_id. We capture it and send it back on follow-up messages so
  // the same in-process agent session continues (keeps prior context) instead of
  // spawning a fresh investigation each time. Cleared by reset() (new conversation).
  const threadIdRef = useRef<string | null>(null);

  const push = useCallback((event: { type?: string; data?: Record<string, unknown> }) => {
    const eventType = event.type || (event.data?.type as string | undefined);

    if (eventType === 'message_queued') {
      const pending = event.data?.pending_count;
      if (typeof pending === 'number' && pending === 0) {
        setQueuedMessages([]);
      }
    }

    stateRef.current = applyEvent(stateRef.current, event);
    setState(stateRef.current);

    if (eventType === 'result' || eventType === 'error') {
      setQueuedMessages([]);
    }
  }, []);

  const sendMessage = useCallback(async (userMessage: string) => {
    if (isStreaming) return;
    // A seeded threadId (detail-page resume) makes every send a follow-up.
    const effectiveThreadId = threadId ?? threadIdRef.current;
    const isFollowUp = effectiveThreadId != null;
    // Append the user's message as a turn marker; new conversation starts clean.
    stateRef.current = withUserMessage(isFollowUp ? stateRef.current : initialTimelineState, userMessage);
    setState(stateRef.current);
    setIsStreaming(true);
    abortRef.current = new AbortController();

    try {
      const response = await fetch('/api/team/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildStreamBody({
          message: userMessage,
          threadId: effectiveThreadId,
          resumeSessionId,
          agentName,
        })),
        signal: abortRef.current.signal,
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${response.status}`);
      }
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(line.slice(6));
              if (parsed.thread_id) threadIdRef.current = parsed.thread_id as string;
              push(parsed);
            } catch { /* partial line */ }
          }
        }
      }
      // If the stream closed without a terminal event, push a synthetic result so
      // runStatus transitions out of 'running' and the spinner clears — unless we
      // are still waiting on background agents (backend should keep the stream open).
      if (shouldSynthesizeStreamEnd(stateRef.current)) {
        const lastResult = [...stateRef.current.items]
          .reverse()
          .find((i): i is Extract<TimelineItem, { kind: 'result' }> => i.kind === 'result');
        push({ type: 'result', data: { text: lastResult?.text ?? '', success: true } });
      }
      const final = stateRef.current;
      if (shouldFinalizeStream(final)) {
        const resultItem = [...final.items].reverse().find((i): i is Extract<TimelineItem, { kind: 'result' }> => i.kind === 'result');
        if (final.error) onError?.(final.error);
        else onComplete?.(resultItem?.text ?? '');
      }
    } catch (err) {
      const isIntentionalStop =
        stoppingRef.current && (err as Error).name === 'AbortError';
      if (!isIntentionalStop && (err as Error).name !== 'AbortError') {
        const msg = (err as Error).message || 'Failed to run agent';
        push({ type: 'error', data: { message: msg } });
        onError?.(msg);
      }
    } finally {
      stoppingRef.current = false;
      // Keep busy/streaming UX while run is still non-terminal (e.g. background wait
      // with a dropped connection) — only unlock when a true terminal event landed.
      if (shouldFinalizeStream(stateRef.current)) {
        setIsStreaming(false);
      }
      abortRef.current = null;
    }
  }, [isStreaming, agentName, threadId, resumeSessionId, onComplete, onError, push]);

  const cancel = useCallback(() => abortRef.current?.abort(), []);

  const queueMessageDuringRun = useCallback(async (text: string) => {
    const effectiveThreadId = threadId ?? threadIdRef.current;
    if (!effectiveThreadId || !isStreaming) {
      throw new Error('No active investigation');
    }
    const { pending_count } = await queueMessage(effectiveThreadId, text);
    setQueuedMessages((prev) => trimQueuedMessages(prev, text, pending_count));
  }, [isStreaming, threadId]);

  const stop = useCallback(async () => {
    if (!isStreaming) return;
    stoppingRef.current = true;
    const effectiveThreadId = threadId ?? threadIdRef.current;
    if (effectiveThreadId) {
      try {
        await interruptThread(effectiveThreadId);
      } catch {
        // Best-effort — wait/abort below still runs.
      }
    }

    await waitForStopResolution(stateRef, STOP_WAIT_MS);

    if (stateRef.current.runStatus === 'running') {
      push({
        type: 'result',
        data: {
          text: 'Investigation stopped.',
          success: true,
          subtype: 'interrupted',
        },
      });
    }

    abortRef.current?.abort();
    setQueuedMessages([]);
    // sendMessage's finally may skip clearing isStreaming while backgroundWaiting
    // gates finalize; intentional stop must always unlock the composer.
    setIsStreaming(false);
  }, [isStreaming, threadId, push]);

  const reset = useCallback(() => {
    threadIdRef.current = null;
    stateRef.current = initialTimelineState;
    setState(initialTimelineState);
  }, []);

  return {
    timeline: state.items,
    runStatus: state.runStatus,
    runId: state.runId,
    backgroundWaiting: visibleBackgroundWaiting(state.backgroundWaiting),
    error: state.error ?? null,
    isStreaming,
    sendMessage,
    queueMessage: queueMessageDuringRun,
    queuedMessages,
    cancel,
    stop,
    reset,
  };
}
