// web_ui/src/lib/agentTree.test.ts
// Pure-logic test for the nested-agent tree builder. Kept in a node-env
// .test.ts file (no DOM/testing-library needed) since buildAgentTree is a pure
// function over TimelineItem arrays.
import { describe, it, expect } from 'vitest';
import { buildAgentTree } from './agentTree';
import type { ToolItem, ThoughtItem } from './agentTimeline';

function tool(overrides: Partial<ToolItem>): ToolItem {
  return {
    kind: 'tool', seq: 0, id: 't', toolName: 'Bash', status: 'success',
    startedAt: new Date().toISOString(), depth: 0, ...overrides,
  };
}

function thought(overrides: Partial<ThoughtItem>): ThoughtItem {
  return { kind: 'thought', seq: 0, ts: new Date().toISOString(), text: 'h', depth: 0, ...overrides };
}

describe('buildAgentTree', () => {
  it('nests tool calls under their real parent at every depth, not flattened to root', () => {
    const tree = buildAgentTree([
      tool({ id: 'a', seq: 0, agentName: 'planner', depth: 0 }),
      tool({ id: 'b', seq: 1, agentName: 'investigation', agentId: 'task-1', parentAgentName: 'planner', depth: 1 }),
      tool({ id: 'c', seq: 2, agentName: 'general-purpose', agentId: 'task-2', parentAgentId: 'task-1', parentAgentName: 'investigation', depth: 2, toolName: 'get_issue.py' }),
    ]);

    expect(tree.depth).toBe(0);
    expect(tree.items.map((i) => (i as ToolItem).id)).toEqual(['a']);

    expect(tree.children).toHaveLength(1);
    const investigation = tree.children[0];
    expect(investigation.agentName).toBe('investigation');
    expect(investigation.agentId).toBe('task-1');
    expect(investigation.depth).toBe(1);
    expect(investigation.items.map((i) => (i as ToolItem).id)).toEqual(['b']);

    expect(investigation.children).toHaveLength(1);
    const grandchild = investigation.children[0];
    expect(grandchild.agentName).toBe('general-purpose');
    expect(grandchild.depth).toBe(2);
    expect(grandchild.items.map((i) => (i as ToolItem).id)).toEqual(['c']);
    expect(tree.children).toHaveLength(1);
  });

  it('attaches root-level thoughts to the root node and subagent thoughts to their node', () => {
    const tree = buildAgentTree([
      thought({ seq: 0, text: 'root think', agent: 'planner', depth: 0 }),
      tool({ id: 'b', seq: 1, agentName: 'investigation', agentId: 'task-1', parentAgentName: 'planner', depth: 1 }),
      thought({ seq: 2, text: 'sub think', agent: 'investigation', agentId: 'task-1', depth: 1 }),
    ]);
    expect(tree.items.filter((i) => i.kind === 'thought').map((i) => (i as ThoughtItem).text)).toEqual(['root think']);
    expect(tree.children[0].items.filter((i) => i.kind === 'thought').map((i) => (i as ThoughtItem).text)).toEqual(['sub think']);
  });

  it('treats items with no agent as root-level (depth 0)', () => {
    const tree = buildAgentTree([
      tool({ id: 'a', seq: 0, agentName: undefined, depth: 0 }),
    ]);
    expect(tree.children).toHaveLength(0);
    expect(tree.items.map((i) => (i as ToolItem).id)).toEqual(['a']);
  });

  it('REGRESSION: same agent type dispatched by two different parents nests each under its own real parent', () => {
    const tree = buildAgentTree([
      tool({ id: 'a', seq: 0, agentName: 'investigation-A', agentId: 'task-A', depth: 1, parentAgentName: 'sre-agent' }),
      tool({ id: 'b', seq: 1, agentName: 'general-purpose', agentId: 'task-A1', parentAgentId: 'task-A', parentAgentName: 'investigation-A', depth: 2, toolName: 'call-under-A' }),
      tool({ id: 'c', seq: 2, agentName: 'investigation-B', agentId: 'task-B', depth: 1, parentAgentName: 'sre-agent' }),
      tool({ id: 'd', seq: 3, agentName: 'general-purpose', agentId: 'task-B1', parentAgentId: 'task-B', parentAgentName: 'investigation-B', depth: 2, toolName: 'call-under-B' }),
    ]);
    const invA = tree.children.find((c) => c.agentId === 'task-A')!;
    const invB = tree.children.find((c) => c.agentId === 'task-B')!;
    expect(invA.children.map((c) => (c.items[0] as ToolItem).toolName)).toEqual(['call-under-A']);
    expect(invB.children.map((c) => (c.items[0] as ToolItem).toolName)).toEqual(['call-under-B']);
  });

  it('REGRESSION: a subagent thought before its first tool call attaches to its own node, not root', () => {
    const tree = buildAgentTree([
      thought({ seq: 0, text: 'investigation is thinking first', agent: 'investigation', agentId: 'task-1', depth: 1 }),
      tool({ id: 'b', seq: 1, agentName: 'investigation', agentId: 'task-1', parentAgentName: 'sre-agent', depth: 1, toolName: 'get_issue.py' }),
    ]);
    const inv = tree.children.find((c) => c.agentId === 'task-1');
    expect(inv?.items.map((i) => (i as ThoughtItem).text ?? (i as ToolItem).toolName)).toContain('investigation is thinking first');
    expect(tree.items.map((i) => (i as ThoughtItem).text ?? (i as ToolItem).toolName)).not.toContain('investigation is thinking first');
  });
});
