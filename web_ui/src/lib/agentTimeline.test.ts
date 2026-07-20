// web_ui/src/lib/agentTimeline.test.ts
import { describe, it, expect } from 'vitest';
import { applyEvent, initialTimelineState, traceToTimeline, withUserMessage, timelineToTurns, runsToTurns, mergeTurns, type RunWithTrace, type Turn, type ThoughtItem } from './agentTimeline';

const ev = (type: string, data: Record<string, unknown> = {}) => ({ type, data });

describe('applyEvent', () => {
  it('captures run_started run_id + root agent and sets running', () => {
    const s = applyEvent(initialTimelineState, ev('run_started', { run_id: 'r1', agent: 'investigator' }));
    expect(s.runId).toBe('r1');
    expect(s.rootAgent).toBe('investigator');
    expect(s.runStatus).toBe('running');
  });

  it('attributes root-level tools + thoughts to the run_started root agent (matches DB replay)', () => {
    let s = applyEvent(initialTimelineState, ev('run_started', { run_id: 'r1', agent: 'investigator' }));
    s = applyEvent(s, ev('tool_start', { name: 'Bash', tool_use_id: 'tu1', input: { command: 'ls' } }));
    s = applyEvent(s, ev('thought', { text: 'looking around' }));
    const tool = s.items.find((i) => i.kind === 'tool') as any;
    const thought = s.items.find((i) => i.kind === 'thought') as any;
    expect(tool.agentName).toBe('investigator');
    expect(thought.agent).toBe('investigator');
  });

  it('appends thought items, skipping (no content)', () => {
    let s = applyEvent(initialTimelineState, ev('thought', { text: 'analyzing' }));
    s = applyEvent(s, ev('thought', { text: '(no content)' }));
    const thoughts = s.items.filter((i) => i.kind === 'thought');
    expect(thoughts).toHaveLength(1);
    expect(thoughts[0]).toMatchObject({ text: 'analyzing', seq: 0 });
  });

  it('matches tool_end to tool_start by tool_use_id and sets output/status', () => {
    let s = applyEvent(initialTimelineState, ev('tool_start', { name: 'Bash', tool_use_id: 'tu1', input: { command: 'ls' } }));
    s = applyEvent(s, ev('tool_end', { name: 'Bash', tool_use_id: 'tu1', success: true, output: 'files' }));
    const tool = s.items.find((i) => i.kind === 'tool') as any;
    expect(tool.status).toBe('success');
    expect(tool.output).toBe('files');
    expect(tool.input).toEqual({ command: 'ls' });
  });

  it('attributes child tools to the Task subagent', () => {
    let s = applyEvent(initialTimelineState, ev('tool_start', { name: 'Task', tool_use_id: 'task1', subagent_type: 'kubernetes', input: {} }));
    s = applyEvent(s, ev('tool_start', { name: 'Bash', tool_use_id: 'tu2', parent_tool_use_id: 'task1', input: { command: 'kubectl' } }));
    const child = s.items.find((i) => i.kind === 'tool' && (i as any).id === 'tu2') as any;
    expect(child.agentName).toBe('kubernetes');
    expect(child.parentToolUseId).toBe('task1');
  });

  it('attributes child tools to an Agent-named subagent dispatch (newer SDK tool name)', () => {
    let s = applyEvent(initialTimelineState, ev('tool_start', { name: 'Agent', tool_use_id: 'task2', subagent_type: 'general-purpose', input: {} }));
    s = applyEvent(s, ev('tool_start', { name: 'Bash', tool_use_id: 'tu3', parent_tool_use_id: 'task2', input: { command: 'ls' } }));
    const child = s.items.find((i) => i.kind === 'tool' && (i as any).id === 'tu3') as any;
    expect(child.agentName).toBe('general-purpose');
  });

  it('tool_start carries depth and parentAgentName from event data (nested-agent attribution)', () => {
    const s = applyEvent(initialTimelineState, ev('tool_start', {
      name: 'Bash', tool_use_id: 't1', agent_type: 'general-purpose',
      parent_agent_type: 'investigation', depth: 2,
    }));
    const item = s.items[0] as any;
    expect(item.agentName).toBe('general-purpose');
    expect(item.parentAgentName).toBe('investigation');
    expect(item.depth).toBe(2);
    expect(item.agentId).toBeUndefined(); // absent on the wire -> undefined, not null
  });

  it('terminal result sets completed and strips (no content)', () => {
    const s = applyEvent(initialTimelineState, ev('result', { text: 'done\n(no content)\n', success: true, structured_report: { title: 'RC' } }));
    const r = s.items.find((i) => i.kind === 'result') as any;
    expect(r.text).toBe('done');
    expect(r.structuredReport).toEqual({ title: 'RC' });
    expect(s.runStatus).toBe('completed');
  });

  it('interrupted result sets interrupted status', () => {
    const s = applyEvent(initialTimelineState, ev('result', {
      text: 'Task interrupted. Send a new message to continue.',
      success: true,
      subtype: 'interrupted',
    }));
    expect(s.runStatus).toBe('interrupted');
  });

  it('error sets failed status', () => {
    const s = applyEvent(initialTimelineState, ev('error', { message: 'boom' }));
    expect(s.runStatus).toBe('failed');
    expect(s.error).toBe('boom');
  });

  it('time-limit error sets timeout status', () => {
    const s = applyEvent(initialTimelineState, ev('error', {
      message: 'Investigation stopped after 10 minutes (time limit).',
    }));
    expect(s.runStatus).toBe('timeout');
  });

  it('resolves a subagent thought (parent_tool_use_id set) to the subagent depth/agentId, not root', () => {
    let s = applyEvent(initialTimelineState, ev('tool_start', {
      name: 'Task', tool_use_id: 'task-1', subagent_type: 'investigation',
      depth: 0, agent_id: null, parent_agent_id: null,
    }));
    s = applyEvent(s, ev('thought', { text: 'investigating first', parent_tool_use_id: 'task-1' }));
    const thought = s.items.find((i) => i.kind === 'thought') as ThoughtItem;
    expect(thought.depth).toBe(1);
    expect(thought.agentId).toBe('task-1');
    expect(thought.parentAgentId).toBeUndefined();
  });

  it('root-level thought has depth 0, no agentId/parentAgentId', () => {
    let s = applyEvent(initialTimelineState, ev('run_started', { run_id: 'r1', agent: 'investigator' }));
    s = applyEvent(s, ev('thought', { text: 'analyzing' }));
    const thought = s.items.find((i) => i.kind === 'thought') as ThoughtItem;
    expect(thought.depth).toBe(0);
    expect(thought.agentId).toBeUndefined();
    expect(thought.parentAgentId).toBeUndefined();
  });
});

