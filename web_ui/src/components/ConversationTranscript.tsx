'use client';

import { useEffect, useState } from 'react';
import {
  ChevronDown, ChevronRight, Bot, User, CheckCircle, XCircle, Loader2, Clock, Code, Brain,
} from 'lucide-react';
import InvestigationReport from '@/components/InvestigationReport';
import MarkdownFallback from '@/components/MarkdownFallback';
import TodoProgressPanel from '@/components/TodoProgressPanel';
import type { Turn, ToolItem, ThoughtItem, BackgroundWaitingState } from '@/lib/agentTimeline';
import { buildAgentTree, type AgentNode } from '@/lib/agentTree';
import { humanizeToolSummary, nestBashUnderSkills } from '@/lib/toolDisplay';
import { earlierThoughtCount, splitLatestThought } from '@/lib/thinkingDisplay';
import { shouldCollapseTurnTree } from '@/lib/turnCollapse';
import { deriveTodoSnapshot, isTodoTool } from '@/lib/todoSnapshot';

const statusIcon = (status: string) => {
  switch (status) {
    case 'success': return <CheckCircle className="w-3.5 h-3.5 text-green-500" />;
    case 'error': return <XCircle className="w-3.5 h-3.5 text-clay" />;
    case 'running': return <Loader2 className="w-3.5 h-3.5 text-forest animate-spin" />;
    default: return <Clock className="w-3.5 h-3.5 text-stone-400" />;
  }
};

