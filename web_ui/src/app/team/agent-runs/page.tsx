'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { apiFetch } from '@/lib/apiClient';
import { HelpTip } from '@/components/onboarding/HelpTip';
import { useAgentStream } from '@/lib/useAgentStream';
import { useOnboarding } from '@/lib/useOnboarding';
import {
  Activity,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  MessageSquare,
  Bot,
  Zap,
  ChevronDown,
  ChevronRight,
  Terminal,
  RefreshCcw,
  Filter,
  Calendar,
  Sparkles,
  X,
  Send,
} from 'lucide-react';
import TraceViewer from '@/components/TraceViewer';
import InvestigationReport from '@/components/InvestigationReport';
import type { InvestigationReportData } from '@/components/InvestigationReport';
import MarkdownFallback from '@/components/MarkdownFallback';

interface AgentRun {
  id: string;
  correlationId: string;
  agentName: string;
  triggerSource: 'slack' | 'api' | 'scheduled' | 'manual';
  triggerActor?: string;
  triggerMessage?: string;
  status: 'running' | 'completed' | 'failed' | 'timeout';
  startedAt: string;
  completedAt?: string;
  durationSeconds?: number;
  toolCallsCount?: number;
  outputSummary?: string;
  outputJson?: InvestigationReportData | null;
  errorMessage?: string;
  confidence?: number;
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed':
      return 'text-green-600 bg-green-100 dark:bg-green-900/30';
    case 'failed':
      return 'text-clay bg-clay-light/15 dark:bg-clay/20';
    case 'timeout':
      return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30';
    case 'running':
      return 'text-forest bg-forest-light/15 dark:bg-forest/30';
    default:
      return 'text-stone-600 bg-stone-100 dark:bg-stone-700';
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-4 h-4" />;
    case 'failed':
      return <XCircle className="w-4 h-4" />;
    case 'timeout':
      return <Clock className="w-4 h-4" />;
    case 'running':
      return <Loader2 className="w-4 h-4 animate-spin" />;
    default:
      return <Activity className="w-4 h-4" />;
  }
};

const getTriggerIcon = (source: string) => {
  switch (source) {
    case 'slack':
      return <MessageSquare className="w-4 h-4" />;
    case 'api':
      return <Terminal className="w-4 h-4" />;
    case 'scheduled':
      return <Calendar className="w-4 h-4" />;
    default:
      return <Zap className="w-4 h-4" />;
  }
};

const AGENT_COLORS: Record<string, string> = {
  planner: 'bg-stone-100 dark:bg-stone-700 text-stone-600',
  k8s_agent: 'bg-stone-100 dark:bg-stone-700 text-stone-600',
  aws_agent: 'bg-stone-100 dark:bg-stone-700 text-stone-600',
  coding_agent: 'bg-stone-100 dark:bg-stone-700 text-stone-600',
  metrics_agent: 'bg-stone-100 dark:bg-stone-700 text-stone-600',
  investigation_agent: 'bg-stone-100 dark:bg-stone-700 text-stone-600',
};

