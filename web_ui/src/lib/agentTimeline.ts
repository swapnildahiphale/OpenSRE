// web_ui/src/lib/agentTimeline.ts
import type { InvestigationReportData } from '@/components/InvestigationReport';

export interface ThoughtItem {
  kind: 'thought';
  seq: number;
  ts: string;
  text: string;
  agent?: string;
  depth: number;
  agentId?: string;
  parentAgentId?: string;
}
export interface ToolItem {
  kind: 'tool';
  seq: number;
  id: string;
  toolName: string;
  agentName?: string;
  // Nested-agent attribution (from SDK PreToolUse hook agent_id resolution).
  // parentAgentName is the *agent type* of the dispatching parent (e.g.
  // "investigation" for a grandchild under it), not a tool_use_id. depth is
  // 0 for the root agent's own calls, 1 for a direct subagent, 2 for a
  // sub-sub-agent, etc. agentId is the SDK's opaque per-agent id.
  parentAgentName?: string;
  parentAgentId?: string;
  depth: number;
  agentId?: string;
  parentToolUseId?: string;
  input?: Record<string, unknown>;
  output?: string;
  status: 'running' | 'success' | 'error';
  startedAt: string;
  durationMs?: number;
  error?: string;
}
export interface ResultItem {
  kind: 'result';
  seq: number;
  text: string;
  structuredReport?: InvestigationReportData | null;
  success: boolean;
}
export interface UserItem {
  kind: 'user';
  seq: number;
  text: string;
  ts: string;
}
export type TimelineItem = ThoughtItem | ToolItem | ResultItem | UserItem;

export type RunStatus = 'idle' | 'running' | 'completed' | 'failed' | 'interrupted' | 'timeout';

export interface BackgroundWaitingState {
  pendingCount: number;
  pendingTaskIds: string[];
  label: string;
}

export interface TimelineState {
  items: TimelineItem[];
  runStatus: RunStatus;
  runId?: string;
  error?: string;
  seqCounter: number;
  taskAgents: Record<string, { agentType: string; depth: number; invocationId: string; parentInvocationId?: string }>;
  rootAgent?: string;
  backgroundWaiting: BackgroundWaitingState | null;
}

export const initialTimelineState: TimelineState = {
  items: [],
  runStatus: 'idle',
  seqCounter: 0,
  taskAgents: {},
  backgroundWaiting: null,
};

interface RawEvent { type?: string; data?: Record<string, unknown> }

const cleanResult = (t: string) =>
  t.replace(/\n*\(no content\)\n*/g, '\n').replace(/\n{3,}/g, '\n\n').trim();

