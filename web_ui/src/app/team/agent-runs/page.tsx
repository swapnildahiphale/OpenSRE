'use client';

import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useIdentity } from '@/lib/useIdentity';
import { apiFetch } from '@/lib/apiClient';
import { useOnboarding } from '@/lib/useOnboarding';
import { NewInvestigationDrawer } from '@/components/NewInvestigationDrawer';
import { TeamPageHeader } from '@/components/team/TeamPageHeader';
import {
  buildEpisodeMap,
  pickThreadSummary,
  type ThreadEpisode,
} from '@/lib/pickThreadSummary';
import { formatRelativeTime } from '@/lib/formatRelativeTime';
import {
  EpisodeResolutionBadge,
  RunStatusBadge,
} from '@/components/RunStatusBadge';
import {
  Activity,
  Loader2,
  MessageSquare,
  Zap,
  Terminal,
  RefreshCcw,
  Calendar,
  Sparkles,
} from 'lucide-react';

interface AgentRun {
  id: string;
  correlationId: string;
  agentName: string;
  triggerSource: 'slack' | 'api' | 'scheduled' | 'manual' | 'web_ui';
  triggerActor?: string;
  triggerMessage?: string;
  status: 'running' | 'completed' | 'failed' | 'timeout' | 'interrupted';
  startedAt: string;
  completedAt?: string;
  durationSeconds?: number;
  toolCallsCount?: number;
  outputJson?: Record<string, unknown> | null;
  errorMessage?: string | null;
}

interface Conversation {
  correlationId: string;
  firstRun: AgentRun;
  latestRun: AgentRun;
  turnCount: number;
}

const selectClass =
  'px-3 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-800';

const triggerIcon = (s: string) => {
  if (s === 'slack') return <MessageSquare className="w-4 h-4" />;
  if (s === 'api') return <Terminal className="w-4 h-4" />;
  if (s === 'scheduled') return <Calendar className="w-4 h-4" />;
  return <Zap className="w-4 h-4" />;
};