export default function TeamAgentRunsPage() {
  const { identity } = useIdentity();
  // Visitors use localStorage only for onboarding state
  const isVisitor = identity?.auth_kind === 'visitor';
  const { state: onboardingState, markFirstAgentRunCompleted, setQuickStartStep } = useOnboarding({ isVisitor });
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterAgent, setFilterAgent] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [showChatPanel, setShowChatPanel] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Use the agent stream hook for proper SSE parsing
  const {
    messages: agentMessages,
    isStreaming,
    error: agentError,
    sendMessage,
    reset: resetChat,
  } = useAgentStream({
    onComplete: () => {
      loadRuns(); // Refresh runs after completion

      // If user is on Step 5 of onboarding, mark first run completed and advance to Step 6
      if (onboardingState.quickStartStep === 5) {
        markFirstAgentRunCompleted();
        setQuickStartStep(6);
      }
    },
  });

  const teamId = identity?.team_node_id;

  const initialLoadDone = useRef(false);
  const loadRuns = useCallback(async () => {
    if (!teamId) return;
    // Only show full-page spinner on initial load
    if (!initialLoadDone.current) setLoading(true);
    try {
      const res = await apiFetch(`/api/team/agent-runs`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setRuns(data);
        }
      }
    } catch (e) {
      console.error('Failed to load agent runs', e);
    } finally {
      setLoading(false);
      initialLoadDone.current = true;
    }
  }, [teamId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // Poll while there are running investigations
  useEffect(() => {
    const hasRunning = runs.some((r) => r.status === 'running');
    if (!hasRunning) return;
    const interval = setInterval(loadRuns, 5000);
    return () => clearInterval(interval);
  }, [runs, loadRuns]);

  const filteredRuns = runs.filter((r) => {
    if (filterAgent !== 'all' && r.agentName !== filterAgent) return false;
    if (filterStatus !== 'all' && r.status !== filterStatus) return false;
    return true;
  });

  const uniqueAgents = [...new Set(runs.map((r) => r.agentName))];
  const runningCount = runs.filter((r) => r.status === 'running').length;

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  const handleSendMessage = () => {
    if (!chatInput.trim() || isStreaming) return;
    sendMessage(chatInput.trim());
    setChatInput('');
  };

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [agentMessages]);

  // Reset chat when panel closes
  const handleCloseChat = () => {
    setShowChatPanel(false);
    resetChat();
    setChatInput('');
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-stone-400" />
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-48px)] flex flex-col p-6 max-w-5xl mx-auto">
      {/* Header - Fixed */}
      <div className="flex items-center justify-between mb-6 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-forest flex items-center justify-center">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">
              Agent Run History
            <HelpTip id="agent-runs" position="right">
              <strong>Agent Runs</strong> are individual AI investigation sessions. Each run uses tools like Grafana, Kubernetes, and your Knowledge Base to analyze incidents and provide recommendations.
            </HelpTip>
          </h1>
            <p className="text-sm text-stone-500">
              View the history of AI agent invocations for your team.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {runningCount > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-400 rounded-full text-sm font-medium">
              <Loader2 className="w-4 h-4 animate-spin" />
              {runningCount} running
            </div>
          )}
          <button
            onClick={() => setShowChatPanel(true)}
            className="flex items-center gap-2 px-4 py-2 bg-forest hover:bg-forest-dark text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            New Investigation
          </button>
          <button
            onClick={loadRuns}
            className="p-2 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800"
          >
            <RefreshCcw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Filters - Fixed */}
      <div className="flex items-center gap-4 mb-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-stone-400" />
          <select
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-800"
          >
            <option value="all">All Agents</option>
            {uniqueAgents.map((agent) => (
              <option key={agent} value={agent}>
                {agent.replace('_', ' ')}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-1">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-800"
          >
            <option value="all">All Status</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="timeout">Timeout</option>
          </select>
          <HelpTip id="run-status" position="bottom">
            <strong>Running:</strong> Agent is actively investigating<br/>
            <strong>Completed:</strong> Investigation finished successfully<br/>
            <strong>Failed:</strong> Agent encountered an error<br/>
            <strong>Timeout:</strong> Investigation exceeded time limit
          </HelpTip>
        </div>
      </div>

      {/* Runs List - Scrollable */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {filteredRuns.length === 0 ? (
          <div className="bg-stone-50 dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-12 text-center">
            <Activity className="w-12 h-12 mx-auto text-stone-300 dark:text-stone-600 mb-4" />
            <p className="text-stone-500">No agent runs found.</p>
          </div>
        ) : (
          <div className="space-y-3 pb-4">
          {filteredRuns.map((run) => (
            <div
              key={run.id}
              className={`bg-white dark:bg-stone-800 border rounded-xl overflow-hidden ${
                run.status === 'running'
                  ? 'border-forest-light dark:border-forest'
                  : 'border-stone-200 dark:border-stone-700'
              }`}
            >
              <div
                className="p-4 cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
                onClick={() => setExpandedId(expandedId === run.id ? null : run.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div
                      className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        AGENT_COLORS[run.agentName] || 'bg-stone-100 dark:bg-stone-700 text-stone-600'
                      }`}
                    >
                      <Bot className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-stone-900 dark:text-white">
                          {run.agentName.replace('_', ' ')}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded-full flex items-center gap-1 ${getStatusColor(run.status)}`}>
                          {getStatusIcon(run.status)}
                          {run.status}
                        </span>
                        {run.confidence && (
                          <span className="text-xs text-stone-500">
                            {run.confidence}% confidence
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-stone-500 line-clamp-1">{run.triggerMessage}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right text-sm">
                      <div className="flex items-center gap-1 text-stone-400">
                        {getTriggerIcon(run.triggerSource)}
                        <span className="capitalize">{run.triggerSource}</span>
                      </div>
                      <div className="text-stone-500">
                        {new Date(run.startedAt).toLocaleTimeString()}
                      </div>
                    </div>
                    {expandedId === run.id ? (
                      <ChevronDown className="w-5 h-5 text-stone-400" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-stone-400" />
                    )}
                  </div>
                </div>
              </div>

              {/* Expanded Content */}
              {expandedId === run.id && (
                <div className="border-t border-stone-200 dark:border-stone-700 p-4 bg-stone-50 dark:bg-stone-900">
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div className="bg-white dark:bg-stone-800 p-3 rounded-lg border border-stone-200 dark:border-stone-600">
                      <div className="text-xs text-stone-500 mb-1 flex items-center gap-1">
                        MTTD (Run Duration)
                        <HelpTip id="mttd" position="top">
                          <strong>Mean Time to Detect</strong> measures how long the agent took to analyze the incident. Lower is better.
                        </HelpTip>
                      </div>
                      <div className="text-lg font-semibold text-stone-900 dark:text-white">
                        {formatDuration(run.durationSeconds)}
                      </div>
                    </div>
                    <div className="bg-white dark:bg-stone-800 p-3 rounded-lg border border-stone-200 dark:border-stone-600">
                      <div className="text-xs text-stone-500 mb-1 flex items-center gap-1">
                        Tool Calls
                        <HelpTip id="tool-calls" position="top">
                          Number of tools the agent used (Grafana queries, K8s lookups, Knowledge Base searches, etc.)
                        </HelpTip>
                      </div>
                      <div className="text-lg font-semibold text-stone-900 dark:text-white flex items-center gap-2">
                        {run.toolCallsCount || (run.status === 'running' ? '-' : 0)}
                        {run.status === 'running' && (
                          <Loader2 className="w-4 h-4 animate-spin text-forest" />
                        )}
                      </div>
                    </div>
                    <div className="bg-white dark:bg-stone-800 p-3 rounded-lg border border-stone-200 dark:border-stone-600">
                      <div className="text-xs text-stone-500 mb-1">Triggered By</div>
                      <div className="text-sm font-medium text-stone-900 dark:text-white truncate">
                        {run.triggerActor || 'system'}
                      </div>
                    </div>
                  </div>

                  {(run.outputJson || run.outputSummary) && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">Output</h4>
                      {run.outputJson ? (
                        <InvestigationReport report={run.outputJson} />
                      ) : run.outputSummary ? (
                        <MarkdownFallback content={run.outputSummary} />
                      ) : null}
                    </div>
                  )}

                  {run.errorMessage && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-clay mb-2">Error</h4>
                      <div className="bg-clay-light/10 dark:bg-clay/20 p-3 rounded-lg border border-clay-light dark:border-clay">
                        <p className="text-sm text-clay-dark dark:text-clay-light">{run.errorMessage}</p>
                      </div>
                    </div>
                  )}

                  {/* Trace Viewer */}
                  <TraceViewer runId={run.id} correlationId={run.correlationId} isRunning={run.status === 'running'} />

                  <div className="text-xs text-stone-400 flex items-center gap-4 mt-4">
                    <span>Correlation ID: {run.correlationId}</span>
                    <span>Started: {new Date(run.startedAt).toLocaleString()}</span>
                    {run.completedAt && <span>Completed: {new Date(run.completedAt).toLocaleString()}</span>}
                  </div>
                </div>
              )}
            </div>
          ))}
          </div>
        )}
      </div>

      {/* Chat Panel Overlay */}
      {showChatPanel && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/20 dark:bg-black/40"
            onClick={handleCloseChat}
          />

          {/* Panel */}
          <div className="relative w-full max-w-lg bg-white dark:bg-stone-800 shadow-2xl flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200 dark:border-stone-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-forest-light/15 dark:bg-forest/30 flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-forest" />
                </div>
                <div>
                  <h2 className="font-semibold text-stone-900 dark:text-white">Ask OpenSRE</h2>
                  <p className="text-xs text-stone-500">AI-powered incident investigation</p>
                </div>
              </div>
              <button
                onClick={handleCloseChat}
                className="p-2 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {agentMessages.length === 0 && (
                <div className="text-center py-12">
                  <Bot className="w-12 h-12 mx-auto text-stone-300 dark:text-stone-600 mb-4" />
                  <p className="text-stone-500 mb-2">Start an investigation</p>
                  <p className="text-sm text-stone-400">
                    Describe the issue you&apos;re investigating, and the AI will analyze your systems.
                  </p>
                </div>
              )}

              {agentMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-forest text-white'
                        : 'bg-stone-100 dark:bg-stone-700 text-stone-900 dark:text-white'
                    }`}
                  >
                    {/* Tool calls for assistant messages */}
                    {msg.role === 'assistant' && msg.toolCalls && msg.toolCalls.length > 0 && (
                      <div className="space-y-1 mb-2 text-xs">
                        {msg.toolCalls.map((tool) => (
                          <div key={tool.id} className="flex items-center gap-2 text-stone-500 dark:text-stone-400">
                            {tool.status === 'running' ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : tool.status === 'completed' ? (
                              <CheckCircle className="w-3 h-3 text-green-500" />
                            ) : (
                              <XCircle className="w-3 h-3 text-clay" />
                            )}
                            <span>{tool.name.replace(/_/g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {msg.content && (
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    )}
                    {msg.isStreaming && !msg.content && (!msg.toolCalls || msg.toolCalls.length === 0) && (
                      <div className="flex items-center gap-2 text-stone-500">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span className="text-sm">Thinking...</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {agentError && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-clay-light/10 dark:bg-clay/20 border border-clay-light dark:border-clay">
                  <XCircle className="w-5 h-5 text-clay flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-clay-dark dark:text-clay-light">{agentError}</div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="border-t border-stone-200 dark:border-stone-700 p-4">
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                  placeholder="Describe the issue to investigate..."
                  className="flex-1 px-4 py-3 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-forest focus:border-transparent"
                  disabled={isStreaming}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!chatInput.trim() || isStreaming}
                  className="p-3 bg-forest hover:bg-forest-dark disabled:bg-stone-300 disabled:dark:bg-stone-700 text-white rounded-lg transition-colors"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
              <p className="text-xs text-stone-400 mt-2 text-center">
                Press Enter to send
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