describe('traceToTimeline', () => {
  const trace = {
    runId: 'r1', total: 2,
    toolCalls: [
      { id: 'a', toolName: 'Bash', agentName: 'sre-agent', toolInput: { command: 'ls' }, toolOutput: 'x', startedAt: '2026-01-01T00:00:00Z', status: 'success', sequenceNumber: 1, durationMs: 5 },
      { id: 'b', toolName: 'Grep', agentName: 'kubernetes', toolInput: { pattern: 'err' }, toolOutput: 'y', startedAt: '2026-01-01T00:00:02Z', status: 'error', sequenceNumber: 3, errorMessage: 'nope' },
    ],
    thoughts: [{ text: 'thinking', ts: '2026-01-01T00:00:01Z', seq: 2, agent: 'sre-agent' }],
  };

  it('interleaves tools + thoughts by seq', () => {
    const items = traceToTimeline(trace);
    expect(items.map((i) => i.kind)).toEqual(['tool', 'thought', 'tool']);
    expect((items[0] as any).id).toBe('a');
  });

  it('appends a terminal result from the run record', () => {
    const items = traceToTimeline(trace, { outputSummary: 'FULL REPORT', outputJson: { title: 'RC' }, status: 'completed' });
    const r = items[items.length - 1] as any;
    expect(r.kind).toBe('result');
    expect(r.text).toBe('FULL REPORT');
    expect(r.structuredReport).toEqual({ title: 'RC' });
  });

  it('maps parentAgent and depth from historical trace (nested-agent attribution)', () => {
    const items = traceToTimeline({
      runId: 'r1', total: 1,
      toolCalls: [{
        id: 't1', toolName: 'Bash', agentName: 'investigation', parentAgent: 'planner',
        depth: 1, agentId: 'agent-A', toolInput: {}, toolOutput: 'ok',
        startedAt: '2026-01-01T00:00:00Z', status: 'success', sequenceNumber: 0,
      }],
      thoughts: [],
    });
    const item = items[0] as any;
    expect(item.parentAgentName).toBe('planner');
    expect(item.depth).toBe(1);
    expect(item.agentId).toBe('agent-A');
  });

  it('maps error status', () => {
    const t = traceToTimeline(trace).find((i) => i.kind === 'tool' && (i as any).id === 'b') as any;
    expect(t.status).toBe('error');
    expect(t.error).toBe('nope');
  });

  it('traceToTimeline maps thought depth/agentId/parentAgentId from the historical trace', () => {
    const items = traceToTimeline({
      runId: 'r1', total: 1, toolCalls: [],
      thoughts: [{ text: 'hi', ts: '2026-01-01T00:00:00Z', seq: 0, agent: 'investigation', depth: 1, agentId: 'task-1', parentAgentId: undefined } as any],
    });
    const thought = items.find((i) => i.kind === 'thought') as ThoughtItem;
    expect(thought.depth).toBe(1);
    expect(thought.agentId).toBe('task-1');
  });
});

