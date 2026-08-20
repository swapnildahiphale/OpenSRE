'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { RequireRole } from '@/components/RequireRole';
import { useIdentity } from '@/lib/useIdentity';
import { useOnboarding } from '@/lib/useOnboarding';
import { apiFetch } from '@/lib/apiClient';
import { QuickStartWizard } from '@/components/onboarding/QuickStartWizard';
import {
  buildEpisodeMap,
  pickThreadSummary,
  type ThreadEpisode,
} from '@/lib/pickThreadSummary';
import { formatRelativeTime } from '@/lib/formatRelativeTime';
import {
  BookOpen,
  Brain,
  GitPullRequest,
  RefreshCw,
  Upload,
  Wrench,
} from 'lucide-react';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useInvestigationLauncher } from '@/components/shell/InvestigationLauncherContext';
import { PageHeader, Panel, StatusDot, listRowHoverClass, TeamPageShell } from '@/components/ui-flow';
import type { ComponentProps } from 'react';

interface TeamStats {
  totalRuns: number;
  successRate: number;
  avgMttdSeconds: number | null;
  runsThisWeek: number;
  runsPrevWeek: number;
  trend: 'up' | 'down' | 'stable';
}

interface PendingItems {
  configChanges: number;
  knowledgeChanges: number;
}

interface AgentRun {
  id: string;
  correlationId: string;
  status: 'running' | 'completed' | 'failed' | 'timeout' | 'interrupted';
  triggerMessage?: string | null;
  outputJson?: Record<string, unknown> | null;
  errorMessage?: string | null;
  startedAt: string;
}

interface Conversation {
  correlationId: string;
  firstRun: AgentRun;
  latestRun: AgentRun;
  turnCount: number;
}

const RECENT_THREAD_LIMIT = 10;

const SPARK_HEIGHTS = [30, 45, 35, 60, 50, 90, 75];

function groupRunsIntoThreads(runs: AgentRun[]): Conversation[] {
  const groups = new Map<string, AgentRun[]>();
  for (const run of runs) {
    const key = run.correlationId || run.id;
    const arr = groups.get(key) ?? [];
    arr.push(run);
    groups.set(key, arr);
  }

  const threads: Conversation[] = [];
  for (const [correlationId, arr] of groups) {
    const sorted = [...arr].sort((a, b) => a.startedAt.localeCompare(b.startedAt));
    threads.push({
      correlationId,
      firstRun: sorted[0],
      latestRun: sorted[sorted.length - 1],
      turnCount: sorted.length,
    });
  }

  return threads.sort((a, b) => b.latestRun.startedAt.localeCompare(a.latestRun.startedAt));
}

function formatMttd(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (seconds < 3600) {
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  }
  const hours = Math.floor(seconds / 3600);
  const remMins = Math.floor((seconds % 3600) / 60);
  return remMins > 0 ? `${hours}h ${remMins}m` : `${hours}h`;
}

function runStatusTone(
  status: AgentRun['status'],
): ComponentProps<typeof StatusDot>['tone'] {
  if (status === 'running') return 'live';
  if (status === 'failed') return 'danger';
  if (status === 'timeout' || status === 'interrupted') return 'warn';
  return 'idle';
}

function issueTypeClass(issueType?: string | null): string {
  if (!issueType) return 'text-slate-600';
  const key = issueType.toLowerCase();
  if (key.includes('auth') || key.includes('security')) return 'text-rose-700';
  if (key.includes('resource') || key.includes('oom')) return 'text-amber-700';
  if (key.includes('latency') || key.includes('performance')) return 'text-emerald-700';
  return 'text-slate-600';
}

