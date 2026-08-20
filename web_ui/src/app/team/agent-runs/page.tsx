'use client';

import type { ReactNode } from 'react';
import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { clsx } from 'clsx';
import { useIdentity } from '@/lib/useIdentity';
import { useOnboarding } from '@/lib/useOnboarding';
import { apiFetch } from '@/lib/apiClient';
import { useInvestigationLauncher } from '@/components/shell/InvestigationLauncherContext';
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
  PageHeader,
  Chip,
  EmptyState,
  Button,
  Skeleton,
  Panel,
  listRowHoverClass,
  TeamPageShell,
} from '@/components/ui-flow';
import {
  MessageSquare,
  Monitor,
  Terminal,
  RotateCw,
  Calendar,
  Search,
  Plus,
  FileText,
} from 'lucide-react';

interface AgentRun {
  id: string;
  correlationId: string;
  agentName: string;
  triggerSource: 'slack' | 'api' | 'scheduled' | 'manual' | 'web_ui' | 'teams';
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

const STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'running', label: 'running' },
  { value: 'completed', label: 'completed' },
  { value: 'interrupted', label: 'interrupted' },
  { value: 'failed', label: 'failed' },
  { value: 'timeout', label: 'timeout' },
] as const;

const ISSUE_TYPE_INITIAL = 5;
const ISSUE_TYPE_BATCH = 5;
const ISSUE_TYPE_MAX = 12;

// Channel icons aligned to investigations mockup (Monitor for web ui, not Zap/flash).
const triggerIcon = (s: string) => {
  if (s === 'slack' || s === 'teams') return <MessageSquare className="w-3.5 h-3.5" />;
  if (s === 'api') return <Terminal className="w-3.5 h-3.5" />;
  if (s === 'scheduled') return <Calendar className="w-3.5 h-3.5" />;
  if (s === 'manual') return <FileText className="w-3.5 h-3.5" />;
  // web_ui — desktop/monitor glyph from mockup
  return <Monitor className="w-3.5 h-3.5" />;
};

function FilterSectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500 mb-3">
      {children}
    </div>
  );
}

function StatusFilterItem({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={clsx(
          'flex items-center gap-2.5 w-full text-left text-sm transition-colors',
          active ? 'text-emerald-700 font-medium' : 'text-slate-700 hover:text-slate-900',
        )}
      >
        <span
          className={clsx(
            'w-3.5 h-3.5 rounded border shrink-0',
            active ? 'border-emerald-500 bg-emerald-500' : 'border-slate-300',
          )}
          aria-hidden
        />
        {label}
      </button>
    </li>
  );
}