describe('withUserMessage', () => {
  it('appends a user marker and advances seq + sets running', () => {
    const s = withUserMessage(initialTimelineState, 'list namespaces');
    const u = s.items[0] as any;
    expect(u.kind).toBe('user');
    expect(u.text).toBe('list namespaces');
    expect(u.seq).toBe(0);
    expect(s.seqCounter).toBe(1);
    expect(s.runStatus).toBe('running');
  });
});

describe('timelineToTurns', () => {
  it('splits a multi-turn timeline on user markers, attaching trace + result per turn', () => {
    let s = withUserMessage(initialTimelineState, 'list namespaces');
    s = applyEvent(s, ev('tool_start', { name: 'Bash', tool_use_id: 't1', input: { command: 'kubectl get ns' } }));
    s = applyEvent(s, ev('tool_end', { name: 'Bash', tool_use_id: 't1', success: true, output: 'none' }));
    s = applyEvent(s, ev('result', { text: 'No clusters', success: true }));
    s = withUserMessage(s, 'aws access?');
    s = applyEvent(s, ev('tool_start', { name: 'Bash', tool_use_id: 't2', input: { command: 'env' } }));

    const turns = timelineToTurns(s.items);
    expect(turns).toHaveLength(2);
    expect(turns[0].query).toBe('list namespaces');
    expect(turns[0].items.map((i) => i.kind)).toEqual(['tool']);
    expect(turns[0].result?.text).toBe('No clusters');
    expect(turns[0].status).toBe('completed');
    expect(turns[1].query).toBe('aws access?');
    expect(turns[1].result).toBeUndefined();      // in-flight
    expect(turns[1].status).toBe('running');
  });
});

describe('runsToTurns', () => {
  it('maps runs (ordered by startedAt) to turns with query + result + items', () => {
    const runs: RunWithTrace[] = [
      { runId: 'b', query: 'aws access?', startedAt: '2026-01-01T00:01:00Z', status: 'failed',
        outputSummary: 'no aws', outputJson: null,
        items: [{ kind: 'tool', seq: 0, id: 'x', toolName: 'Bash', status: 'success', startedAt: 't' } as any] },
      { runId: 'a', query: 'list namespaces', startedAt: '2026-01-01T00:00:00Z', status: 'completed',
        outputSummary: 'none', outputJson: null, items: [] },
    ];
    const turns = runsToTurns(runs);
    expect(turns.map((t) => t.runId)).toEqual(['a', 'b']);   // sorted by startedAt
    expect(turns[0].query).toBe('list namespaces');
    expect(turns[1].result?.text).toBe('no aws');
    expect(turns[1].result?.success).toBe(false);
    expect(turns[1].items).toHaveLength(1);
  });
});

describe('mergeTurns', () => {
  // Reproduces the run-detail-page duplication bug: a follow-up run shares the
  // opened run's correlationId, so the poller places it in `historical` while
  // the SSE stream is still rendering the same run in `live`. While the live
  // run id is known, the historical copy must be dropped so the turn shows once.
  it('concatenates historical + live when no live run id is known (no streaming)', () => {
    const hist: Turn[] = [
      { runId: 'h1', query: 'first', items: [], status: 'completed' },
    ];
    const live: Turn[] = [
      { query: 'followup', items: [], status: 'running' },
    ];
    const merged = mergeTurns(hist, live, undefined);
    expect(merged).toHaveLength(2);
    expect(merged.map((t) => t.runId)).toEqual(['h1', undefined]);
  });

  it('drops the historical copy of the in-flight live run to avoid duplication', () => {
    const hist: Turn[] = [
      { runId: 'h1', query: 'first', items: [], status: 'completed' },
      { runId: 'live-run', query: 'followup',
        items: [{ kind: 'tool', seq: 0, id: 't', toolName: 'Bash', status: 'success', startedAt: 'x' } as any],
        status: 'running' },
    ];
    const live: Turn[] = [
      { query: 'followup',
        items: [{ kind: 'tool', seq: 0, id: 't', toolName: 'Bash', status: 'running', startedAt: 'x' } as any],
        status: 'running' },
    ];
    const merged = mergeTurns(hist, live, 'live-run');
    // historical live-run copy is dropped; only the live (in-flight) turn remains
    expect(merged).toHaveLength(2);
    expect(merged.map((t) => t.runId)).toEqual(['h1', undefined]);
    expect((merged[1].items[0] as any).status).toBe('running');
  });

  it('once liveRunId clears (stream settled + reset), history shows the run again', () => {
    const hist: Turn[] = [
      { runId: 'h1', query: 'first', items: [], status: 'completed' },
      { runId: 'live-run', query: 'followup', items: [], status: 'completed',
        result: { kind: 'result', seq: 0, text: 'done', success: true } as any },
    ];
    const merged = mergeTurns(hist, [], undefined);
    expect(merged.map((t) => t.runId)).toEqual(['h1', 'live-run']);
  });
});

