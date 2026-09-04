'use client';

import type { ReactNode } from 'react';
import { useState, useEffect, useMemo, useRef } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { clsx } from 'clsx';
import { ChevronDown, Clock, RotateCw, Search } from 'lucide-react';
import { formatRelativeTime } from '@/lib/formatRelativeTime';
import { Button, Chip, EmptyState, Panel, Skeleton, listRowHoverClass } from '@/components/ui-flow';

interface Component {
  type: string;
  name: string;
}

interface Episode {
  episode_id: string;
  agent_run_id: string | null;
  issue_type: string;
  issue_description: string;
  severity: string | null;
  components: Component[];
  services: string[];
  skills_used: string[];
  resolved: boolean;
  root_cause: string | null;
  summary: string | null;
  effectiveness_score: number | null;
  duration_seconds: number | null;
  created_at: string | null;
  extraction_status?: 'ok' | 'failed';
}

const ISSUE_TYPE_INITIAL = 5;
const ISSUE_TYPE_BATCH = 5;
const ISSUE_TYPE_MAX = 12;

const severityColors: Record<string, string> = {
  critical: 'bg-red-100/80 text-red-700',
  warning: 'bg-amber-100/80 text-amber-900',
  info: 'bg-emerald-100/50 text-emerald-800',
};

const NEUTRAL_CHIP =
  'inline-flex items-center h-6 px-2.5 rounded-full text-[11px] font-medium bg-slate-50 text-slate-600 border border-slate-200/80';

function FilterSectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500 mb-3">{children}</div>
  );
}

function StatusFilterItem({
  active,
  label,
  count,
  onClick,
}: {
  active: boolean;
  label: string;
  count?: number;
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
        {count != null && (
          <span className="ml-auto font-mono text-[11px] text-slate-400 tabular-nums">{count}</span>
        )}
      </button>
    </li>
  );
}

function ResolutionPill({ resolved }: { resolved: boolean }) {
  return (
    <span
      className={
        resolved
          ? 'inline-flex items-center h-5 px-2 rounded-full text-[10px] font-medium tracking-wide bg-emerald-100/70 text-emerald-800'
          : 'inline-flex items-center h-5 px-2 rounded-full text-[10px] font-medium tracking-wide bg-amber-100/80 text-amber-900'
      }
    >
      {resolved ? 'resolved' : 'open'}
    </span>
  );
}

function formatDuration(seconds: number | null): string | null {
  if (seconds == null) return null;
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
}