export default function TeamAgentRunsPage() {
  const router = useRouter();
  const { identity } = useIdentity();
  const {
    state: onboardingState,
    markFirstAgentRunCompleted,
    setQuickStartStep,
  } = useOnboarding();
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [episodes, setEpisodes] = useState<ThreadEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterChannel, setFilterChannel] = useState('all');
  const [selectedIssueTypes, setSelectedIssueTypes] = useState<Set<string>>(new Set());
  const [issueTypeVisibleCount, setIssueTypeVisibleCount] = useState(ISSUE_TYPE_INITIAL);
  const [searchText, setSearchText] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const { open: openInvestigation, registerOnComplete } = useInvestigationLauncher();
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

  const handleInvestigationComplete = useCallback(() => {
    loadRuns();
    if (onboardingState.quickStartStep === 5) {
      markFirstAgentRunCompleted();
      setQuickStartStep(6);
    }
  }, [
    loadRuns,
    onboardingState.quickStartStep,
    markFirstAgentRunCompleted,
    setQuickStartStep,
  ]);

  useEffect(() => {
    return registerOnComplete(handleInvestigationComplete);
  }, [registerOnComplete, handleInvestigationComplete]);

  useEffect(() => {
    if (!runs.some((r) => r.status === 'running')) return;
    const id = setInterval(loadRuns, 5000);
    return () => clearInterval(id);
  }, [runs, loadRuns]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadRuns();
    window.setTimeout(() => setRefreshing(false), 600);
  };

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

  const issueTypeFreqs = useMemo(() => {
    const counts = new Map<string, number>();
    for (const ep of episodes) {
      if (ep.issue_type) {
        counts.set(ep.issue_type, (counts.get(ep.issue_type) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => b.count - a.count);
  }, [episodes]);

  const visibleIssueTypes = issueTypeFreqs.slice(
    0,
    Math.min(issueTypeVisibleCount, ISSUE_TYPE_MAX),
  );
  const canExpandIssueTypes =
    issueTypeVisibleCount < Math.min(issueTypeFreqs.length, ISSUE_TYPE_MAX);

  const expandIssueTypes = () => {
    setIssueTypeVisibleCount((n) =>
      Math.min(n + ISSUE_TYPE_BATCH, ISSUE_TYPE_MAX, issueTypeFreqs.length),
    );
  };

  const toggleIssueType = (value: string) => {
    setSelectedIssueTypes((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  };

  const clearAllFilters = () => {
    setFilterStatus('all');
    setFilterChannel('all');
    setSelectedIssueTypes(new Set());
    setSearchText('');
  };

  const filtered = conversations.filter((c) => {
    if (filterStatus !== 'all' && c.latestRun.status !== filterStatus) return false;
    if (filterChannel !== 'all' && c.latestRun.triggerSource !== filterChannel) return false;
    if (selectedIssueTypes.size > 0) {
      const ep = episodeMap.get(c.correlationId);
      if (!ep?.issue_type || !selectedIssueTypes.has(ep.issue_type)) return false;
    }
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
    return ['web_ui', 'teams', 'slack', 'api', 'manual', 'scheduled'].filter((s) =>
      sources.has(s as AgentRun['triggerSource']),
    );
  }, [runs]);

  const runningCount = conversations.filter((c) => c.latestRun.status === 'running').length;
  const fmtDuration = (s?: number) =>
    !s ? null : s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;

  const hasActiveFilters =
    filterStatus !== 'all' ||
    filterChannel !== 'all' ||
    selectedIssueTypes.size > 0 ||
    searchText.trim().length > 0;

  return (
    <TeamPageShell
      className="space-y-10"
      header={
        <div className="flex flex-wrap items-end justify-between gap-6">
          <PageHeader
            eyebrow="Investigations"
            title="Runs"
            subtitle="Episode and thread summaries"
          />
          {!loading && conversations.length > 0 && (
            <div className="flex items-center gap-3 shrink-0">
              {runningCount > 0 && (
                <span className="inline-flex items-center gap-2 h-9 px-3.5 rounded-full text-[13px] font-medium bg-slate-100 text-slate-600">
                  <span className="live-dot w-2 h-2 rounded-full shrink-0" aria-hidden />
                  <span className="font-mono tabular-nums">
                    {runningCount} running
                  </span>
                </span>
              )}
              <button
                type="button"
                onClick={handleRefresh}
                className="p-2 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition-colors"
                aria-label="Refresh"
                title="Refresh"
              >
                <RotateCw className={clsx('w-5 h-5', refreshing && 'animate-spin')} />
              </button>
            </div>
          )}
        </div>
      }
    >
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : conversations.length === 0 ? (
        <EmptyState
          title="No investigations yet"
          action={
            <Button variant="primary" onClick={openInvestigation}>
              <Plus className="w-3.5 h-3.5" />
              New Investigation
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-12 gap-10">
          <aside className="col-span-12 lg:col-span-3">
            <div className="sticky top-[80px] space-y-8">
              <div>
                <FilterSectionLabel>Status</FilterSectionLabel>
                <ul className="space-y-1.5">
                  {STATUS_OPTIONS.map((opt) => (
                    <StatusFilterItem
                      key={opt.value}
                      label={opt.label}
                      active={filterStatus === opt.value}
                      onClick={() => setFilterStatus(opt.value)}
                    />
                  ))}
                </ul>
              </div>

              {issueTypeFreqs.length > 0 && (
                <div>
                  <FilterSectionLabel>Issue type</FilterSectionLabel>
                  <div className="flex flex-wrap gap-1.5">
                    {visibleIssueTypes.map(({ value, count }) => (
                      <Chip
                        key={value}
                        active={selectedIssueTypes.has(value)}
                        onClick={() => toggleIssueType(value)}
                        className="h-auto px-2.5 py-1 font-mono normal-case"
                      >
                        {value}{' '}
                        <span className="text-slate-400 tabular-nums">{count}</span>
                      </Chip>
                    ))}
                    {canExpandIssueTypes && (
                      <button
                        type="button"
                        onClick={expandIssueTypes}
                        className="px-2.5 py-1 rounded-full text-xs font-medium border border-slate-200/70 bg-slate-50 text-slate-500 hover:bg-slate-100 hover:border-slate-300 hover:text-slate-600 font-mono transition"
                        aria-label="Show more issue types"
                        title="Show more issue types"
                      >
                        …
                      </button>
                    )}
                  </div>
                </div>
              )}

              <div>
                <FilterSectionLabel>Channel</FilterSectionLabel>
                <div className="flex flex-wrap gap-1.5">
                  <Chip
                    active={filterChannel === 'all'}
                    onClick={() => setFilterChannel('all')}
                    className="h-auto px-2.5 py-1 normal-case"
                  >
                    all
                  </Chip>
                  {channelOptions.map((ch) => (
                    <Chip
                      key={ch}
                      active={filterChannel === ch}
                      onClick={() => setFilterChannel(ch)}
                      className="h-auto px-2.5 py-1 normal-case"
                    >
                      {ch.replace(/_/g, ' ')}
                    </Chip>
                  ))}
                </div>
              </div>

              {hasActiveFilters && (
                <div>
                  <button
                    type="button"
                    onClick={clearAllFilters}
                    className="text-[12px] text-slate-500 hover:text-slate-800 transition-colors"
                  >
                    clear all
                  </button>
                </div>
              )}
            </div>
          </aside>

          <div className="col-span-12 lg:col-span-9">
            <div className="relative mb-6">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search investigations..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl border border-slate-200/70 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400/50"
              />
            </div>

            {filtered.length === 0 ? (
              <EmptyState
                title="No investigations match your filters"
                action={
                  hasActiveFilters ? (
                    <Button variant="secondary" onClick={clearAllFilters}>
                      Clear filters
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <Panel
                as="ul"
                className="rounded-[1.5rem] shadow-[0_20px_40px_-15px_rgba(15,23,42,0.05)] divide-y divide-slate-100"
              >
                {filtered.map((conv) => {
                  const ep = episodeMap.get(conv.correlationId);
                  const summary = pickThreadSummary(ep, conv.latestRun, conv.firstRun);
                  const isRunning = conv.latestRun.status === 'running';
                  const duration = fmtDuration(conv.latestRun.durationSeconds);

                  return (
                    <li key={conv.correlationId}>
                      <button
                        type="button"
                        onClick={() => router.push(`/team/agent-runs/${conv.latestRun.id}`)}
                        className={clsx(
                          'w-full text-left px-5 py-4',
                          listRowHoverClass,
                          isRunning && 'border-l-2 border-emerald-400',
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex flex-wrap items-center gap-2 mb-1.5">
                              <RunStatusBadge status={conv.latestRun.status} size="sm" />
                              {ep?.issue_type && (
                                <span className="font-mono text-[12px] text-slate-500">
                                  {ep.issue_type}
                                </span>
                              )}
                              {ep && (
                                <EpisodeResolutionBadge
                                  resolved={ep.resolved ?? false}
                                  size="sm"
                                  showIcon={false}
                                />
                              )}
                              <span className="text-xs text-slate-400 font-mono tabular-nums ml-auto">
                                {formatRelativeTime(conv.latestRun.startedAt)}
                              </span>
                            </div>

                            <p className="text-[14.5px] text-slate-900 leading-snug mb-2">
                              {summary}
                            </p>

                            {ep?.services && ep.services.length > 0 && (
                              <div className="flex gap-1.5 mb-2 flex-wrap">
                                {ep.services.slice(0, 5).map((s) => (
                                  <span
                                    key={s}
                                    className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md font-mono"
                                  >
                                    {s}
                                  </span>
                                ))}
                              </div>
                            )}

                            <div className="flex items-center gap-2 text-xs text-slate-400 flex-wrap">
                              <span className="inline-flex items-center gap-1 capitalize">
                                {triggerIcon(conv.latestRun.triggerSource)}
                                {conv.latestRun.triggerSource.replace(/_/g, ' ')}
                              </span>
                              {duration && !isRunning && (
                                <>
                                  <span>·</span>
                                  <span className="font-mono tabular-nums">{duration}</span>
                                </>
                              )}
                              {conv.turnCount > 1 && (
                                <>
                                  <span>·</span>
                                  <span className="font-mono tabular-nums">
                                    {conv.turnCount} turns
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </Panel>
            )}
          </div>
        </div>
      )}
    </TeamPageShell>
  );
}
