'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/apiClient';
import { traceToTimeline, type TimelineItem, type TraceResponse, type RunRecord } from '@/lib/agentTimeline';

export function useRunTrace(runId: string | undefined, isRunning: boolean) {
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    async function load() {
      try {
        const [traceRes, runRes] = await Promise.all([
          apiFetch(`/api/team/agent-runs/${runId}/trace`),
          apiFetch(`/api/team/agent-runs/${runId}`),
        ]);
        const trace: TraceResponse = traceRes.ok ? await traceRes.json() : { runId: runId!, toolCalls: [], thoughts: [], total: 0 };
        const run: RunRecord | undefined = runRes.ok ? await runRes.json() : undefined;
        if (!cancelled) setTimeline(traceToTimeline(trace, run));
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load trace');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    if (isRunning) {
      const id = setInterval(load, 3000);
      return () => { cancelled = true; clearInterval(id); };
    }
    return () => { cancelled = true; };
  }, [runId, isRunning]);

  return { timeline, loading, error };
}
