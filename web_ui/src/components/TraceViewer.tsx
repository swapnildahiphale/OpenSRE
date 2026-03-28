'use client';

import { useState, useEffect } from 'react';
import { apiFetch } from '@/lib/apiClient';
import {
  ChevronDown,
  ChevronRight,
  Wrench,
  Bot,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  Code,
  Brain,
} from 'lucide-react';

interface ToolCall {
  id: string;
  toolName: string;
  agentName?: string;
  parentAgent?: string;
  toolInput?: Record<string, any>;
  toolOutput?: string;
  startedAt: string;
  durationMs?: number;
  status: string;
  errorMessage?: string;
  sequenceNumber: number;
}

interface Thought {
  text: string;
  ts: string;
  seq: number;
  agent?: string;
}

interface TraceData {
  runId: string;
  toolCalls: ToolCall[];
  thoughts?: Thought[];
  total: number;
}

interface TraceViewerProps {
  runId: string;
  correlationId: string;
  isRunning?: boolean;
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'success':
      return <CheckCircle className="w-3.5 h-3.5 text-green-500" />;
    case 'error':
      return <XCircle className="w-3.5 h-3.5 text-clay" />;
    case 'running':
      return <Loader2 className="w-3.5 h-3.5 text-forest animate-spin" />;
    default:
      return <Clock className="w-3.5 h-3.5 text-stone-400" />;
  }
};

