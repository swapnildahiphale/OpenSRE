'use client';

import { useEffect, useState } from 'react';
import {
  ChevronDown, ChevronRight, Bot, User, XCircle, Clock, Code, Brain,
} from 'lucide-react';
import InvestigationReport from '@/components/InvestigationReport';
import MarkdownFallback from '@/components/MarkdownFallback';
import TodoProgressPanel from '@/components/TodoProgressPanel';
import { OpenSreBrandLogo } from '@/components/brand/OpenSreBrandLogo';
import { SuccessCheck } from '@/components/ui-flow/SuccessCheck';
import type { Turn, ToolItem, ThoughtItem, BackgroundWaitingState } from '@/lib/agentTimeline';
import { buildAgentTree, type AgentNode } from '@/lib/agentTree';
import { humanizeToolSummary, nestBashUnderSkills } from '@/lib/toolDisplay';
import { earlierThoughtCount, splitLatestThought } from '@/lib/thinkingDisplay';
import { shouldCollapseTurnTree } from '@/lib/turnCollapse';
import { deriveTodoSnapshot, isTodoTool } from '@/lib/todoSnapshot';

const statusIcon = (status: string) => {
  switch (status) {
    case 'success':
      // w-3 — mockup tick weight (Phosphor filled path via SuccessCheck)
      return <SuccessCheck className="w-3 h-3 text-emerald-600 shrink-0" />;
    case 'error':
      return <XCircle className="w-3 h-3 text-rose-500 shrink-0" strokeWidth={1.75} />;
    case 'running':
      return (
        <span className="live-dot w-2 h-2 rounded-full shrink-0" aria-hidden="true" />
      );
    default:
      return <Clock className="w-3 h-3 text-slate-400 shrink-0" strokeWidth={1.75} />;
  }
};