export function applyEvent(state: TimelineState, event: RawEvent): TimelineState {
  const data = (event.data && typeof event.data === 'object') ? event.data : {};
  const type = event.type || (data.type as string) || 'unknown';

  switch (type) {
    case 'run_started':
      return {
        ...state,
        runId: (data.run_id as string) ?? state.runId,
        rootAgent: (data.agent as string) ?? state.rootAgent,
        runStatus: 'running',
      };

    case 'thought': {
      const text = ((data.text as string) ?? '').trim();
      if (!text || text === '(no content)') return state;
      const parent = data.parent_tool_use_id as string | undefined;
      const info = parent ? state.taskAgents[parent] : undefined;
      const item: ThoughtItem = {
        kind: 'thought', seq: state.seqCounter, ts: new Date().toISOString(),
        text,
        agent: info ? info.agentType : state.rootAgent,
        depth: info ? info.depth : 0,
        agentId: info ? info.invocationId : undefined,
        parentAgentId: info ? info.parentInvocationId : undefined,
      };
      return { ...state, items: [...state.items, item], seqCounter: state.seqCounter + 1 };
    }

    case 'tool_start': {
      const name = (data.name as string) ?? 'unknown';
      const id = (data.tool_use_id as string) ?? `tool-${state.seqCounter}`;
      const parent = data.parent_tool_use_id as string | undefined;
      const taskAgents = ((name === 'Task' || name === 'Agent') && data.subagent_type)
        ? {
            ...state.taskAgents,
            [id]: {
              agentType: data.subagent_type as string,
              depth: ((data.depth as number) ?? 0) + 1,
              invocationId: id,
              parentInvocationId: (data.agent_id as string) ?? undefined,
            },
          }
        : state.taskAgents;
      const item: ToolItem = {
        kind: 'tool', seq: state.seqCounter, id, toolName: name,
        // Primary source is the SDK-hook-derived agent_type on the event
        // (set for every call at any depth by the PreToolUse hook). The
        // taskAgents/rootAgent fallbacks stay as a defensive net for any
        // event that somehow lacks the new fields (e.g. an older stream).
        agentName: (data.agent_type as string) ?? (parent ? state.taskAgents[parent]?.agentType : state.rootAgent),
        parentAgentName: (data.parent_agent_type as string) ?? undefined,
        parentAgentId: (data.parent_agent_id as string) ?? undefined,
        depth: (data.depth as number) ?? 0,
        agentId: (data.agent_id as string) ?? undefined,
        parentToolUseId: parent,
        input: (data.input as Record<string, unknown>) ?? undefined,
        status: 'running', startedAt: new Date().toISOString(),
      };
      return { ...state, items: [...state.items, item], taskAgents, seqCounter: state.seqCounter + 1 };
    }

    case 'tool_end': {
      const id = data.tool_use_id as string | undefined;
      const success = data.success !== false;
      const output = (data.output as string) ?? (data.summary as string) ?? undefined;
      const error = data.error as string | undefined;
      let targetIndex = -1;
      if (id) {
        targetIndex = state.items.findIndex((it) => it.kind === 'tool' && it.id === id);
      } else {
        for (let i = state.items.length - 1; i >= 0; i--) {
          const it = state.items[i];
          if (it.kind === 'tool' && it.status === 'running') { targetIndex = i; break; }
        }
      }
      if (targetIndex === -1) return state;
      const items = state.items.map((it, i) => {
        if (i !== targetIndex || it.kind !== 'tool') return it;
        return {
          ...it, status: (success ? 'success' : 'error') as ToolItem['status'],
          output, error,
          durationMs: Date.now() - Date.parse(it.startedAt),
        };
      });
      return { ...state, items };
    }

    case 'task_started':
      // Background SDK task launched — stay running until terminal result.
      return { ...state, runStatus: 'running' };

    case 'background_waiting': {
      const pendingTaskIds = (data.pending_task_ids as string[]) ?? [];
      const pendingCount = (data.pending_count as number) ?? pendingTaskIds.length;
      const label = (data.label as string) ?? `Waiting on ${pendingCount} background agent(s)…`;
      return {
        ...state,
        runStatus: 'running',
        backgroundWaiting: { pendingCount, pendingTaskIds, label },
      };
    }

    case 'task_notification': {
      const taskId = data.task_id as string | undefined;
      const waiting = state.backgroundWaiting;
      if (!waiting || !taskId) {
        return { ...state, runStatus: 'running' };
      }
      const pendingTaskIds = waiting.pendingTaskIds.filter((id) => id !== taskId);
      const pendingCount = pendingTaskIds.length;
      // Keep backgroundWaiting until terminal result/error — even when pending hits 0,
      // so stream-end synthetic complete and onComplete stay gated until the run finishes.
      return {
        ...state,
        runStatus: 'running',
        backgroundWaiting: {
          ...waiting,
          pendingCount,
          pendingTaskIds,
        },
      };
    }

    case 'result': {
      const interrupted = data.subtype === 'interrupted';
      const item: ResultItem = {
        kind: 'result', seq: state.seqCounter,
        text: cleanResult((data.text as string) ?? ''),
        structuredReport: (data.structured_report as InvestigationReportData) ?? null,
        success: data.success !== false,
      };
      return {
        ...state, items: [...state.items, item],
        runStatus: interrupted ? 'interrupted' : (item.success ? 'completed' : 'failed'),
        backgroundWaiting: null,
        seqCounter: state.seqCounter + 1,
      };
    }

    case 'error': {
      const message = (data.message as string) ?? 'Unknown error';
      const timedOut = message.toLowerCase().includes('time limit');
      return {
        ...state,
        error: message,
        runStatus: timedOut ? 'timeout' : 'failed',
        backgroundWaiting: null,
      };
    }

    default:
      return state;
  }
}

export interface ToolCallTrace {
  id: string;
  toolName: string;
  agentName?: string | null;
  parentAgent?: string | null;
  // Nested-agent attribution persisted on agent_tool_calls (Task 4).
  depth?: number | null;
  agentId?: string | null;
  parentAgentId?: string | null;
  toolInput?: Record<string, unknown> | null;
  toolOutput?: string | null;
  startedAt: string;
  durationMs?: number | null;
  status: string;
  errorMessage?: string | null;
  sequenceNumber: number;
}
export interface ThoughtTrace {
  text: string; ts: string; seq: number; agent?: string | null;
  depth?: number | null; agentId?: string | null; parentAgentId?: string | null;
}
export interface TraceResponse {
  runId: string;
  toolCalls: ToolCallTrace[];
  thoughts: ThoughtTrace[];
  total: number;
}
export interface RunRecord {
  outputSummary?: string | null;
  outputJson?: InvestigationReportData | null;
  status?: string;
}

export interface Turn {
  runId?: string;
  query: string;
  items: TimelineItem[];   // thoughts + tools only (no result)
  result?: ResultItem;
  status: RunStatus;
}

