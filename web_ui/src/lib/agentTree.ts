// web_ui/src/lib/agentTree.ts
// Pure nested-agent tree builder for the conversation transcript.
//
// Node identity is the STABLE invocation id (agentId — the tool_use_id of the
// Task/Agent dispatch that spawned this subagent), not the agent type name.
// Agent type names (e.g. "general-purpose") are reused across unrelated
// dispatches within a run (confirmed live: the SDK also reuses its own opaque
// agent_id across unrelated dispatches — see agent.py's _resolve_agent). Only
// the dispatching tool_use_id is guaranteed unique, so it's the tree key.
//
// Kept as a pure, DOM-free function in src/lib so it can be unit-tested in the
// node vitest environment alongside agentTimeline.test.ts.
import type { ToolItem, ThoughtItem } from './agentTimeline';

export interface AgentNode {
  agentName: string;
  // Stable invocation id. undefined only for the synthetic root node (root has
  // no dispatching tool_use_id).
  agentId?: string;
  depth: number;
  // This agent invocation's own rows: its thoughts + the tool calls it ran
  // directly (not the calls made by its nested subagents — those go under
  // `children`).
  items: (ToolItem | ThoughtItem)[];
  // Nested agent invocations dispatched by this agent, in arrival order.
  children: AgentNode[];
}

type TraceItem = ToolItem | ThoughtItem;

function itemAgentId(it: TraceItem): string | undefined {
  return it.kind === 'tool' ? it.agentId : it.agentId;
}
function itemAgentName(it: TraceItem): string {
  return (it.kind === 'tool' ? it.agentName : it.agent) || 'sre-agent';
}
function itemParentAgentId(it: TraceItem): string | undefined {
  return it.kind === 'tool' ? it.parentAgentId : it.parentAgentId;
}

/**
 * Build a recursive agent tree from a flat, seq-ordered list of timeline items.
 *
 * Attribution rules:
 * - depth 0 (or no agentId) => root's own row.
 * - depth >= 1 => belongs to the node identified by `agentId`. The node is
 *   created once per agentId (never per name — the same agent type can be
 *   dispatched more than once, by different parents, within one run) and
 *   attached under the parent node identified by `parentAgentId`. If the
 *   parent node hasn't been seen yet, falls back to root so the row is never
 *   lost (this can happen if a parent's own first item hasn't arrived yet,
 *   e.g. out-of-order live-stream delivery of a rare edge case).
 */
export function buildAgentTree(items: TraceItem[]): AgentNode {
  const root: AgentNode = { agentName: 'sre-agent', depth: 0, items: [], children: [] };
  // One node per stable invocation id (agentId), never per agent name.
  const nodesById = new Map<string, AgentNode>();

  for (const it of [...items].sort((a, b) => a.seq - b.seq)) {
    const agentId = itemAgentId(it);
    const depth = it.depth;

    if (depth === 0 || !agentId) {
      root.items.push(it);
      continue;
    }

    let node = nodesById.get(agentId);
    if (!node) {
      node = { agentName: itemAgentName(it), agentId, depth, items: [], children: [] };
      nodesById.set(agentId, node);
      const parentId = itemParentAgentId(it);
      const parentNode = (parentId && nodesById.get(parentId)) || root;
      parentNode.children.push(node);
    }
    node.items.push(it);
  }
  return root;
}