const fmtDuration = (ms?: number) => (!ms ? '—' : ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`);

// Emerald gradient for agent nesting depth; slate for generic/utility agents.
const AGENT_COLORS: Record<string, string> = {
  'sre-agent': 'border-l-emerald-800',
  planner: 'border-l-emerald-800',
  investigation: 'border-l-emerald-700',
  kubernetes: 'border-l-emerald-600',
  k8s: 'border-l-emerald-600',
  metrics: 'border-l-emerald-600',
  log_analysis: 'border-l-emerald-600',
  aws: 'border-l-emerald-500',
  'general-purpose': 'border-l-slate-400',
  github: 'border-l-slate-500',
  coding: 'border-l-slate-500',
  traces: 'border-l-slate-400',
};

const TOOL_BORDER = 'border-l-emerald-600';

function ToolInput({ call }: { call: ToolItem }) {
  const input = call.input;
  if (!input || Object.keys(input).length === 0) return null;
  if (call.toolName === 'Bash' && input.command) {
    return (
      <pre className="text-xs bg-slate-100 dark:bg-stone-800 p-2 rounded overflow-x-auto max-h-48 overflow-y-auto font-mono text-slate-700 dark:text-stone-300">
        <span className="text-emerald-600 dark:text-emerald-400">$ </span>{String(input.command)}
      </pre>
    );
  }
  if ((call.toolName === 'Read' || call.toolName === 'Write' || call.toolName === 'Edit') && input.file_path) {
    return <div className="text-xs font-mono text-slate-700 dark:text-stone-300 bg-slate-100 dark:bg-stone-800 p-2 rounded">{String(input.file_path)}</div>;
  }
  if ((call.toolName === 'Task' || call.toolName === 'Agent') && input.description) {
    return (
      <div className="text-xs space-y-1">
        {input.subagent_type ? <span className="inline-block px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-900/20 text-emerald-800 dark:text-emerald-300 font-medium">{String(input.subagent_type)}</span> : null}
        <p className="text-slate-700 dark:text-stone-300">{String(input.description)}</p>
      </div>
    );
  }
  if (isTodoTool(call.toolName)) {
    const todos = Array.isArray(input.todos) ? input.todos : null;
    if (call.toolName === 'TodoWrite' && todos) {
      return (
        <ul className="text-xs space-y-0.5">
          {todos.map((t: Record<string, unknown>, i: number) => {
            const st = (t.status ?? 'pending') as string;
            const icon = st === 'completed' ? '✅' : st === 'in_progress' ? '🔧' : '○';
            return (
              <li key={i} className="font-mono text-slate-700 dark:text-stone-300">
                {icon} {String(t.activeForm ?? t.content ?? '').slice(0, 120)}
              </li>
            );
          })}
        </ul>
      );
    }
    if (call.toolName === 'TaskCreate') {
      return <p className="text-xs text-slate-700 dark:text-stone-300">+ {String(input.subject ?? '')}</p>;
    }
    if (call.toolName === 'TaskUpdate') {
      const id = (input.taskId ?? input.id ?? input.task_id) as string | undefined;
      return (
        <p className="text-xs text-slate-700 dark:text-stone-300">
          {id ? <span className="font-mono">{String(id).slice(0, 12)}</span> : null}
          {input.status ? <span className="ml-2">→ {String(input.status)}</span> : null}
          {input.subject ? <span className="ml-2">{String(input.subject).slice(0, 100)}</span> : null}
        </p>
      );
    }
    if (call.toolName === 'TaskList') return <p className="text-xs text-slate-500">snapshot request</p>;
    if (call.toolName === 'TaskGet') return <p className="text-xs text-slate-500">read task</p>;
  }
  return (
    <pre className="text-xs bg-slate-100 dark:bg-stone-800 p-2 rounded overflow-x-auto max-h-32 overflow-y-auto font-mono text-slate-700 dark:text-stone-300">
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
  const color = AGENT_COLORS[call.agentName || ''] || TOOL_BORDER;
  const summary = humanizeToolSummary(call, { technicalDetails });
  return (
    <div className={`border-b border-slate-100 dark:border-stone-700 last:border-b-0 border-l-2 ${color}`}>
      <div
        className="px-3 py-2 flex items-center gap-3 cursor-pointer hover:bg-slate-50 dark:hover:bg-stone-800/50"
        onClick={() => setOpen(!open)}
      >
        <div className="flex-shrink-0">{open ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}</div>
        <div className="flex-shrink-0">{statusIcon(call.status)}</div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-slate-900 dark:text-white">{call.toolName}</div>
          {summary ? <div className="text-xs text-slate-500 dark:text-stone-400 font-mono truncate mt-0.5">{summary}</div> : null}
        </div>
        <div className="flex-shrink-0 text-xs text-slate-400 tabular-nums">{fmtDuration(call.durationMs)}</div>
      </div>
      {open && (
        <div className="px-3 pb-3 pt-1 bg-slate-50 dark:bg-stone-900 border-t border-slate-100 dark:border-stone-700">
          {call.input && Object.keys(call.input).length > 0 && (
            <div className="mb-3"><div className="text-xs font-medium text-slate-500 mb-1 flex items-center gap-1"><Code className="w-3 h-3" />Input</div><ToolInput call={call} /></div>
          )}
          {call.output && (
            <div className="mb-3"><div className="text-xs font-medium text-slate-500 mb-1 flex items-center gap-1"><Code className="w-3 h-3" />Output</div>
              <pre className="text-xs bg-slate-100 dark:bg-stone-800 p-2 rounded overflow-x-auto max-h-96 overflow-y-auto font-mono text-slate-700 dark:text-stone-300 whitespace-pre-wrap">{call.output}</pre>
            </div>
          )}
          {call.error && (
            <div className="mb-3"><div className="text-xs font-medium text-rose-600 mb-1">Error</div>
              <pre className="text-xs bg-rose-50 dark:bg-rose-900/20 p-2 rounded text-rose-700 dark:text-rose-300 whitespace-pre-wrap">{call.error}</pre>
            </div>
          )}
          {nestedBash && nestedBash.length > 0 && (
            <div className="mt-3 ml-6 border-l border-slate-200 dark:border-stone-600">
              {nestedBash.map((bash) => (
                <ToolRow key={bash.id} call={bash} technicalDetails={technicalDetails} />
              ))}
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
    <div className="border-b border-slate-100 dark:border-stone-700 last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        className="w-full text-left px-3 py-2 flex items-start gap-2 cursor-pointer hover:bg-amber-50/50 dark:hover:bg-amber-900/10"
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
            <p className="text-[11px] text-slate-400">
              Thinking · {thoughts.length} step{thoughts.length === 1 ? '' : 's'}
            </p>
            {thoughts.map((t, i) => (
              <p
                key={i}
                className={`text-xs leading-relaxed ${
                  i === thoughts.length - 1
                    ? 'text-slate-600 dark:text-stone-300'
                    : 'text-slate-500 dark:text-stone-400 italic'
                }`}
              >
                {t.text}
              </p>
            ))}
          </div>
        ) : (
          <div className="flex-1 min-w-0">
            <p className="text-[11px] text-slate-400 mb-0.5">
              Thinking · latest
              {earlierCount > 0 ? (
                <span className="text-slate-400">
                  {' '}
                  · {earlierCount} earlier ▸
                </span>
              ) : null}
            </p>
            <p className="text-xs text-slate-600 dark:text-stone-400 italic leading-relaxed whitespace-pre-wrap">
              {latest.text}
            </p>
          </div>
        )}
      </button>
    </div>
  );
}

type TimelineTraceItem = ToolItem | ThoughtItem;

function AgentGroup({ node, technicalDetails }: { node: AgentNode; technicalDetails: boolean }) {
  const [open, setOpen] = useState(true);
  const displayItems = nestBashUnderSkills(node.items, { technicalDetails });
  const thoughts = displayItems.filter((i): i is ThoughtItem => i.kind === 'thought');
  const tools = displayItems.filter((i): i is ToolItem & { nestedBash?: ToolItem[] } => i.kind === 'tool');
  const color = AGENT_COLORS[node.agentName] || 'border-l-emerald-800';
  return (
    <div data-testid="agent-tree-node" data-depth={node.depth} className={`border-l-2 ${color}`} style={{ marginLeft: node.depth * 16 }}>
      <div
        className="px-3 py-2 bg-slate-50 dark:bg-stone-700 border-b border-slate-200 dark:border-stone-600 flex items-center gap-2 cursor-pointer hover:bg-slate-100 dark:hover:bg-stone-700/70"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
        <Bot className="w-4 h-4 text-slate-500" />
        <span className="text-sm font-medium text-slate-700 dark:text-stone-300">{node.agentName.replace(/_/g, ' ')}</span>
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
    <div className="rounded-xl border border-slate-200/80 dark:border-stone-600 bg-white dark:bg-stone-800 overflow-hidden">
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
  const todos = deriveTodoSnapshot(todoTools);
  return (
    <div className="space-y-4">
      {/* User message — right-aligned with avatar */}
      <div className="flex items-start justify-end gap-2.5">
        <div className="max-w-[min(100%,42rem)] rounded-2xl rounded-tr-md bg-slate-100/90 dark:bg-stone-700/80 px-3.5 py-2.5">
          <p className="text-sm font-medium text-slate-900 dark:text-white whitespace-pre-wrap leading-relaxed">
            {turn.query}
          </p>
        </div>
        <div
          className="w-7 h-7 rounded-full bg-slate-200 dark:bg-stone-700 flex items-center justify-center flex-shrink-0"
          aria-label="You"
          title="You"
        >
          <User className="w-4 h-4 text-slate-600 dark:text-stone-300" />
        </div>
      </div>

      {/* OpenSRE reply — left-aligned with spinner logo */}
      <div className="flex items-start gap-2.5">
        <div
          className="w-7 h-7 rounded-full bg-white dark:bg-stone-800 border border-slate-200/80 dark:border-stone-600 flex items-center justify-center flex-shrink-0 overflow-hidden"
          aria-label="OpenSRE"
          title="OpenSRE"
        >
          <OpenSreBrandLogo variant="spinner" surface="avatar" />
        </div>
        <div className="flex-1 min-w-0 space-y-3">
          {collapse && !treeOpen ? (
            <button
              type="button"
              className="text-xs text-slate-500 dark:text-stone-400 hover:text-slate-700 dark:hover:text-stone-300 transition-colors"
              onClick={() => setTreeOpen(true)}
            >
              Agent activity ({stepCount} step{stepCount === 1 ? '' : 's'}) ▸
            </button>
          ) : (
            <>
              {collapse && (
                <button
                  type="button"
                  className="text-xs text-slate-500 dark:text-stone-400 hover:text-slate-700 dark:hover:text-stone-300 transition-colors mb-1"
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
              className="flex items-center gap-2 text-sm text-slate-500 dark:text-stone-400"
            >
              <span className="live-dot w-2.5 h-2.5 rounded-full shrink-0" aria-hidden="true" />
              {backgroundWaiting.label}
            </p>
          ) : null}
          {todos.length > 0 && <TodoProgressPanel todos={todos} />}
          {turn.status === 'running' && !turn.result && !backgroundWaiting && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <span className="live-dot w-2.5 h-2.5 rounded-full" aria-hidden="true" />
              Working…
            </div>
          )}
          {turn.result && (
            turn.result.structuredReport
              ? <InvestigationReport report={turn.result.structuredReport} />
              : <MarkdownFallback content={turn.result.text} />
          )}
        </div>
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
    return <p className="text-sm text-slate-400 py-3">{isRunning ? 'Waiting for the agent…' : 'No activity yet.'}</p>;
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
    <div className="space-y-8 divide-y divide-slate-100 dark:divide-stone-800">
      {turnsWithTodos.map(({ turn, todoTools }, i) => (
        <div key={turn.runId ?? i} className={i > 0 ? 'pt-8' : ''}>
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