export default function EpisodesPage() {
  const searchParams = useSearchParams();
  const targetEpisodeId = searchParams.get('episode');
  const initialIssueType = searchParams.get('issue_type');

  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'resolved' | 'unresolved'>('all');
  const [issueTypeFilter, setIssueTypeFilter] = useState(initialIssueType ?? 'all');
  const [sortBy, setSortBy] = useState<'newest' | 'effectiveness'>('newest');
  const [issueTypeVisibleCount, setIssueTypeVisibleCount] = useState(ISSUE_TYPE_INITIAL);
  const [manualExpandedId, setManualExpandedId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const scrolledToDeepLink = useRef(false);

  useEffect(() => {
    if (initialIssueType) setIssueTypeFilter(initialIssueType);
  }, [initialIssueType]);

  useEffect(() => {
    fetch('/api/memory/episodes')
      .then((r) => r.json())
      .then((data) => setEpisodes(data.episodes || []))
      .catch(() => setEpisodes([]))
      .finally(() => setLoading(false));
  }, []);

  const issueTypeFreqs = useMemo(() => {
    const counts = new Map<string, number>();
    for (const ep of episodes) {
      if (ep.issue_type) counts.set(ep.issue_type, (counts.get(ep.issue_type) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => b.count - a.count);
  }, [episodes]);

  const visiblePatterns = issueTypeFreqs.slice(
    0,
    Math.min(issueTypeVisibleCount, ISSUE_TYPE_MAX),
  );
  const canExpandPatterns =
    issueTypeVisibleCount < Math.min(issueTypeFreqs.length, ISSUE_TYPE_MAX);

  const expandPatterns = () => {
    setIssueTypeVisibleCount((n) =>
      Math.min(n + ISSUE_TYPE_BATCH, ISSUE_TYPE_MAX, issueTypeFreqs.length),
    );
  };

  const stats = useMemo(() => {
    const total = episodes.length;
    const resolved = episodes.filter((e) => e.resolved).length;
    const open = total - resolved;
    return { total, resolved, open };
  }, [episodes]);

  const hasTargetEpisode = useMemo(
    () => Boolean(targetEpisodeId && episodes.some((ep) => ep.episode_id === targetEpisodeId)),
    [targetEpisodeId, episodes],
  );

  const expandedId = useMemo(() => {
    if (manualExpandedId !== null) return manualExpandedId;
    if (hasTargetEpisode) return targetEpisodeId;
    return null;
  }, [manualExpandedId, hasTargetEpisode, targetEpisodeId]);

  useEffect(() => {
    if (!hasTargetEpisode || scrolledToDeepLink.current) return;
    scrolledToDeepLink.current = true;
    requestAnimationFrame(() => {
      document
        .getElementById(`episode-${targetEpisodeId}`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }, [hasTargetEpisode, targetEpisodeId]);

  const filteredEpisodes = useMemo(() => {
    let result = [...episodes];

    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      result = result.filter(
        (ep) =>
          ep.issue_description?.toLowerCase().includes(q) ||
          ep.issue_type?.toLowerCase().includes(q) ||
          ep.summary?.toLowerCase().includes(q) ||
          ep.root_cause?.toLowerCase().includes(q) ||
          ep.services.some((s) => s.toLowerCase().includes(q)),
      );
    }

    if (statusFilter === 'resolved') result = result.filter((e) => e.resolved);
    if (statusFilter === 'unresolved') result = result.filter((e) => !e.resolved);

    if (issueTypeFilter !== 'all') {
      result = result.filter((e) => e.issue_type === issueTypeFilter);
    }

    if (sortBy === 'newest') {
      result.sort((a, b) => {
        const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
        const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
        return tb - ta;
      });
    } else {
      result.sort((a, b) => {
        const ea = a.effectiveness_score ?? -1;
        const eb = b.effectiveness_score ?? -1;
        return eb - ea;
      });
    }

    return result;
  }, [episodes, searchText, statusFilter, issueTypeFilter, sortBy]);

  const visibleEpisodes = useMemo(() => {
    if (!targetEpisodeId) return filteredEpisodes;
    const pinned = episodes.find((ep) => ep.episode_id === targetEpisodeId);
    if (!pinned || filteredEpisodes.some((ep) => ep.episode_id === targetEpisodeId)) {
      return filteredEpisodes;
    }
    return [pinned, ...filteredEpisodes];
  }, [episodes, filteredEpisodes, targetEpisodeId]);

  const hasActiveFilters =
    statusFilter !== 'all' ||
    issueTypeFilter !== 'all' ||
    searchText.trim().length > 0;

  const clearAllFilters = () => {
    setStatusFilter('all');
    setIssueTypeFilter('all');
    setSearchText('');
  };

  const toggleExpand = (id: string) => {
    setManualExpandedId((prev) => (prev === id ? null : id));
  };

  const retryExtract = async (episodeId: string) => {
    setRetryingId(episodeId);
    try {
      const res = await fetch(`/api/memory/episodes/${episodeId}/reextract`, {
        method: 'POST',
      });
      const data = await res.json();
      if (res.ok && data.episode) {
        setEpisodes((prev) =>
          prev.map((ep) => (ep.episode_id === episodeId ? data.episode : ep)),
        );
      }
    } catch {
      // leave row as failed
    } finally {
      setRetryingId(null);
    }
  };

  if (loading) {
    return (
      <div className="grid grid-cols-12 gap-10">
        <Skeleton className="col-span-12 lg:col-span-3 h-64 rounded-xl" />
        <div className="col-span-12 lg:col-span-9 space-y-4">
          <Skeleton className="h-11 w-full rounded-xl" />
          <Skeleton className="h-48 w-full rounded-[2rem]" />
          <Skeleton className="h-48 w-full rounded-[2rem]" />
        </div>
      </div>
    );
  }

  if (episodes.length === 0) {
    return (
      <EmptyState
        title="No episodes yet"
        description="Episodes are created automatically after investigations."
        action={
          <Link href="/team/agent-runs">
            <Button variant="primary">Start investigation</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="grid grid-cols-12 gap-10">
      <aside className="col-span-12 lg:col-span-3">
        <div className="sticky top-[80px] space-y-8">
          <div>
            <FilterSectionLabel>Status</FilterSectionLabel>
            <ul className="space-y-1.5">
              <StatusFilterItem
                label="All"
                count={stats.total}
                active={statusFilter === 'all'}
                onClick={() => setStatusFilter('all')}
              />
              <StatusFilterItem
                label="Resolved"
                count={stats.resolved}
                active={statusFilter === 'resolved'}
                onClick={() => setStatusFilter('resolved')}
              />
              <StatusFilterItem
                label="Open"
                count={stats.open}
                active={statusFilter === 'unresolved'}
                onClick={() => setStatusFilter('unresolved')}
              />
            </ul>
          </div>

          {issueTypeFreqs.length > 0 && (
            <div>
              <FilterSectionLabel>Patterns</FilterSectionLabel>
              <div className="flex flex-wrap gap-1.5">
                <Chip
                  active={issueTypeFilter === 'all'}
                  onClick={() => setIssueTypeFilter('all')}
                  className="h-auto px-2.5 py-1 normal-case"
                >
                  all
                </Chip>
                {visiblePatterns.map(({ value, count }) => (
                  <Chip
                    key={value}
                    active={issueTypeFilter === value}
                    onClick={() => setIssueTypeFilter(value)}
                    title={value}
                    className="h-auto max-w-full px-2.5 py-1 font-mono normal-case text-left whitespace-normal break-words"
                  >
                    {value} ·{count}
                  </Chip>
                ))}
                {canExpandPatterns && (
                  <button
                    type="button"
                    onClick={expandPatterns}
                    className="px-2.5 py-1 rounded-full text-xs font-medium border border-slate-200/70 bg-slate-50 text-slate-500 hover:bg-slate-100 hover:border-slate-300 hover:text-slate-600 transition"
                    aria-label="Show more patterns"
                    title="Show more patterns"
                  >
                    …
                  </button>
                )}
              </div>
            </div>
          )}

          <div>
            <FilterSectionLabel>Sort</FilterSectionLabel>
            <ul className="space-y-1.5">
              <StatusFilterItem
                label="Newest first"
                active={sortBy === 'newest'}
                onClick={() => setSortBy('newest')}
              />
              <StatusFilterItem
                label="Most effective"
                active={sortBy === 'effectiveness'}
                onClick={() => setSortBy('effectiveness')}
              />
            </ul>
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

      <div className="col-span-12 lg:col-span-9 space-y-5">
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search episodes…"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full h-11 pl-10 pr-4 rounded-xl border border-slate-200/70 bg-white text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-300"
          />
        </div>

        {filteredEpisodes.length === 0 && !hasTargetEpisode ? (
          <EmptyState
            title="No episodes match your filters"
            action={
              hasActiveFilters ? (
                <Button variant="secondary" onClick={clearAllFilters}>
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        ) : (
          <Panel className="rounded-[2.5rem] shadow-[0_20px_40px_-15px_rgba(15,23,42,0.05)] divide-y divide-slate-100">
            {visibleEpisodes.map((ep) => {
              const expanded = expandedId === ep.episode_id;
              const duration = formatDuration(ep.duration_seconds);
              const isDeepLinkTarget = targetEpisodeId === ep.episode_id;

              return (
                <div
                  key={ep.episode_id}
                  id={`episode-${ep.episode_id}`}
                  className={clsx(
                    'px-6 py-5',
                    listRowHoverClass,
                    isDeepLinkTarget && expanded && 'ring-1 ring-emerald-500/30 border-emerald-500',
                  )}
                >
                  <button
                    type="button"
                    onClick={() => toggleExpand(ep.episode_id)}
                    className="w-full text-left"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <ResolutionPill resolved={ep.resolved} />
                          <span className="text-[14.5px] text-slate-900">
                            {ep.issue_type || 'unknown'}
                          </span>
                          {ep.extraction_status === 'failed' && (
                            <span className="inline-flex items-center h-5 px-2 rounded-full text-[10px] font-medium tracking-wide bg-slate-100 text-slate-600">
                              couldn’t summarize
                            </span>
                          )}
                          {ep.severity && (
                            <span
                              className={clsx(
                                'text-[11px] px-2 py-0.5 rounded-full',
                                severityColors[ep.severity] ??
                                  'bg-slate-100 text-slate-700',
                              )}
                            >
                              {ep.severity}
                            </span>
                          )}
                        </div>

                        {ep.issue_description && (
                          <p
                            className={clsx(
                              'text-sm text-slate-600 mb-2',
                              !expanded && 'line-clamp-2',
                            )}
                          >
                            {ep.issue_description}
                          </p>
                        )}

                        {ep.services.length > 0 && (
                          <div className="flex gap-1.5 mb-2 flex-wrap">
                            {(expanded ? ep.services : ep.services.slice(0, 3)).map((s) => (
                              <span key={s} className={NEUTRAL_CHIP}>
                                {s}
                              </span>
                            ))}
                            {!expanded && ep.services.length > 3 && (
                              <span className="text-xs text-slate-400">
                                +{ep.services.length - 3} more
                              </span>
                            )}
                          </div>
                        )}

                        <div className="flex items-center gap-3 text-xs text-slate-400 flex-wrap">
                          {ep.created_at && (
                            <span className="font-mono tabular-nums">
                              {formatRelativeTime(ep.created_at)}
                            </span>
                          )}
                          {duration && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              <span className="font-mono">{duration}</span>
                            </span>
                          )}
                        </div>
                      </div>
                      <ChevronDown
                        className={clsx(
                          'w-5 h-5 text-slate-400 shrink-0 mt-1 transition-transform',
                          expanded && 'rotate-180',
                        )}
                      />
                    </div>
                  </button>

                  {expanded && (
                    <div className="mt-4 pt-4 border-t border-slate-100">
                      {ep.summary && (
                        <p className="text-sm text-slate-600 mb-3">{ep.summary}</p>
                      )}
                      {ep.root_cause && (
                        <p className="text-sm text-slate-500 mb-3">
                          <span className="font-medium text-slate-700">Root cause:</span>{' '}
                          {ep.root_cause}
                        </p>
                      )}
                      {ep.skills_used.length > 0 && (
                        <div className="flex gap-1.5 mb-3 flex-wrap">
                          {ep.skills_used.map((s) => (
                            <span key={s} className={NEUTRAL_CHIP}>
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                      {ep.components.length > 0 && (
                        <div className="flex gap-1.5 mb-3 flex-wrap">
                          {ep.components.map((c) => (
                            <span key={`${c.type}:${c.name}`} className={NEUTRAL_CHIP} title={c.type}>
                              {c.type}:{c.name}
                            </span>
                          ))}
                        </div>
                      )}
                      {ep.extraction_status === 'failed' && (
                        <div className="flex items-center justify-between gap-3 mb-4">
                          <p className="text-sm text-slate-500">Couldn’t summarize this investigation.</p>
                          <button
                            type="button"
                            disabled={retryingId === ep.episode_id}
                            onClick={(e) => {
                              e.stopPropagation();
                              void retryExtract(ep.episode_id);
                            }}
                            className="inline-flex items-center gap-1.5 text-sm text-emerald-700 hover:underline disabled:opacity-50"
                          >
                            <RotateCw className="w-3.5 h-3.5" />
                            Retry
                          </button>
                        </div>
                      )}
                      {ep.effectiveness_score != null && (
                        <p className="text-xs text-slate-500 mb-4">
                          Effectiveness{' '}
                          <span className="font-mono text-slate-700">
                            {ep.effectiveness_score.toFixed(2)}
                          </span>
                        </p>
                      )}
                      {ep.agent_run_id && (
                        <Link
                          href={`/team/agent-runs/${ep.agent_run_id}`}
                          className="text-sm text-emerald-700 font-medium hover:underline"
                        >
                          Open investigation →
                        </Link>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </Panel>
        )}
      </div>
    </div>
  );
}