export interface RunWithTrace {
  runId: string;
  query: string;
  startedAt: string;
  status: RunStatus;
  outputSummary?: string | null;
  outputJson?: InvestigationReportData | null;
  items: TimelineItem[];   // thoughts + tools from the run's trace (no result)
}

/** Append a user message marker to the live timeline and mark the run running. */
export function withUserMessage(state: TimelineState, text: string): TimelineState {
  const item: UserItem = { kind: 'user', seq: state.seqCounter, text, ts: new Date().toISOString() };
  return {
    ...state,
    items: [...state.items, item],
    seqCounter: state.seqCounter + 1,
    runStatus: 'running',
    error: undefined,
  };
}

/** Split a flat live timeline into turns on `user` markers. */
export function timelineToTurns(items: TimelineItem[]): Turn[] {
  const turns: Turn[] = [];
  let cur: Turn | null = null;
  const ensure = () => {
    if (!cur) { cur = { query: '', items: [], status: 'running' }; turns.push(cur); }
    return cur;
  };
  for (const it of items) {
    if (it.kind === 'user') {
      cur = { query: it.text, items: [], status: 'running' };
      turns.push(cur);
    } else if (it.kind === 'result') {
      const t = ensure();
      t.result = it;
      t.status = it.success ? 'completed' : 'failed';
    } else {
      ensure().items.push(it);
    }
  }
  return turns;
}

/** Build turns from persisted runs (one run = one turn), ordered by startedAt. */
export function runsToTurns(runs: RunWithTrace[]): Turn[] {
  return [...runs]
    .sort((a, b) => a.startedAt.localeCompare(b.startedAt))
    .map((r) => ({
      runId: r.runId,
      query: r.query,
      items: r.items.filter((i) => i.kind !== 'result'),
      result: (r.outputSummary || r.outputJson)
        ? {
            kind: 'result' as const, seq: Number.MAX_SAFE_INTEGER,
            text: r.outputSummary ?? '', structuredReport: r.outputJson ?? null,
            success: r.status !== 'failed' && r.status !== 'timeout',
          }
        : undefined,
      status: r.status,
    }));
}

/**
 * Merge historical turns (polled DB traces) with live turns (SSE stream) for
 * the run detail page, preventing the in-flight follow-up from rendering twice.
 *
 * Why this is needed: a follow-up run shares the opened run's correlationId, so
 * the `useConversation` poller pulls it into `historical` (from its DB trace)
 * while the `useAgentStream` SSE stream is still rendering the same run in
 * `live`. Naively concatenating would show that turn twice for the whole run.
 *
 * While a live run id is known (`liveRunId`, captured from the stream's
 * `run_started` event), drop its historical copy so the live stream owns it.
 * When the stream settles and `reset()` clears `liveRunId`, the (now completed)
 * run is shown from history alone — no duplication at any point.
 */
export function mergeTurns(
  historical: Turn[],
  live: Turn[],
  liveRunId?: string | null,
): Turn[] {
  if (!liveRunId) return [...historical, ...live];
  return [...historical.filter((t) => t.runId !== liveRunId), ...live];
}

export function traceToTimeline(trace: TraceResponse, run?: RunRecord): TimelineItem[] {
  const tools: TimelineItem[] = (trace.toolCalls ?? []).map((tc) => ({
    kind: 'tool', seq: tc.sequenceNumber, id: tc.id, toolName: tc.toolName,
    agentName: tc.agentName ?? undefined,
    // tc.parentAgent was already on ToolCallTrace but never read before this;
    // read it here alongside the new depth/agentId so historical DB replay
    // shows the same nested attribution as the live stream.
    parentAgentName: tc.parentAgent ?? undefined,
    parentAgentId: tc.parentAgentId ?? undefined,
    depth: tc.depth ?? 0,
    agentId: tc.agentId ?? undefined,
    parentToolUseId: undefined,
    input: tc.toolInput ?? undefined, output: tc.toolOutput ?? undefined,
    status: tc.status === 'error' ? 'error' : 'success',
    startedAt: tc.startedAt, durationMs: tc.durationMs ?? undefined,
    error: tc.errorMessage ?? undefined,
  }));
  const thoughts: TimelineItem[] = (trace.thoughts ?? []).map((t) => ({
    kind: 'thought', seq: t.seq, ts: t.ts, text: t.text, agent: t.agent ?? undefined,
    depth: t.depth ?? 0, agentId: t.agentId ?? undefined, parentAgentId: t.parentAgentId ?? undefined,
  }));
  const items = [...tools, ...thoughts].sort((a, b) => a.seq - b.seq);
  if (run && (run.outputJson || run.outputSummary)) {
    items.push({
      kind: 'result', seq: Number.MAX_SAFE_INTEGER,
      text: run.outputSummary ?? '', structuredReport: run.outputJson ?? null,
      success: run.status !== 'failed',
    });
  }
  return items;
}