const formatDuration = (ms?: number) => {
  if (!ms) return '-';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

function getToolSummary(call: ToolCall): string | null {
  const input = call.toolInput;
  if (!input) return null;
  switch (call.toolName) {
    case 'Bash':
      return input.command ? String(input.command).substring(0, 120) : null;
    case 'Skill':
      return input.skill
        ? `skill: ${input.skill}${input.args ? ` — ${String(input.args).substring(0, 80)}` : ''}`
        : null;
    case 'Read':
    case 'Write':
    case 'Edit':
      return input.file_path ? String(input.file_path) : null;
    case 'Grep':
      return input.pattern
        ? `pattern: "${input.pattern}"${input.path ? ` in ${input.path}` : ''}`
        : null;
    case 'Glob':
      return input.pattern ? `glob: "${input.pattern}"` : null;
    case 'Task':
      return input.description
        ? `${input.subagent_type || 'subagent'}: ${String(input.description).substring(0, 100)}`
        : null;
    default: {
      const firstVal = Object.values(input).find((v) => typeof v === 'string');
      return firstVal ? String(firstVal).substring(0, 100) : null;
    }
  }
}

function renderToolInput(call: ToolCall) {
  const input = call.toolInput;
  if (!input || Object.keys(input).length === 0) return null;

  switch (call.toolName) {
    case 'Bash':
      if (input.command) {
        return (
          <pre className="text-xs bg-stone-100 dark:bg-stone-800 p-2 rounded overflow-x-auto max-h-48 overflow-y-auto font-mono text-stone-700 dark:text-stone-300">
            <span className="text-green-600 dark:text-green-400">$ </span>
            {String(input.command)}
          </pre>
        );
      }
      break;
    case 'Skill':
      if (input.skill) {
        return (
          <div className="text-xs space-y-1">
            <span className="inline-block px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 font-medium">
              {input.skill}
            </span>
            {input.args && (
              <pre className="bg-stone-100 dark:bg-stone-800 p-2 rounded font-mono text-stone-700 dark:text-stone-300 whitespace-pre-wrap">
                {String(input.args)}
              </pre>
            )}
          </div>
        );
      }
      break;
    case 'Read':
    case 'Write':
    case 'Edit':
      if (input.file_path) {
        return (
          <div className="text-xs font-mono text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-stone-800 p-2 rounded">
            {String(input.file_path)}
            {input.offset && <span className="text-stone-400 ml-2">offset: {input.offset}</span>}
            {input.limit && <span className="text-stone-400 ml-2">limit: {input.limit}</span>}
          </div>
        );
      }
      break;
    case 'Grep':
    case 'Glob':
      if (input.pattern) {
        return (
          <div className="text-xs font-mono bg-stone-100 dark:bg-stone-800 p-2 rounded space-y-1">
            <div>
              <span className="text-stone-400">pattern: </span>
              <span className="text-amber-600 dark:text-amber-400">{input.pattern}</span>
            </div>
            {input.path && (
              <div>
                <span className="text-stone-400">path: </span>
                <span className="text-stone-700 dark:text-stone-300">{input.path}</span>
              </div>
            )}
            {input.glob && (
              <div>
                <span className="text-stone-400">glob: </span>
                <span className="text-stone-700 dark:text-stone-300">{input.glob}</span>
              </div>
            )}
          </div>
        );
      }
      break;
    case 'Task':
      if (input.description) {
        return (
          <div className="text-xs space-y-1">
            {input.subagent_type && (
              <span className="inline-block px-2 py-0.5 rounded-full bg-forest-light/15 dark:bg-forest/20 text-forest-dark dark:text-forest-light font-medium">
                {input.subagent_type}
              </span>
            )}
            <p className="text-stone-700 dark:text-stone-300">{String(input.description)}</p>
          </div>
        );
      }
      break;
  }

  // Default: raw JSON
  return (
    <pre className="text-xs bg-stone-100 dark:bg-stone-800 p-2 rounded overflow-x-auto max-h-32 overflow-y-auto font-mono text-stone-700 dark:text-stone-300">
      {JSON.stringify(input, null, 2)}
    </pre>
  );
}

type TraceItem =
  | { kind: 'tool'; data: ToolCall }
  | { kind: 'thought'; data: Thought[] };

/**
 * Interleave thoughts between tool calls by sequence number.
 * Consecutive thoughts are grouped into a single collapsible block.
 */
function interleaveTrace(toolCalls: ToolCall[], thoughts: Thought[]): TraceItem[] {
  if (!thoughts || thoughts.length === 0) {
    return toolCalls.map((tc) => ({ kind: 'tool' as const, data: tc }));
  }

  const items: TraceItem[] = [];
  let thoughtIdx = 0;
  const sorted = [...thoughts].sort((a, b) => a.seq - b.seq);

  for (const tc of toolCalls) {
    // Collect all thoughts that come before this tool call
    const group: Thought[] = [];
    while (thoughtIdx < sorted.length && sorted[thoughtIdx].seq <= tc.sequenceNumber) {
      group.push(sorted[thoughtIdx]);
      thoughtIdx++;
    }
    if (group.length > 0) {
      items.push({ kind: 'thought', data: group });
    }
    items.push({ kind: 'tool', data: tc });
  }

  // Trailing thoughts after last tool call
  if (thoughtIdx < sorted.length) {
    items.push({ kind: 'thought', data: sorted.slice(thoughtIdx) });
  }

  return items;
}

const AGENT_ORDER: Record<string, number> = {
  planner: 0,
  // investigation subagents: 10-19
  kubernetes: 10,
  k8s: 10,
  metrics: 11,
  log_analysis: 12,
  traces: 13,
  aws: 14,
  github: 15,
  coding: 16,
  // post-investigation
  synthesizer: 20,
  writeup: 21,
  memory_store: 22,
  'sre-agent': 30,
  unknown: 99,
};

const AGENT_COLORS: Record<string, string> = {
  planner: 'border-l-purple-500',
  investigation: 'border-l-forest',
  k8s: 'border-l-forest',
  aws: 'border-l-orange-500',
  metrics: 'border-l-green-500',
  coding: 'border-l-pink-500',
  log_analysis: 'border-l-yellow-500',
  github: 'border-l-stone-500',
  writeup: 'border-l-indigo-500',
  synthesizer: 'border-l-teal-500',
  'sre-agent': 'border-l-stone-400',
};

export function TraceViewer({ runId, correlationId, isRunning }: TraceViewerProps) {
  const [trace, setTrace] = useState<TraceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCalls, setExpandedCalls] = useState<Set<string>>(new Set());
  const [collapsedAgents, setCollapsedAgents] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function loadTrace() {
      try {
        const res = await apiFetch(`/api/team/agent-runs/${runId}/trace`);
        if (res.ok) {
          const data = await res.json();
          setTrace(data);
        } else {
          const errData = await res.json().catch(() => ({}));
          setError(errData.error || `Failed to load trace (${res.status})`);
        }
      } catch (e: any) {
        setError(e?.message || 'Failed to load trace');
      } finally {
        setLoading(false);
      }
    }
    loadTrace();

    // Poll while the run is still active
    if (isRunning) {
      const interval = setInterval(loadTrace, 3000);
      return () => clearInterval(interval);
    }
  }, [runId, isRunning]);

  const toggleCall = (callId: string) => {
    setExpandedCalls((prev) => {
      const next = new Set(prev);
      if (next.has(callId)) {
        next.delete(callId);
      } else {
        next.add(callId);
      }
      return next;
    });
  };

  const toggleAgent = (agentName: string) => {
    setCollapsedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(agentName)) {
        next.delete(agentName);
      } else {
        next.add(agentName);
      }
      return next;
    });
  };

  // Group tool calls by agent
  const groupedByAgent = (trace?.toolCalls || []).reduce((acc, tc) => {
    const agent = tc.agentName || 'unknown';
    if (!acc[agent]) acc[agent] = [];
    acc[agent].push(tc);
    return acc;
  }, {} as Record<string, ToolCall[]>);

  const thoughts = trace?.thoughts || [];

  // Ensure agents with thoughts but no tool calls also get groups
  for (const t of thoughts) {
    if (t.agent && !groupedByAgent[t.agent]) {
      groupedByAgent[t.agent] = [];
    }
  }

  if (loading) {
    return (
      <div className="py-4 flex items-center justify-center text-stone-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading trace...
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-4 text-center text-stone-500">
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  if (!trace || (trace.toolCalls.length === 0 && thoughts.length === 0)) {
    return (
      <div className="py-4 text-center text-stone-500">
        <Wrench className="w-8 h-8 mx-auto mb-2 text-stone-300" />
        <p className="text-sm">No tool calls recorded for this run.</p>
        <p className="text-xs text-stone-400 mt-1">
          Trace data may not be available for older runs.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium text-stone-700 dark:text-stone-300 flex items-center gap-2">
          <Wrench className="w-4 h-4" />
          Execution Trace ({trace.total} tool calls)
        </h4>
        <a
          href={`https://platform.openai.com/traces?trace_id=${correlationId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-forest hover:text-forest-dark dark:text-forest-light hover:underline"
        >
          View in OpenAI Dashboard
        </a>
      </div>

      <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-600 overflow-hidden">
        {/* Agent groups sorted by graph topology */}
        {Object.entries(groupedByAgent)
          .sort(([a], [b]) => (AGENT_ORDER[a] ?? 50) - (AGENT_ORDER[b] ?? 50))
          .map(([agentName, calls]) => {
          // Filter thoughts to this agent group (or include unattributed ones if only one group)
          const agentThoughts = thoughts.filter(
            (t) => t.agent === agentName || (!t.agent && Object.keys(groupedByAgent).length === 1)
          );
          const items = interleaveTrace(calls, agentThoughts);
          const isCollapsed = collapsedAgents.has(agentName);
          return (
            <div key={agentName}>
              <div
                className="px-3 py-2 bg-stone-50 dark:bg-stone-700 border-b border-stone-200 dark:border-stone-600 flex items-center gap-2 cursor-pointer hover:bg-stone-100 dark:hover:bg-stone-700/50 select-none"
                onClick={() => toggleAgent(agentName)}
              >
                {isCollapsed ? (
                  <ChevronRight className="w-4 h-4 text-stone-400" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-stone-400" />
                )}
                <Bot className="w-4 h-4 text-stone-500" />
                <span className="text-sm font-medium text-stone-700 dark:text-stone-300">
                  {agentName.replace(/_/g, ' ')}
                </span>
                <span className="text-xs text-stone-400">
                  {calls.length > 0 ? `${calls.length} calls` : `${agentThoughts.length} thoughts`}
                </span>
              </div>
              {!isCollapsed && items.map((item, idx) =>
                item.kind === 'thought' ? (
                  <ThoughtBlock key={`thought-${idx}`} thoughts={item.data} />
                ) : (
                  <ToolCallRow
                    key={item.data.id}
                    call={item.data}
                    isExpanded={expandedCalls.has(item.data.id)}
                    onToggle={() => toggleCall(item.data.id)}
                    indent={item.data.parentAgent ? 1 : 0}
                  />
                ),
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface ToolCallRowProps {
  call: ToolCall;
  isExpanded: boolean;
  onToggle: () => void;
  indent: number;
}

function ToolCallRow({ call, isExpanded, onToggle, indent }: ToolCallRowProps) {
  const agentColor = AGENT_COLORS[call.agentName || ''] || 'border-l-stone-400';

  return (
    <div
      className={`border-b border-stone-100 dark:border-stone-700 last:border-b-0 border-l-2 ${agentColor}`}
      style={{ marginLeft: indent * 16 }}
    >
      <div
        className="px-3 py-2 flex items-center gap-3 cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
        onClick={onToggle}
      >
        <div className="flex-shrink-0">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-stone-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-stone-400" />
          )}
        </div>
        <div className="flex-shrink-0">{getStatusIcon(call.status)}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-stone-900 dark:text-white">
              {call.toolName}
            </span>
            {call.agentName && (
              <span className="text-xs text-stone-400">via {call.agentName}</span>
            )}
          </div>
          {getToolSummary(call) && (
            <div className="text-xs text-stone-500 dark:text-stone-400 font-mono truncate mt-0.5">
              {getToolSummary(call)}
            </div>
          )}
        </div>
        <div className="flex-shrink-0 text-xs text-stone-400">
          {formatDuration(call.durationMs)}
        </div>
      </div>

      {isExpanded && (
        <div className="px-3 pb-3 pt-1 bg-stone-50 dark:bg-stone-900 border-t border-stone-100 dark:border-stone-700">
          {call.toolInput && Object.keys(call.toolInput).length > 0 && (
            <div className="mb-3">
              <div className="text-xs font-medium text-stone-500 mb-1 flex items-center gap-1">
                <Code className="w-3 h-3" />
                Input
              </div>
              {renderToolInput(call)}
            </div>
          )}

          {call.toolOutput && (
            <div className="mb-3">
              <div className="text-xs font-medium text-stone-500 mb-1 flex items-center gap-1">
                <Code className="w-3 h-3" />
                Output
              </div>
              <pre className="text-xs bg-stone-100 dark:bg-stone-800 p-2 rounded overflow-x-auto max-h-96 overflow-y-auto font-mono text-stone-700 dark:text-stone-300 whitespace-pre-wrap">
                {call.toolOutput}
              </pre>
            </div>
          )}

          {call.errorMessage && (
            <div className="mb-3">
              <div className="text-xs font-medium text-clay mb-1">Error</div>
              <pre className="text-xs bg-clay-light/10 dark:bg-clay/20 p-2 rounded text-clay-dark dark:text-clay-light whitespace-pre-wrap">
                {call.errorMessage}
              </pre>
            </div>
          )}

          <div className="text-xs text-stone-400 flex items-center gap-3">
            <span>#{call.sequenceNumber}</span>
            <span>{new Date(call.startedAt).toLocaleTimeString()}</span>
            {call.durationMs && <span>{formatDuration(call.durationMs)}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

function ThoughtBlock({ thoughts }: { thoughts: Thought[] }) {
  const [expanded, setExpanded] = useState(false);
  const preview = thoughts[0]?.text?.substring(0, 120) || '';

  return (
    <div className="border-b border-stone-100 dark:border-stone-700 last:border-b-0">
      <div
        className="px-3 py-1.5 flex items-start gap-2 cursor-pointer hover:bg-amber-50/50 dark:hover:bg-amber-900/10"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-shrink-0 mt-0.5">
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-amber-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-amber-400" />
          )}
        </div>
        <Brain className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
        {expanded ? (
          <div className="flex-1 min-w-0 space-y-1.5">
            {thoughts.map((t, i) => (
              <p
                key={i}
                className="text-xs text-stone-600 dark:text-stone-400 leading-relaxed"
              >
                {t.text}
              </p>
            ))}
          </div>
        ) : (
          <p className="text-xs text-stone-500 dark:text-stone-400 italic truncate flex-1 min-w-0">
            {preview}
            {thoughts.length > 1 && (
              <span className="text-amber-500 ml-1">+{thoughts.length - 1} more</span>
            )}
          </p>
        )}
      </div>
    </div>
  );
}

export default TraceViewer;