export default function TeamDashboardPage() {
  const router = useRouter();
  const { identity } = useIdentity();
  const [stats, setStats] = useState<TeamStats | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [episodes, setEpisodes] = useState<ThreadEpisode[]>([]);
  const [pending, setPending] = useState<PendingItems>({ configChanges: 0, knowledgeChanges: 0 });
  const [refreshing, setRefreshing] = useState(false);
  const { registerOnComplete } = useInvestigationLauncher();

  const {
    shouldShowWelcome,
    markWelcomeSeen,
    markFirstAgentRunCompleted,
  } = useOnboarding();
  const [showWelcomeModal, setShowWelcomeModal] = useState(false);

  useEffect(() => {
    if (shouldShowWelcome) {
      setShowWelcomeModal(true);
    }
  }, [shouldShowWelcome]);

  const refreshDashboard = useCallback(() => {
    fetch('/api/team/stats')
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        data && setStats(data);
      })
      .catch(err => console.error('Failed to load stats:', err));

    fetch('/api/team/pending')
      .then(res => res.ok ? res.json() : null)
      .then(data => data && setPending(data))
      .catch(err => console.error('Failed to load pending items:', err));

    Promise.all([apiFetch('/api/team/agent-runs'), fetch('/api/memory/episodes')])
      .then(async ([runsRes, episodesRes]) => {
        if (runsRes.ok) {
          const data = await runsRes.json();
          if (Array.isArray(data)) setRuns(data);
        }
        if (episodesRes.ok) {
          const epData = await episodesRes.json();
          setEpisodes(epData.episodes ?? []);
        }
      })
      .catch(err => console.error('Failed to load investigation context:', err));
  }, []);

  useEffect(() => {
    refreshDashboard();
  }, [refreshDashboard]);

  useEffect(() => {
    return registerOnComplete(refreshDashboard);
  }, [registerOnComplete, refreshDashboard]);

  const handleRefresh = () => {
    setRefreshing(true);
    refreshDashboard();
    window.setTimeout(() => setRefreshing(false), 600);
  };

  const episodeMap = useMemo(() => buildEpisodeMap(episodes), [episodes]);

  const allThreads = useMemo(() => groupRunsIntoThreads(runs), [runs]);
  const recentThreads = useMemo(
    () => allThreads.slice(0, RECENT_THREAD_LIMIT),
    [allThreads],
  );

  // Live count: threads whose latest run is still running (same scope as loaded runs).
  const liveInvestigationCount = useMemo(
    () => allThreads.filter(t => t.latestRun.status === 'running').length,
    [allThreads],
  );

  // Footer breakdown uses all loaded agent runs (full /api/team/agent-runs payload).
  const runStatusCounts = useMemo(() => {
    let running = 0;
    let timeout = 0;
    let failed = 0;
    for (const run of runs) {
      if (run.status === 'running') running++;
      else if (run.status === 'timeout') timeout++;
      else if (run.status === 'failed') failed++;
    }
    return { running, timeout, failed };
  }, [runs]);

  const totalPending = pending.configChanges + pending.knowledgeChanges;
  const teamLabel = identity?.team_node_id || identity?.org_id || 'unknown';

  const handleWelcomeRunAgent = () => {
    markWelcomeSeen();
    markFirstAgentRunCompleted();
    setShowWelcomeModal(false);
    window.location.href = '/team/agent-runs';
  };

  const handleWelcomeSkip = () => {
    markWelcomeSeen();
    setShowWelcomeModal(false);
  };

  return (
    <RequireRole role="team" fallbackHref="/">
      {showWelcomeModal && (
        <QuickStartWizard
          onClose={() => setShowWelcomeModal(false)}
          onRunAgent={handleWelcomeRunAgent}
          onSkip={handleWelcomeSkip}
        />
      )}

      <TeamPageShell className="space-y-10">
        <div className="flex flex-wrap items-end justify-between gap-8">
          <PageHeader
            eyebrow="Dashboard"
            title="Today"
            subtitle="Monitor your AI agents and team activity"
          />
          <div className="flex flex-col items-end gap-3 text-sm shrink-0">
            {liveInvestigationCount > 0 && (
              <span className="inline-flex items-center gap-2 text-slate-500">
                <span className="live-dot w-2 h-2 rounded-full" aria-hidden />
                <span className="font-mono text-[13px] tabular-nums">
                  {liveInvestigationCount} live investigation
                  {liveInvestigationCount !== 1 ? 's' : ''}
                </span>
              </span>
            )}
            <div className="text-xs text-slate-400 text-right font-mono">
              Team: <span className="text-slate-600">{teamLabel}</span>
            </div>
          </div>
        </div>

        {/* Ops pulse stats — big In flight tile + 3 border-t details */}
        <section className="grid grid-cols-12 gap-8">
          <div className="col-span-12 md:col-span-5">
            <div
              className="relative overflow-hidden rounded-[2rem] border border-slate-200/70 p-6 shadow-[0_20px_40px_-15px_rgba(15,23,42,0.05)] flex flex-col min-h-[272px]"
              style={{
                background: 'linear-gradient(170deg, rgb(209 250 229 / 0.55), white 75%)',
              }}
            >
              <div
                className="absolute -top-8 -right-8 w-36 h-36 rounded-full breath pointer-events-none"
                style={{ backgroundColor: 'rgb(16 185 129 / 0.12)', filter: 'blur(40px)' }}
                aria-hidden
              />
              <div className="relative flex-1 flex flex-col">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                    In flight
                  </span>
                  {liveInvestigationCount > 0 && (
                    <span className="inline-flex items-center h-7 px-3 rounded-full text-xs font-medium bg-emerald-100/70 text-emerald-800 border border-emerald-200/80">
                      Active
                    </span>
                  )}
                </div>
                <div className="mt-4 flex items-baseline gap-2.5">
                  <span className="text-6xl font-medium tracking-tighter text-emerald-800 font-mono tabular-nums leading-none">
                    {liveInvestigationCount}
                  </span>
                  {(stats?.runsThisWeek ?? 0) > 0 && (
                    <span className="text-emerald-600 font-mono text-sm font-medium">
                      / {stats?.runsThisWeek} this week
                    </span>
                  )}
                </div>
                <div className="mt-5 flex items-end gap-1 h-7">
                  {SPARK_HEIGHTS.map((h, i) => (
                    <span
                      key={i}
                      className={`w-1.5 rounded-sm ${
                        i >= 5 ? 'bg-emerald-500' : i >= 3 ? 'bg-emerald-400/80' : 'bg-emerald-300/70'
                      }`}
                      style={{ height: `${h}%` }}
                    />
                  ))}
                </div>
                <div className="mt-auto pt-5 flex gap-6 text-xs font-mono text-slate-500">
                  <span>
                    <span className="text-emerald-600 font-medium">{runStatusCounts.running}</span>{' '}
                    running
                  </span>
                  <span>
                    <span className="text-amber-600 font-medium">{runStatusCounts.timeout}</span>{' '}
                    timeout
                  </span>
                  <span>
                    <span className="text-slate-500 font-medium">{runStatusCounts.failed}</span>{' '}
                    failed
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div className="col-span-12 md:col-span-7 grid grid-cols-3 gap-x-10 px-2">
            <div className="border-t border-slate-200 pt-6">
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Total runs</div>
              <div className="mt-4 text-4xl font-medium tracking-tight font-mono tabular-nums text-slate-900">
                {stats?.totalRuns ?? 0}
              </div>
            </div>
            <div className="border-t border-slate-200 pt-6">
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Success</div>
              <div className="mt-4 text-4xl font-medium tracking-tight font-mono tabular-nums text-slate-900">
                {stats?.successRate ?? 0}%
              </div>
            </div>
            <div className="border-t border-slate-200 pt-6">
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">MTTD</div>
              <div className="mt-4 text-4xl font-medium tracking-tight font-mono tabular-nums text-slate-900">
                {formatMttd(stats?.avgMttdSeconds)}
              </div>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <section className="lg:col-span-2">
            <Panel className="flex flex-col max-h-[540px]">
              <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between shrink-0">
                <h2 className="text-lg font-medium tracking-tight text-slate-900">Recent Activity</h2>
                <button
                  type="button"
                  onClick={handleRefresh}
                  className="text-xs text-slate-500 hover:text-slate-700 inline-flex items-center gap-1 transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
              </div>
              <ul className="divide-y divide-slate-100 overflow-y-auto flex-1">
                {recentThreads.length === 0 && (
                  <li className="px-5 py-8 text-center text-sm text-slate-500">
                    No recent investigations
                  </li>
                )}
                {recentThreads.map(thread => {
                  const ep = episodeMap.get(thread.correlationId);
                  const summary = pickThreadSummary(ep, thread.latestRun, thread.firstRun);
                  const status = thread.latestRun.status;

                  return (
                    <li key={thread.correlationId}>
                      <button
                        type="button"
                        onClick={() => router.push(`/team/agent-runs/${thread.latestRun.id}`)}
                        className={`w-full text-left px-5 py-4 ${listRowHoverClass}`}
                      >
                        <div className="flex items-start gap-3">
                          <span className="mt-1.5">
                            <StatusDot tone={runStatusTone(status)} label={status} />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2 mb-1.5 text-xs text-slate-500">
                              {ep?.issue_type && (
                                <span className={`font-medium ${issueTypeClass(ep.issue_type)}`}>
                                  {ep.issue_type}
                                </span>
                              )}
                              {thread.turnCount > 1 && <span>{thread.turnCount} turns</span>}
                              <span className="font-mono tabular-nums">
                                {formatRelativeTime(thread.latestRun.startedAt)}
                              </span>
                            </div>
                            <p className="text-[14.5px] text-slate-900 leading-snug line-clamp-2">
                              {summary}
                            </p>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
              <div className="px-5 py-3 border-t border-slate-100 shrink-0">
                <Link
                  href="/team/agent-runs"
                  className="text-sm text-emerald-700 font-medium hover:underline"
                >
                  All investigations →
                </Link>
              </div>
            </Panel>
          </section>

          <div className="flex flex-col gap-4">
            <Panel>
              <div className="px-4 py-3.5 border-b border-slate-100 flex items-center justify-between">
                <h2 className="text-lg font-medium tracking-tight text-slate-900">Pending Items</h2>
                {totalPending > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 font-mono tabular-nums">
                    {totalPending}
                  </span>
                )}
              </div>
              <div className="p-4 space-y-2">
                <Link
                  href="/team/pending-changes"
                  className="block p-3 rounded-xl border border-slate-200/70 hover:border-slate-300 hover:bg-slate-50/50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <GitPullRequest className="w-4 h-4 text-slate-400" />
                      <span className="text-sm font-medium text-slate-900">Config Changes</span>
                    </div>
                    {pending.configChanges > 0 && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 font-mono">
                        {pending.configChanges}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-1.5">Awaiting approval</p>
                </Link>

                <Link
                  href="/team/knowledge"
                  className="block p-3 rounded-xl border border-slate-200/70 hover:border-slate-300 hover:bg-slate-50/50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-4 h-4 text-slate-400" />
                      <span className="text-sm font-medium text-slate-900">Knowledge Changes</span>
                    </div>
                    {pending.knowledgeChanges > 0 && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100/60 text-emerald-700 font-mono">
                        {pending.knowledgeChanges}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-1.5">Proposed changes</p>
                </Link>
              </div>
            </Panel>

            <Panel>
              <div className="px-4 py-3.5 border-b border-slate-100">
                <h2 className="text-lg font-medium tracking-tight text-slate-900">Quick Actions</h2>
              </div>
              <div className="p-4 space-y-2">
                <Link
                  href="/team/knowledge"
                  className="block p-3 rounded-xl border border-slate-200/70 hover:border-slate-300 hover:bg-slate-50/50 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-lg bg-slate-100 text-slate-500 group-hover:bg-slate-200/70 transition-colors">
                      <Upload className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-900">Upload Knowledge</div>
                      <div className="text-xs text-slate-500">Add documentation</div>
                    </div>
                  </div>
                </Link>

                <Link
                  href="/team/agents"
                  className="block p-3 rounded-xl border border-slate-200/70 hover:border-slate-300 hover:bg-slate-50/50 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-lg bg-slate-100 text-slate-500 group-hover:bg-slate-200/70 transition-colors">
                      <Wrench className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-900">Configure Agents</div>
                      <div className="text-xs text-slate-500">Edit agent topology</div>
                    </div>
                  </div>
                </Link>

                <Link
                  href="/team/memory"
                  className="block p-3 rounded-xl border border-slate-200/70 hover:border-emerald-300/70 hover:bg-emerald-50/30 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-lg bg-emerald-100/50 text-emerald-700 group-hover:bg-emerald-100 transition-colors">
                      <Brain className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-900">Memory</div>
                      <div className="text-xs text-slate-500">Past investigations</div>
                    </div>
                  </div>
                </Link>
              </div>
            </Panel>
          </div>
        </div>
      </TeamPageShell>
    </RequireRole>
  );
}
