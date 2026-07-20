'use client';

import { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '@/lib/apiClient';
import { canContinueConversation } from '@/lib/streamRequest';
import {
  traceToTimeline, runsToTurns,
  type Turn, type RunWithTrace, type TraceResponse, type RunStatus,
} from '@/lib/agentTimeline';
import { pickThreadSummary, type ThreadRunSlice } from '@/lib/pickThreadSummary';

interface ListRun {
  id: string; correlationId: string; agentName: string; status: string;
  startedAt: string; triggerMessage?: string;
  outputSummary?: string | null; outputJson?: Record<string, unknown> | null;
  errorMessage?: string | null;
  sdkSessionId?: string | null;
}

const asRunStatus = (s: string): RunStatus =>
  s === 'completed' || s === 'running' || s === 'failed' || s === 'interrupted' || s === 'timeout'
    ? s
    : 'idle';

const asThreadRunStatus = (s: string): ThreadRunSlice['status'] => {
  if (s === 'running' || s === 'completed' || s === 'failed' || s === 'timeout' || s === 'interrupted') {
    return s;
  }
  return 'completed';
};

export function useConversation(runId: string | undefined) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [title, setTitle] = useState('');
  const [agentName, setAgentName] = useState('');
  const [status, setStatus] = useState<RunStatus>('idle');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [sessionAlive, setSessionAlive] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // isCancelled defaults to () => false for the public reload path.
  // The polling effect passes its own cancelled flag so in-flight fetches
  // do not setState after unmount or runId change.
  const load = useCallback(async (isCancelled: () => boolean = () => false) => {
    if (!runId) return;
    try {
      const runRes = await apiFetch(`/api/team/agent-runs/${runId}`);
      if (!runRes.ok) throw new Error(`Run not found (${runRes.status})`);
      const thisRun: ListRun = await runRes.json();

      const listRes = await apiFetch('/api/team/agent-runs');
      const allRuns: ListRun[] = listRes.ok ? await listRes.json() : [];
      const convRuns = allRuns
        .filter((r) => r.correlationId && r.correlationId === thisRun.correlationId)
        .sort((a, b) => a.startedAt.localeCompare(b.startedAt));
      const runs = convRuns.length > 0 ? convRuns : [thisRun];

      const withTraces: RunWithTrace[] = await Promise.all(runs.map(async (r) => {
        const tRes = await apiFetch(`/api/team/agent-runs/${r.id}/trace`);
        const trace: TraceResponse = tRes.ok ? await tRes.json() : { runId: r.id, toolCalls: [], thoughts: [], total: 0 };
        return {
          runId: r.id, query: r.triggerMessage ?? '', startedAt: r.startedAt,
          status: asRunStatus(r.status),
          outputSummary: r.outputSummary ?? null,
          outputJson: (r.outputJson ?? null) as RunWithTrace['outputJson'],
          items: traceToTimeline(trace),
        };
      }));

      const epRes = await fetch('/api/memory/episodes');
      const epData = epRes.ok ? await epRes.json() : { episodes: [] };
      const episode = (epData.episodes ?? []).find(
        (e: { correlation_id?: string }) => e.correlation_id === thisRun.correlationId,
      );

      let alive = false;
      let inMemorySessionId: string | null = null;
      if (thisRun.correlationId) {
        const activeRes = await apiFetch(
          `/api/team/agent/threads/${encodeURIComponent(thisRun.correlationId)}/active`,
        );
        if (activeRes.ok) {
          const activeData = await activeRes.json() as {
            active?: boolean; sdk_session_id?: string | null;
          };
          alive = activeData.active === true;
          inMemorySessionId = activeData.sdk_session_id ?? null;
        }
      }

      // Guard: don't setState if the component unmounted or runId changed mid-fetch.
      if (isCancelled()) return;
      setTurns(runsToTurns(withTraces));
      const latestRun = runs[runs.length - 1];
      setTitle(
        pickThreadSummary(
          episode,
          {
            status: asThreadRunStatus(latestRun.status),
            triggerMessage: latestRun.triggerMessage,
            outputJson: latestRun.outputJson,
            errorMessage: latestRun.errorMessage,
          },
          {
            status: asThreadRunStatus(runs[0]?.status ?? 'completed'),
            triggerMessage: runs[0]?.triggerMessage,
          },
        ),
      );
      setAgentName(runs[0]?.agentName ?? 'agent');
      setThreadId(thisRun.correlationId || null);
      // Latest run in the conversation carries the freshest session id.
      const latestSession = [...runs].reverse().map((r) => r.sdkSessionId).find(Boolean) ?? null;
      setSessionId(latestSession ?? inMemorySessionId ?? null);
      setSessionAlive(alive);
      setErrorMessage(latestRun.errorMessage ?? null);
      setStatus(asRunStatus(runs[runs.length - 1]?.status ?? 'idle'));
    } catch (e) {
      if (!isCancelled()) setError(e instanceof Error ? e.message : 'Failed to load conversation');
    } finally {
      if (!isCancelled()) setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    const tick = () => load(() => cancelled);
    tick();
    const intervalMs = status === 'running' ? 1500 : 4000;
    const timer = setInterval(tick, intervalMs);
    return () => { cancelled = true; clearInterval(timer); };
  }, [runId, load, status]);

  // Public reload: called by the detail page after a follow-up completes.
  // No cancellation token — callers own their own lifecycle.
  const reload = useCallback(() => load(), [load]);

  return {
    turns, title, agentName, status,
    sessionId, threadId, sessionAlive, errorMessage,
    continuable: canContinueConversation({ sessionId, sessionAlive }),
    loading, error, reload,
  };
}