const fmtDuration = (ms?: number) => (!ms ? '-' : ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`);

// Left-bar accent colors per agent. Restricted to the OpenSRE theme palette
// (forest / clay / stone) so the nesting reads as an elegant green gradient
// from root → subagent → leaf, with clay reserved for infra-style agents and
// stone for generic/utility agents. Avoids off-theme hues (purple, pink, etc.).
const AGENT_COLORS: Record<string, string> = {
  // Root orchestrators — deepest forest, the outermost nesting bar.
  'sre-agent': 'border-l-forest-dark',
  planner: 'border-l-forest-dark',
  // Specialist subagents — mid forest.
  investigation: 'border-l-forest',
  kubernetes: 'border-l-forest',
  k8s: 'border-l-forest',
  metrics: 'border-l-forest',
  log_analysis: 'border-l-forest',
  // Infra/cloud agents — clay accent (the only non-green, kept for contrast).
  aws: 'border-l-clay',
  // Generic / utility agents — neutral stone so they recede.
  'general-purpose': 'border-l-stone-400',
  github: 'border-l-stone-500',
  coding: 'border-l-stone-500',
  traces: 'border-l-stone-400',
};

function ToolInput({ call }: { call: ToolItem }) {
  const input = call.input;
  if (!input || Object.keys(input).length === 0) return null;
  if (call.toolName === 'Bash' && input.command) {
    return (
      <pre className="text-xs bg-stone-100 dark:bg-stone-800 p-2 rounded overflow-x-auto max-h-48 overflow-y-auto font-mono text-stone-700 dark:text-stone-300">
        <span className="text-green-600 dark:text-green-400">$ </span>{String(input.command)}
      </pre>
    );
  }
  if ((call.toolName === 'Read' || call.toolName === 'Write' || call.toolName === 'Edit') && input.file_path) {
    return <div className="text-xs font-mono text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-stone-800 p-2 rounded">{String(input.file_path)}</div>;
  }
  if ((call.toolName === 'Task' || call.toolName === 'Agent') && input.description) {
    return (
      <div className="text-xs space-y-1">
        {input.subagent_type ? <span className="inline-block px-2 py-0.5 rounded-full bg-forest-light/15 dark:bg-forest/20 text-forest-dark dark:text-forest-light font-medium">{String(input.subagent_type)}</span> : null}
        <p className="text-stone-700 dark:text-stone-300">{String(input.description)}</p>
      </div>
    );
  }
  // Todo / Task tools: render a compact, human-readable delta instead of raw JSON.
  // The full snapshot is shown in the TodoProgressPanel below the trace; here we
  // only summarize what this individual call changed.
  if (isTodoTool(call.toolName)) {
    const todos = Array.isArray(input.todos) ? input.todos : null;
    if (call.toolName === 'TodoWrite' && todos) {
      return (
        <ul className="text-xs space-y-0.5">
          {todos.map((t: Record<string, unknown>, i: number) => {
            const status = (t.status ?? 'pending') as string;
            const icon = status === 'completed' ? '✅' : status === 'in_progress' ? '🔧' : '○';
            return (
              <li key={i} className="font-mono text-stone-700 dark:text-stone-300">
                {icon} {String(t.activeForm ?? t.content ?? '').slice(0, 120)}
              </li>
            );
          })}
        </ul>
      );
    }
    if (call.toolName === 'TaskCreate') {
      return <p className="text-xs text-stone-700 dark:text-stone-300">+ {String(input.subject ?? '')}</p>;
    }
    if (call.toolName === 'TaskUpdate') {
      const id = (input.taskId ?? input.id ?? input.task_id) as string | undefined;
      return (
        <p className="text-xs text-stone-700 dark:text-stone-300">
          {id ? <span className="font-mono">{String(id).slice(0, 12)}</span> : null}
          {input.status ? <span className="ml-2">→ {String(input.status)}</span> : null}
          {input.subject ? <span className="ml-2">{String(input.subject).slice(0, 100)}</span> : null}
        </p>
      );
    }
    if (call.toolName === 'TaskList') return <p className="text-xs text-stone-500">snapshot request</p>;
    if (call.toolName === 'TaskGet') return <p className="text-xs text-stone-500">read task</p>;
  }
  return (
    <pre className="text-xs bg-stone-100 dark:bg-stone-800 p-2 rounded overflow-x-auto max-h-32 overflow-y-auto font-mono text-stone-700 dark:text-stone-300">
      {JSON.stringify(input, null, 2)}
    </pre>
  );
}

function ToolRow({
  call,
  technicalDetails,
  nestedBash,
}: {
  call: ToolItem;
  technicalDetails: boolean;
  nestedBash?: ToolItem[];
}) {
  const [open, setOpen] = useState(false);
  const color = AGENT_COLORS[call.agentName || ''] || 'border-l-stone-400';
  const summary = humanizeToolSummary(call, { technicalDetails });
  return (
    <div className={`border-b border-stone-100 dark:border-stone-700 last:border-b-0 border-l-2 ${color}`}>
      <div className="px-3 py-2 flex items-center gap-3 cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50" onClick={() => setOpen(!open)}>
        <div className="flex-shrink-0">{open ? <ChevronDown className="w-4 h-4 text-stone-400" /> : <ChevronRight className="w-4 h-4 text-stone-400" />}</div>
        <div className="flex-shrink-0">{statusIcon(call.status)}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-stone-900 dark:text-white">{call.toolName}</span>
          </div>
          {summary ? <div className="text-xs text-stone-500 dark:text-stone-400 font-mono truncate mt-0.5">{summary}</div> : null}
        </div>
        <div className="flex-shrink-0 text-xs text-stone-400">{fmtDuration(call.durationMs)}</div>
      </div>
      {open && (
        <div className="px-3 pb-3 pt-1 bg-stone-50 dark:bg-stone-900 border-t border-stone-100 dark:border-stone-700">
          {call.input && Object.keys(call.input).length > 0 && (
            <div className="mb-3"><div className="text-xs font-medium text-stone-500 mb-1 flex items-center gap-1"><Code className="w-3 h-3" />Input</div><ToolInput call={call} /></div>
          )}
          {call.output && (
            <div className="mb-3"><div className="text-xs font-medium text-stone-500 mb-1 flex items-center gap-1"><Code className="w-3 h-3" />Output</div>
              <pre className="text-xs bg-stone-100 dark:bg-stone-800 p-2 rounded overflow-x-auto max-h-96 overflow-y-auto font-mono text-stone-700 dark:text-stone-300 whitespace-pre-wrap">{call.output}</pre>
            </div>
          )}
          {call.error && (
            <div className="mb-3"><div className="text-xs font-medium text-clay mb-1">Error</div>
              <pre className="text-xs bg-clay-light/10 dark:bg-clay/20 p-2 rounded text-clay-dark dark:text-clay-light whitespace-pre-wrap">{call.error}</pre>
            </div>
          )}
          {nestedBash && nestedBash.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-medium text-stone-500 mb-1">Commands</div>
              <div className="border border-stone-200 dark:border-stone-600 rounded overflow-hidden">
                {nestedBash.map((bash) => (
                  <ToolRow key={bash.id} call={bash} technicalDetails={technicalDetails} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ThinkingBlock({ thoughts }: { thoughts: ThoughtItem[] }) {
  const [open, setOpen] = useState(false);
  if (thoughts.length === 0) return null;
  const { latest } = splitLatestThought(thoughts);
  const earlierCount = earlierThoughtCount(thoughts);
  if (!latest) return null;
  return (
    <div className="border-b border-stone-100 dark:border-stone-700 last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        className="w-full text-left px-3 py-1.5 flex items-start gap-2 cursor-pointer hover:bg-amber-50/50 dark:hover:bg-amber-900/10"
        onClick={() => setOpen(!open)}
        data-testid="thinking-block"
      >
        <div className="flex-shrink-0 mt-0.5">
          {open ? (
            <ChevronDown className="w-3.5 h-3.5 text-amber-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-amber-400" />
          )}
        </div>
        <Brain className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
        {open ? (
          <div className="flex-1 min-w-0 space-y-1.5">
            <p className="text-[11px] text-stone-400">
              Thinking · {thoughts.length} step{thoughts.length === 1 ? '' : 's'}
            </p>
            {thoughts.map((t, i) => (
              <p
                key={i}
                className={`text-xs leading-relaxed ${
                  i === thoughts.length - 1
                    ? 'text-stone-600 dark:text-stone-300'
                    : 'text-stone-500 dark:text-stone-400 italic'
                }`}
              >
                {t.text}
              </p>
            ))}
          </div>
        ) : (
          <div className="flex-1 min-w-0">
            <p className="text-[11px] text-stone-400 mb-0.5">
              Thinking · latest
              {earlierCount > 0 ? (
                <span className="text-stone-400">
                  {' '}
                  · {earlierCount} earlier ▸
                </span>
              ) : null}
            </p>
            <p className="text-xs text-stone-600 dark:text-stone-400 italic leading-relaxed whitespace-pre-wrap">
              {latest.text}
            </p>
          </div>
        )}
      </button>
    </div>
  );
}

type TimelineTraceItem = ToolItem | ThoughtItem;

// Recursive renderer for one agent invocation: its own thoughts + tool calls,
// then each nested subagent invocation as an indented, collapsible child group.
// Replaces the old flat groupByAgent bucket — attribution is now conveyed by
// the tree structure itself (which AgentGroup a row is nested under), not a
// per-row "via <agent>" label.
function AgentGroup({ node, technicalDetails }: { node: AgentNode; technicalDetails: boolean }) {
  const [open, setOpen] = useState(true);
  const displayItems = nestBashUnderSkills(node.items, { technicalDetails });
  const thoughts = displayItems.filter((i): i is ThoughtItem => i.kind === 'thought');
  const tools = displayItems.filter((i): i is ToolItem & { nestedBash?: ToolItem[] } => i.kind === 'tool');
  const color = AGENT_COLORS[node.agentName] || 'border-l-stone-400';
  return (
    <div data-testid="agent-tree-node" data-depth={node.depth} className={`border-l-2 ${color}`} style={{ marginLeft: node.depth * 16 }}>
      <div
        className="px-3 py-2 bg-stone-50 dark:bg-stone-700 border-b border-stone-200 dark:border-stone-600 flex items-center gap-2 cursor-pointer hover:bg-stone-100 dark:hover:bg-stone-700/70"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown className="w-4 h-4 text-stone-400" /> : <ChevronRight className="w-4 h-4 text-stone-400" />}
        <Bot className="w-4 h-4 text-stone-500" />
        <span className="text-sm font-medium text-stone-700 dark:text-stone-300">{node.agentName.replace(/_/g, ' ')}</span>
      </div>
      {open && (
        <div className="bg-white dark:bg-stone-800">
          <ThinkingBlock thoughts={thoughts} />
          {tools.map((t) => (
            <ToolRow
              key={t.id}
              call={t}
              technicalDetails={technicalDetails}
              nestedBash={t.nestedBash?.length ? t.nestedBash : undefined}
            />
          ))}
          {node.children.map((child) => (
            <AgentGroup key={child.agentId ?? child.agentName} node={child} technicalDetails={technicalDetails} />
          ))}
        </div>
      )}
    </div>
  );
}

function AgentTrace({ items, technicalDetails }: { items: TimelineTraceItem[]; technicalDetails: boolean }) {
  if (items.length === 0) return null;
  const tree = buildAgentTree(items);
  return (
    <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-600 overflow-hidden">
      <AgentGroup node={tree} technicalDetails={technicalDetails} />
    </div>
  );
}

function TurnBlock({
  turn,
  todoTools,
  index,
  turns,
  technicalDetails,
  backgroundWaiting,
}: {
  turn: Turn;
  todoTools: ToolItem[];
  index: number;
  turns: Turn[];
  technicalDetails: boolean;
  backgroundWaiting?: BackgroundWaitingState | null;
}) {
  const collapse = shouldCollapseTurnTree(turn, index, turns, { technicalDetails });
  const [treeOpen, setTreeOpen] = useState(!collapse);
  useEffect(() => { setTreeOpen(!collapse); }, [collapse]);

  const traceItems = turn.items.filter((i): i is TimelineTraceItem => i.kind === 'tool' || i.kind === 'thought');
  const stepCount = traceItems.length;
  // Task tools accumulate across the session (unlike TodoWrite full snapshots).
  // todoTools is cumulative from prior turns through this one.
  const todos = deriveTodoSnapshot(todoTools);
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2">
        <div className="w-7 h-7 rounded-full bg-stone-200 dark:bg-stone-700 flex items-center justify-center flex-shrink-0"><User className="w-4 h-4 text-stone-600 dark:text-stone-300" /></div>
        <p className="text-sm font-medium text-stone-900 dark:text-white pt-1 whitespace-pre-wrap">{turn.query}</p>
      </div>
      <div className="pl-9 space-y-3">
        {collapse && !treeOpen ? (
          <button
            type="button"
            className="text-xs text-stone-500 dark:text-stone-400 hover:text-stone-700 dark:hover:text-stone-300"
            onClick={() => setTreeOpen(true)}
          >
            Agent activity ({stepCount} step{stepCount === 1 ? '' : 's'}) ▸
          </button>
        ) : (
          <>
            {collapse && (
              <button
                type="button"
                className="text-xs text-stone-500 dark:text-stone-400 hover:text-stone-700 dark:hover:text-stone-300 mb-1"
                onClick={() => setTreeOpen(false)}
              >
                Hide agent activity ▾
              </button>
            )}
            <AgentTrace items={traceItems} technicalDetails={technicalDetails} />
          </>
        )}
        {backgroundWaiting ? (
          <p
            aria-live="polite"
            data-testid="background-waiting-label"
            className="flex items-center gap-2 text-sm text-stone-500 dark:text-stone-400"
          >
            <Loader2 className="w-4 h-4 animate-spin text-forest shrink-0" />
            {backgroundWaiting.label}
          </p>
        ) : null}
        {todos.length > 0 && <TodoProgressPanel todos={todos} />}
        {turn.status === 'running' && !turn.result && !backgroundWaiting && (
          <div className="flex items-center gap-2 text-sm text-stone-400"><Loader2 className="w-4 h-4 animate-spin text-forest" /> Working…</div>
        )}
        {turn.result && (
          turn.result.structuredReport
            ? <InvestigationReport report={turn.result.structuredReport} />
            : <MarkdownFallback content={turn.result.text} />
        )}
      </div>
    </div>
  );
}

export default function ConversationTranscript({
  turns,
  isRunning,
  technicalDetails = false,
  backgroundWaiting = null,
}: {
  turns: Turn[];
  isRunning?: boolean;
  technicalDetails?: boolean;
  backgroundWaiting?: BackgroundWaitingState | null;
}) {
  if (turns.length === 0) {
    return <p className="text-sm text-stone-400 py-3">{isRunning ? 'Waiting for the agent…' : 'No activity yet.'}</p>;
  }
  const turnsWithTodos = turns.reduce<{ turn: Turn; todoTools: ToolItem[] }[]>((acc, turn) => {
    const prev = acc.length ? acc[acc.length - 1].todoTools : [];
    const todoTools = [
      ...prev,
      ...turn.items.filter((i): i is ToolItem => i.kind === 'tool' && isTodoTool(i.toolName)),
    ];
    acc.push({ turn, todoTools });
    return acc;
  }, []);
  return (
    <div className="space-y-6 divide-y divide-stone-100 dark:divide-stone-800">
      {turnsWithTodos.map(({ turn, todoTools }, i) => (
        <div key={turn.runId ?? i} className={i > 0 ? 'pt-6' : ''}>
          <TurnBlock
            turn={turn}
            todoTools={todoTools}
            index={i}
            turns={turns}
            technicalDetails={technicalDetails}
            backgroundWaiting={i === turnsWithTodos.length - 1 ? backgroundWaiting : null}
          />
        </div>
      ))}
    </div>
  );
}
