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
import { RunStatusBadge } from '@/components/RunStatusBadge';
import {
  Bot,
  Activity,
  Brain,
  TrendingUp,
  Clock,
  BookOpen,
  RefreshCw,
  Upload,
  Wrench,
  GitPullRequest,
  Sparkles,
} from 'lucide-react';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { NewInvestigationDrawer } from '@/components/NewInvestigationDrawer';

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

export default function TeamDashboardPage() {
  const router = useRouter();
  const { identity } = useIdentity();
  const [stats, setStats] = useState<TeamStats | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [episodes, setEpisodes] = useState<ThreadEpisode[]>([]);
  const [pending, setPending] = useState<PendingItems>({ configChanges: 0, knowledgeChanges: 0 });
  // Opens the shared investigation slide-over (same drawer the Agent Runs page uses).
  const [showChat, setShowChat] = useState(false);

  // Onboarding state - visitors use localStorage only
  const isVisitor = identity?.auth_kind === 'visitor';
  const {
    shouldShowWelcome,
    markWelcomeSeen,
    markFirstAgentRunCompleted,
  } = useOnboarding({ isVisitor });
  const [showWelcomeModal, setShowWelcomeModal] = useState(false);

  // Show welcome modal on first visit
  useEffect(() => {
    if (shouldShowWelcome) {
      setShowWelcomeModal(true);
    }
  }, [shouldShowWelcome]);

  // Re-fetch dashboard stats, investigations, and pending items.
  // Called on mount and again after an investigation completes so a fresh
  // thread shows up without a manual refresh.
  const refreshDashboard = useCallback(() => {
    fetch('/api/team/stats')
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        console.log('Stats API response:', data);
        data && setStats(data);
      })
      .catch(err => console.error('Failed to load stats:', err));

    fetch('/api/team/pending')
      .then(res => res.ok ? res.json() : null)
      .then(data => data && setPending(data))
      .catch(err => console.error('Failed to load pending items:', err));

    // Enrich run rows with episode summaries (same join as /team/agent-runs).
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

  const episodeMap = useMemo(() => buildEpisodeMap(episodes), [episodes]);

  // One row per investigation thread (correlation_id), not per agent run.
  const recentThreads = useMemo(() => {
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

    return threads
      .sort((a, b) => b.latestRun.startedAt.localeCompare(a.latestRun.startedAt))
      .slice(0, RECENT_THREAD_LIMIT);
  }, [runs]);

  const totalPending = pending.configChanges + pending.knowledgeChanges;

  const handleWelcomeRunAgent = () => {
    markWelcomeSeen();
    markFirstAgentRunCompleted();
    setShowWelcomeModal(false);
    // Navigate to agent-runs page where they can run agents
    window.location.href = '/team/agent-runs';
  };

  const handleWelcomeSkip = () => {
    markWelcomeSeen();
    setShowWelcomeModal(false);
  };

  return (
    <RequireRole role="team" fallbackHref="/">
      {/* Onboarding Modals */}
      {showWelcomeModal && (
        <QuickStartWizard
          onClose={() => setShowWelcomeModal(false)}
          onRunAgent={handleWelcomeRunAgent}
          onSkip={handleWelcomeSkip}
        />
      )}

      <div className="p-8 max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-forest flex items-center justify-center"><Bot className="w-5 h-5 text-white" /></div>
            <div>
              <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">Team Dashboard</h1>
              <p className="text-sm text-stone-500">Monitor your AI agents and team activity</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button onClick={() => setShowChat(true)} className="flex items-center gap-2 px-4 py-2 bg-forest hover:bg-forest-dark text-white rounded-lg text-sm font-medium transition-colors">
              <Sparkles className="w-4 h-4" />Investigate
            </button>
            <div className="text-xs text-stone-500 text-right">
              <div>
                Team: <span className="font-mono">{identity?.team_node_id || identity?.org_id || 'unknown'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Team Overview Stats */}
        <div>
          <h2 className="text-lg font-semibold text-stone-900 dark:text-white mb-4">Team Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-stone-500">Total Agent Runs</div>
                  <div className="text-3xl font-bold text-stone-900 dark:text-white mt-1">
                    {stats?.totalRuns || 0}
                  </div>
                  {stats && stats.trend !== 'stable' && (
                    <div className="flex items-center gap-1 mt-1">
                      {stats.trend === 'up' ? (
                        <TrendingUp className="w-3 h-3 text-green-500" />
                      ) : (
                        <Activity className="w-3 h-3 text-clay rotate-180" />
                      )}
                      <span className={`text-xs ${stats.trend === 'up' ? 'text-green-600' : 'text-clay'}`}>
                        {stats.runsThisWeek} this week
                      </span>
                    </div>
                  )}
                </div>
                <Bot className="w-10 h-10 text-stone-400 opacity-80" />
              </div>
            </div>

            <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-stone-500">Success Rate</div>
                  <div className="text-3xl font-bold text-stone-900 dark:text-white mt-1">
                    {stats?.successRate || 0}%
                  </div>
                </div>
                <TrendingUp className="w-10 h-10 text-green-500 opacity-80" />
              </div>
            </div>

            <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-stone-500">Avg MTTD</div>
                  <div className="text-3xl font-bold text-stone-900 dark:text-white mt-1">
                    {stats?.avgMttdSeconds != null
                      ? stats.avgMttdSeconds < 60
                        ? `${Math.round(stats.avgMttdSeconds)}s`
                        : stats.avgMttdSeconds < 3600
                        ? `${Math.round(stats.avgMttdSeconds / 60)}m`
                        : `${(stats.avgMttdSeconds / 3600).toFixed(1)}h`
                      : 'N/A'}
                  </div>
                  <div className="text-xs text-stone-400 mt-1">Last 30 days</div>
                </div>
                <Clock className="w-10 h-10 text-stone-400 opacity-80" />
              </div>
            </div>
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Activity Feed - Takes 2 columns, height matches right column */}
          <div className="lg:col-span-2">
            <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl shadow-sm flex flex-col max-h-[526px]">
              <div className="p-5 border-b border-stone-200 dark:border-stone-700 flex-shrink-0">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-stone-900 dark:text-white">Recent Activity</h2>
                  <button
                    onClick={refreshDashboard}
                    className="text-xs text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 flex items-center gap-1"
                  >
                    <RefreshCw className="w-3 h-3" />
                    Refresh
                  </button>
                </div>
              </div>
              <div className="divide-y divide-stone-200 dark:divide-stone-700 overflow-y-auto flex-1">
                {recentThreads.length === 0 && (
                  <div className="p-8 text-center text-sm text-stone-500">No recent investigations</div>
                )}
                {recentThreads.map((thread) => {
                  const ep = episodeMap.get(thread.correlationId);
                  const summary = pickThreadSummary(ep, thread.latestRun, thread.firstRun);

                  return (
                    <button
                      key={thread.correlationId}
                      type="button"
                      onClick={() => router.push(`/team/agent-runs/${thread.latestRun.id}`)}
                      className="w-full text-left p-4 hover:bg-stone-50 dark:hover:bg-stone-800/50 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 mt-0.5">
                          <div className="p-2 rounded-lg bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300">
                            <Bot className="w-4 h-4" />
                          </div>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <RunStatusBadge status={thread.latestRun.status} size="sm" />
                            {ep?.issue_type && (
                              <span className="text-xs font-medium text-stone-700 dark:text-stone-300">
                                {ep.issue_type}
                              </span>
                            )}
                            {thread.turnCount > 1 && (
                              <span className="text-xs text-stone-400">
                                {thread.turnCount} turns
                              </span>
                            )}
                            <span className="text-xs text-stone-400">
                              {formatRelativeTime(thread.latestRun.startedAt)}
                            </span>
                          </div>
                          <p className="text-sm text-stone-900 dark:text-white line-clamp-2">
                            {summary}
                          </p>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Column - Pending Items + Quick Actions */}
          <div className="flex flex-col gap-4">
            {/* Pending Items */}
            <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl shadow-sm">
              <div className="p-4 border-b border-stone-200 dark:border-stone-700">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-stone-900 dark:text-white">Pending Items</h2>
                  {totalPending > 0 && (
                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-400">
                      {totalPending}
                    </span>
                  )}
                </div>
              </div>
              <div className="p-4 space-y-2">
                <Link
                  href="/team/pending-changes"
                  className="block p-2.5 rounded-lg border border-stone-200 dark:border-stone-700 hover:border-stone-400 dark:hover:border-stone-600 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <GitPullRequest className="w-4 h-4 text-stone-500" />
                      <span className="text-sm font-medium text-stone-900 dark:text-white">Config Changes</span>
                    </div>
                    {pending.configChanges > 0 && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-400">
                        {pending.configChanges}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-stone-500 mt-1">Awaiting approval</p>
                </Link>

                <Link
                  href="/team/knowledge"
                  className="block p-2.5 rounded-lg border border-stone-200 dark:border-stone-700 hover:border-stone-400 dark:hover:border-stone-600 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-4 h-4 text-stone-500" />
                      <span className="text-sm font-medium text-stone-900 dark:text-white">Knowledge Changes</span>
                    </div>
                    {pending.knowledgeChanges > 0 && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                        {pending.knowledgeChanges}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-stone-500 mt-1">Proposed changes</p>
                </Link>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl shadow-sm">
              <div className="p-4 border-b border-stone-200 dark:border-stone-700">
                <h2 className="text-lg font-semibold text-stone-900 dark:text-white">Quick Actions</h2>
              </div>
              <div className="p-4 space-y-2">
                <Link
                  href="/team/knowledge"
                  className="block p-2.5 rounded-lg border border-stone-200 dark:border-stone-700 hover:border-stone-400 dark:hover:border-stone-600 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-lg bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-400 group-hover:bg-stone-200 dark:group-hover:bg-stone-700 transition-colors">
                      <Upload className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-stone-900 dark:text-white">Upload Knowledge</div>
                      <div className="text-xs text-stone-500">Add documentation</div>
                    </div>
                  </div>
                </Link>

                <Link
                  href="/team/agents"
                  className="block p-2.5 rounded-lg border border-stone-200 dark:border-stone-700 hover:border-stone-400 dark:hover:border-stone-600 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-lg bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-400 group-hover:bg-stone-200 dark:group-hover:bg-stone-700 transition-colors">
                      <Wrench className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-stone-900 dark:text-white">Configure Agents</div>
                      <div className="text-xs text-stone-500">Edit agent topology</div>
                    </div>
                  </div>
                </Link>

                <Link
                  href="/team/memory"
                  className="block p-2.5 rounded-lg border border-stone-200 dark:border-stone-700 hover:border-clay dark:hover:border-clay transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-lg bg-clay-light/10 dark:bg-clay/20 text-clay dark:text-clay-light group-hover:bg-clay-light/15 dark:group-hover:bg-clay/30 transition-colors">
                      <Brain className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-stone-900 dark:text-white">Memory</div>
                      <div className="text-xs text-stone-500">Past investigations</div>
                    </div>
                  </div>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Shared investigation slide-over — same drawer the Agent Runs page uses.
          On completion, refresh dashboard stats/activity so the new run shows up. */}
      <NewInvestigationDrawer
        open={showChat}
        onClose={() => setShowChat(false)}
        onComplete={refreshDashboard}
      />
    </RequireRole>
  );
}
