'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Clock } from 'lucide-react';
import { EpisodeResolutionBadge } from '@/components/RunStatusBadge';
import { formatRelativeTime } from '@/lib/formatRelativeTime';

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
}

const severityColors: Record<string, string> = {
  critical: 'bg-clay-light/15 text-clay-dark dark:bg-clay/20 dark:text-clay-light',
  warning: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  info: 'bg-forest-light/15 text-forest-dark dark:bg-forest/30 dark:text-forest-light',
};

const selectClass =
  'px-3 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-800';

function formatDuration(seconds: number | null): string | null {
  if (seconds == null) return null;
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
}

export default function EpisodesPage() {
  const searchParams = useSearchParams();
  const targetEpisodeId = searchParams.get('episode');

  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'resolved' | 'unresolved'>('all');
  const [issueTypeFilter, setIssueTypeFilter] = useState('all');
  const [sortBy, setSortBy] = useState<'newest' | 'effectiveness'>('newest');
  const [manualExpandedId, setManualExpandedId] = useState<string | null>(null);
  const scrolledToDeepLink = useRef(false);

  useEffect(() => {
    fetch('/api/memory/episodes')
      .then((r) => r.json())
      .then((data) => setEpisodes(data.episodes || []))
      .catch(() => setEpisodes([]))
      .finally(() => setLoading(false));
  }, []);

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

  const stats = useMemo(() => {
    const total = episodes.length;
    const resolved = episodes.filter((e) => e.resolved).length;
    const open = total - resolved;
    return { total, resolved, open };
  }, [episodes]);

  const issueTypes = useMemo(() => {
    const types = new Set<string>();
    for (const ep of episodes) {
      if (ep.issue_type) types.add(ep.issue_type);
    }
    return [...types].sort();
  }, [episodes]);

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

  const toggleExpand = (id: string) => {
    setManualExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-6">
      {!loading && episodes.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <span className="text-sm px-3 py-1 rounded-full border border-stone-200 dark:border-stone-600 text-stone-600 dark:text-stone-300">
            {stats.total} total
          </span>
          <span className="text-sm px-3 py-1 rounded-full border border-stone-200 dark:border-stone-600 text-stone-600 dark:text-stone-300">
            {stats.resolved} resolved
          </span>
          <span className="text-sm px-3 py-1 rounded-full border border-stone-200 dark:border-stone-600 text-stone-600 dark:text-stone-300">
            {stats.open} open
          </span>
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
      ) : episodes.length === 0 ? (
        <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-12 text-center">
          <p className="text-stone-500 dark:text-stone-400 mb-4">
            No episodes stored yet. Episodes are created automatically after investigations.
          </p>
          <Link
            href="/team/agent-runs"
            className="inline-flex items-center px-4 py-2 bg-forest hover:bg-forest-dark text-white rounded-lg text-sm font-medium transition-colors"
          >
            Start investigation
          </Link>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="text"
              placeholder="Search episodes..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="flex-1 min-w-[200px] px-3 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-800"
            />
            <select
              value={statusFilter}
              onChange={(e) =>
                setStatusFilter(e.target.value as 'all' | 'resolved' | 'unresolved')
              }
              className={selectClass}
            >
              <option value="all">All status</option>
              <option value="resolved">Resolved</option>
              <option value="unresolved">Unresolved</option>
            </select>
            <select
              value={issueTypeFilter}
              onChange={(e) => setIssueTypeFilter(e.target.value)}
              className={selectClass}
            >
              <option value="all">All issue types</option>
              {issueTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'newest' | 'effectiveness')}
              className={selectClass}
            >
              <option value="newest">Newest first</option>
              <option value="effectiveness">Most effective</option>
            </select>
          </div>

          {filteredEpisodes.length === 0 && !hasTargetEpisode ? (
            <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-8 text-center text-stone-500">
              No episodes match your filters.
            </div>
          ) : (
            <div className="space-y-3">
              {visibleEpisodes.map((ep) => {
                const expanded = expandedId === ep.episode_id;
                const duration = formatDuration(ep.duration_seconds);

                const isDeepLinkTarget = targetEpisodeId === ep.episode_id;

                return (
                  <div
                    key={ep.episode_id}
                    id={`episode-${ep.episode_id}`}
                    className={`w-full text-left bg-white dark:bg-stone-800 border rounded-xl p-4 transition-colors ${
                      isDeepLinkTarget && expanded
                        ? 'border-forest ring-1 ring-forest/30'
                        : 'border-stone-200 dark:border-stone-700 hover:border-stone-400 dark:hover:border-stone-600'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => toggleExpand(ep.episode_id)}
                      className="w-full text-left"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                          <EpisodeResolutionBadge resolved={ep.resolved} size="sm" />
                          <span className="text-sm font-medium text-stone-900 dark:text-white">
                            {ep.issue_type || 'unknown'}
                          </span>
                          {ep.severity && (
                            <span
                              className={`text-xs px-2 py-0.5 rounded-full ${
                                severityColors[ep.severity] ||
                                'bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-300'
                              }`}
                            >
                              {ep.severity}
                            </span>
                          )}
                        </div>

                        {ep.issue_description && (
                          <p
                            className={`text-sm text-stone-600 dark:text-stone-300 mb-2 ${
                              expanded ? '' : 'line-clamp-2'
                            }`}
                          >
                            {ep.issue_description}
                          </p>
                        )}

                        {ep.services.length > 0 && (
                          <div className="flex gap-1.5 mb-2 flex-wrap">
                            {(expanded ? ep.services : ep.services.slice(0, 3)).map((s) => (
                              <span
                                key={s}
                                className="text-xs bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 px-2 py-0.5 rounded"
                              >
                                {s}
                              </span>
                            ))}
                            {!expanded && ep.services.length > 3 && (
                              <span className="text-xs text-stone-400">
                                +{ep.services.length - 3} more
                              </span>
                            )}
                          </div>
                        )}

                        {ep.skills_used.length > 0 && (
                          <div className="flex gap-1.5 mb-2 flex-wrap">
                            {(expanded ? ep.skills_used : ep.skills_used.slice(0, 2)).map((s) => (
                              <span
                                key={s}
                                className="text-xs bg-forest-light/15 text-forest-dark dark:bg-forest/30 dark:text-forest-light px-2 py-0.5 rounded"
                              >
                                {s}
                              </span>
                            ))}
                            {!expanded && ep.skills_used.length > 2 && (
                              <span className="text-xs text-stone-400">
                                +{ep.skills_used.length - 2} more
                              </span>
                            )}
                          </div>
                        )}

                        {expanded && (
                          <>
                            {ep.summary && (
                              <p className="text-sm text-stone-600 dark:text-stone-300 mb-2">
                                {ep.summary}
                              </p>
                            )}
                            {ep.root_cause && (
                              <p className="text-sm text-stone-500 dark:text-stone-400 mb-2">
                                <span className="font-medium">Root cause:</span> {ep.root_cause}
                              </p>
                            )}
                            {ep.components.length > 0 && (
                              <div className="flex gap-1.5 mb-2 flex-wrap">
                                {ep.components.map((c) => (
                                  <span
                                    key={`${c.type}:${c.name}`}
                                    className="text-xs bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 px-2 py-0.5 rounded"
                                    title={c.type}
                                  >
                                    {c.type}:{c.name}
                                  </span>
                                ))}
                              </div>
                            )}
                          </>
                        )}

                        <div className="flex items-center gap-3 text-xs text-stone-400 flex-wrap">
                          {ep.created_at && (
                            <span>{formatRelativeTime(ep.created_at)}</span>
                          )}
                          {duration && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {duration}
                            </span>
                          )}
                        </div>
                        </div>
                      </div>
                    </button>

                    {ep.agent_run_id && (
                      <div className="mt-2 pt-2 border-t border-stone-100 dark:border-stone-700">
                        <Link
                          href={`/team/agent-runs/${ep.agent_run_id}`}
                          className="text-forest hover:text-forest-dark text-sm font-medium"
                        >
                          View run
                        </Link>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