describe('background agent waiting', () => {
  it('keeps runStatus running on background_waiting', () => {
    let s = initialTimelineState;
    s = applyEvent(s, {
      type: 'background_waiting',
      data: {
        pending_count: 1,
        pending_task_ids: ['bg-1'],
        label: 'Waiting on 1 background agent(s)…',
      },
    });
    expect(s.runStatus).toBe('running');
    expect(s.backgroundWaiting?.pendingCount).toBe(1);
  });

  it('completes only on result after waiting', () => {
    let s = initialTimelineState;
    s = applyEvent(s, {
      type: 'background_waiting',
      data: { pending_count: 1, pending_task_ids: ['bg-1'], label: 'Waiting…' },
    });
    s = applyEvent(s, {
      type: 'task_notification',
      data: { task_id: 'bg-1', status: 'completed', summary: 'ok' },
    });
    expect(s.runStatus).toBe('running');
    expect(s.backgroundWaiting).not.toBeNull();
    expect(s.backgroundWaiting?.pendingCount).toBe(0);
    s = applyEvent(s, {
      type: 'result',
      data: { text: 'Final findings', success: true },
    });
    expect(s.runStatus).toBe('completed');
    expect(s.backgroundWaiting).toBeNull();
  });

  it('keeps backgroundWaiting after last task_notification until result', () => {
    let s = initialTimelineState;
    s = applyEvent(s, {
      type: 'background_waiting',
      data: { pending_count: 1, pending_task_ids: ['bg-1'], label: 'Waiting…' },
    });
    s = applyEvent(s, {
      type: 'task_notification',
      data: { task_id: 'bg-1', status: 'completed', summary: 'ok' },
    });
    expect(s.runStatus).toBe('running');
    expect(s.backgroundWaiting).not.toBeNull();
    expect(s.backgroundWaiting?.pendingTaskIds).toEqual([]);
  });
});

describe('stream end while background waiting', () => {
  it('does not synthesize complete after last notification without result', async () => {
    const { shouldSynthesizeStreamEnd } = await import('./useAgentStream');
    let s = initialTimelineState;
    s = applyEvent(s, {
      type: 'background_waiting',
      data: { pending_count: 1, pending_task_ids: ['bg-1'], label: 'Waiting…' },
    });
    s = applyEvent(s, {
      type: 'task_notification',
      data: { task_id: 'bg-1', status: 'completed', summary: 'ok' },
    });
    expect(s.runStatus).toBe('running');
    expect(shouldSynthesizeStreamEnd(s)).toBe(false);
  });
});

describe('runStatus terminal transition', () => {
  it('stays running without a terminal event, then completes on synthetic result', () => {
    let state = initialTimelineState;
    // Simulate a run with thought + tool but no result event (stream closed early)
    state = applyEvent(state, ev('run_started', { run_id: 'r1', agent: 'investigator' }));
    state = applyEvent(state, ev('thought', { text: 'Checking...' }));
    state = applyEvent(state, ev('tool_start', { name: 'Bash', tool_use_id: 't1', input: {} }));
    state = applyEvent(state, ev('tool_end', { name: 'Bash', tool_use_id: 't1', success: true }));

    // Stream closed without result — runStatus is still running (this is the bug scenario)
    expect(state.runStatus).toBe('running');

    // Applying a synthetic result event is the fix — it must transition to completed
    state = applyEvent(state, ev('result', { text: '', success: true }));
    expect(state.runStatus).toBe('completed');
  });
});