export default function TeamAgentRunsPage() {
  const router = useRouter();
  const { identity } = useIdentity();
  const { state: onboardingState, markFirstAgentRunCompleted, setQuickStartStep } =
    useOnboarding();
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [episodes, setEpisodes] = useState<ThreadEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterChannel, setFilterChannel] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [showChat, setShowChat] = useState(false);
  const teamId = identity?.team_node_id;
  const initialLoadDone = useRef(false);

  const loadRuns = useCallback(async () => {
    if (!teamId) return;
    if (!initialLoadDone.current) setLoading(true);
    try {
      const [runsRes, episodesRes] = await Promise.all([
        apiFetch('/api/team/agent-runs'),
        fetch('/api/memory/episodes'),
      ]);
      if (runsRes.ok) {
        const data = await runsRes.json();
        if (Array.isArray(data)) setRuns(data);
      }
      if (episodesRes.ok) {
        const epData = await episodesRes.json();
        setEpisodes(epData.episodes ?? []);
      }
    } finally {
      setLoading(false);
      initialLoadDone.current = true;
    }
  }, [teamId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (!runs.some((r) => r.status === 'running')) return;
    const id = setInterval(loadRuns, 5000);
    return () => clearInterval(id);
  }, [runs, loadRuns]);

  const episodeMap = useMemo(() => buildEpisodeMap(episodes), [episodes]);

  const conversations: Conversation[] = useMemo(() => {
    const groups = new Map<string, AgentRun[]>();
    for (const r of runs) {
      const key = r.correlationId || r.id;
      const arr = groups.get(key) ?? [];
      arr.push(r);
      groups.set(key, arr);
    }
    const out: Conversation[] = [];
    for (const [correlationId, arr] of groups) {
      const sorted = [...arr].sort((a, b) => a.startedAt.localeCompare(b.startedAt));
      out.push({
        correlationId,
        firstRun: sorted[0],
        latestRun: sorted[sorted.length - 1],
        turnCount: sorted.length,
      });
    }
    return out.sort((a, b) => b.latestRun.startedAt.localeCompare(a.latestRun.startedAt));
  }, [runs]);

  const filtered = conversations.filter((c) => {
    if (filterStatus !== 'all' && c.latestRun.status !== filterStatus) return false;
    if (filterChannel !== 'all' && c.latestRun.triggerSource !== filterChannel) return false;
    if (!searchText.trim()) return true;
    const ep = episodeMap.get(c.correlationId);
    const summary = pickThreadSummary(ep, c.latestRun, c.firstRun).toLowerCase();
    const q = searchText.toLowerCase();
    return (
      summary.includes(q) ||
      ep?.issue_type?.toLowerCase().includes(q) ||
      ep?.services?.some((s) => s.toLowerCase().includes(q)) ||
      c.firstRun.triggerMessage?.toLowerCase().includes(q)
    );
  });

  const channelOptions = useMemo(() => {
    const sources = new Set(runs.map((r) => r.triggerSource));
    return ['web_ui', 'slack', 'api', 'manual', 'scheduled'].filter((s) =>
      sources.has(s as AgentRun['triggerSource']),
    );
  }, [runs]);

  const runningCount = conversations.filter((c) => c.latestRun.status === 'running').length;
  const fmtDuration = (s?: number) => (!s ? '-' : s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`);

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
      <TeamPageHeader
        icon={Activity}
        title="Investigations"
        subtitle="Past threads your team ran through the agent"
        actions={
          <div className="flex items-center gap-3">
            {runningCount > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-400 rounded-full text-sm font-medium">
                <Loader2 className="w-4 h-4 animate-spin" />
                {runningCount} running
              </div>
            )}
            <button
              onClick={() => setShowChat(true)}
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
        }
      />

      {!loading && conversations.length > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            placeholder="Search investigations..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="flex-1 min-w-[200px] px-3 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-800"
          />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className={selectClass}
          >
            <option value="all">All Status</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="interrupted">Interrupted</option>
            <option value="failed">Failed</option>
            <option value="timeout">Timeout</option>
          </select>
          <select
            value={filterChannel}
            onChange={(e) => setFilterChannel(e.target.value)}
            className={selectClass}
          >
            <option value="all">All channels</option>
            {channelOptions.map((ch) => (
              <option key={ch} value={ch}>
                {ch.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="animate-pulse bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-4"
            >
              <div className="flex gap-2 mb-3">
                <div className="h-5 w-16 bg-stone-200 dark:bg-stone-700 rounded-full" />
                <div className="h-5 w-24 bg-stone-200 dark:bg-stone-700 rounded-full" />
              </div>
              <div className="h-4 w-full bg-stone-200 dark:bg-stone-700 rounded mb-2" />
              <div className="h-4 w-3/4 bg-stone-200 dark:bg-stone-700 rounded" />
            </div>
          ))}
        </div>
      ) : conversations.length === 0 ? (
        <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-12 text-center">
          <Activity className="w-12 h-12 mx-auto text-stone-300 dark:text-stone-600 mb-4" />
          <p className="text-stone-500 dark:text-stone-400 mb-4">No investigations yet.</p>
          <button
            onClick={() => setShowChat(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-forest hover:bg-forest-dark text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            New Investigation
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-12 text-center">
          <p className="text-stone-500 dark:text-stone-400">No investigations match your filters.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((conv) => {
            const ep = episodeMap.get(conv.correlationId);
            const summary = pickThreadSummary(ep, conv.latestRun, conv.firstRun);
            const isRunning = conv.latestRun.status === 'running';

            return (
              <button
                key={conv.correlationId}
                onClick={() => router.push(`/team/agent-runs/${conv.latestRun.id}`)}
                className={`w-full text-left bg-white dark:bg-stone-800 border rounded-xl p-4 shadow-sm hover:bg-stone-50 dark:hover:bg-stone-800/50 transition-colors active:scale-[0.98] ${
                  isRunning
                    ? 'border-forest-light dark:border-forest'
                    : 'border-stone-200 dark:border-stone-700'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <RunStatusBadge status={conv.latestRun.status} />
                      {ep?.issue_type && (
                        <span className="text-sm font-medium text-stone-900 dark:text-white">
                          {ep.issue_type}
                        </span>
                      )}
                      {ep && <EpisodeResolutionBadge resolved={ep.resolved ?? false} />}
                      <span className="text-xs text-stone-400">
                        {formatRelativeTime(conv.latestRun.startedAt)}
                      </span>
                    </div>

                    <p className="text-sm text-stone-700 dark:text-stone-300 line-clamp-2 mb-2">
                      {summary}
                    </p>

                    {ep?.services && ep.services.length > 0 && (
                      <div className="flex gap-1.5 mb-2 flex-wrap">
                        {ep.services.slice(0, 3).map((s) => (
                          <span
                            key={s}
                            className="text-xs bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 px-2 py-0.5 rounded"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center gap-2 text-xs text-stone-400 flex-wrap">
                      <span className="flex items-center gap-1 capitalize">
                        {triggerIcon(conv.latestRun.triggerSource)}
                        {conv.latestRun.triggerSource.replace(/_/g, ' ')}
                      </span>
                      <span>·</span>
                      <span>{fmtDuration(conv.latestRun.durationSeconds)}</span>
                      {conv.turnCount > 1 && (
                        <>
                          <span>·</span>
                          <span>{conv.turnCount} turns</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {showChat && (
        <NewInvestigationDrawer
          open={showChat}
          onClose={() => setShowChat(false)}
          onComplete={() => {
            loadRuns();
            if (onboardingState.quickStartStep === 5) {
              markFirstAgentRunCompleted();
              setQuickStartStep(6);
            }
          }}
        />
      )}
    </div>
  );
}
