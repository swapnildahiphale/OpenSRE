'use client';

import { useState, useEffect, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Search, TrendingUp } from 'lucide-react';
import { EpisodeResolutionBadge } from '@/components/RunStatusBadge';
import { formatRelativeTime } from '@/lib/formatRelativeTime';

interface IssueTypeCount {
  issue_type: string;
  count: number;
}

interface RecentEpisode {
  episode_id: string;
  issue_type: string;
  issue_description?: string | null;
  resolved: boolean;
  summary: string | null;
  services?: string[];
  updated_at: string | null;
}

interface LatestStrategy {
  strategy_id: string;
  issue_type: string;
  component_key: string;
}

interface MemoryOverview {
  total_episodes: number;
  resolved: number;
  unresolved: number;
  resolution_rate: number;
  episodes_this_week: number;
  issue_type_counts: IssueTypeCount[];
  recent_episodes: RecentEpisode[];
  strategy_count: number;
  latest_strategies: LatestStrategy[];
}

const CARD_SURFACE =
  'bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl shadow-sm';

const EPISODE_CARD =
  'block rounded-xl border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-800 shadow-sm p-3 hover:border-stone-400 dark:hover:border-stone-600 transition-colors';

export default function MemoryPage() {
  const router = useRouter();
  const [overview, setOverview] = useState<MemoryOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetch('/api/memory/overview')
      .then((r) => r.json())
      .then(setOverview)
      .catch(() => setOverview(null))
      .finally(() => setLoading(false));
  }, []);

  const handleSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;
    router.push(`/team/memory/search?q=${encodeURIComponent(q)}`);
  };

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-20 bg-stone-200 dark:bg-stone-700 rounded-xl" />
        <div className="h-10 bg-stone-200 dark:bg-stone-700 rounded-xl" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="h-64 bg-stone-200 dark:bg-stone-700 rounded-xl" />
          <div className="h-64 bg-stone-200 dark:bg-stone-700 rounded-xl" />
        </div>
      </div>
    );
  }

  const data = overview ?? {
    total_episodes: 0,
    resolved: 0,
    unresolved: 0,
    resolution_rate: 0,
    episodes_this_week: 0,
    issue_type_counts: [],
    recent_episodes: [],
    strategy_count: 0,
    latest_strategies: [],
  };

  return (
    <div className="space-y-5">
      {/* Health strip */}
      <div className={`${CARD_SURFACE} p-4`}>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <div className="text-2xl font-bold text-forest">
              {data.resolution_rate}%
            </div>
            <div className="text-xs text-stone-500">Resolution rate</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-stone-900 dark:text-white">
              {data.total_episodes}
            </div>
            <div className="text-xs text-stone-500">Total episodes</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-stone-900 dark:text-white">
              +{data.episodes_this_week}
            </div>
            <div className="text-xs text-stone-500">This week</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-stone-900 dark:text-white">
              {data.strategy_count}
            </div>
            <div className="text-xs text-stone-500">Strategies</div>
          </div>
        </div>
      </div>

      {/* Compact search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search past investigations semantically..."
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-800"
          />
        </div>
        <button
          type="submit"
          disabled={!searchQuery.trim()}
          className="shrink-0 px-4 py-2 text-sm font-medium rounded-lg bg-forest hover:bg-forest-dark text-white disabled:opacity-50 transition-colors"
        >
          Search
        </button>
      </form>

      {/* Two-column body */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Recent episodes */}
        <div className={`${CARD_SURFACE} p-4`}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-stone-900 dark:text-white">
              Recent episodes
            </h2>
            <Link
              href="/team/memory/episodes"
              className="text-xs text-forest hover:text-forest-dark font-medium"
            >
              View all
            </Link>
          </div>

          {data.recent_episodes.length === 0 ? (
            <p className="text-sm text-stone-500 py-4 text-center">
              No episodes yet. Run an investigation to start building memory.
            </p>
          ) : (
            <div className="space-y-2">
              {data.recent_episodes.map((ep) => {
                const preview = ep.summary || ep.issue_description;
                const services = (ep.services ?? []).filter(Boolean).slice(0, 2);

                return (
                  <Link
                    key={ep.episode_id}
                    href={`/team/memory/episodes?episode=${encodeURIComponent(ep.episode_id)}`}
                    className={EPISODE_CARD}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-2 min-w-0 flex-wrap">
                        <EpisodeResolutionBadge resolved={ep.resolved} size="sm" />
                        <span className="text-sm font-medium text-stone-900 dark:text-white truncate">
                          {ep.issue_type || 'unknown'}
                        </span>
                      </div>
                      {ep.updated_at && (
                        <span className="shrink-0 text-xs text-stone-400">
                          {formatRelativeTime(ep.updated_at)}
                        </span>
                      )}
                    </div>

                    {preview && (
                      <p className="text-sm text-stone-600 dark:text-stone-300 line-clamp-2 mb-1.5">
                        {preview}
                      </p>
                    )}

                    {services.length > 0 && (
                      <div className="flex gap-1.5 flex-wrap">
                        {services.map((service) => (
                          <span
                            key={service}
                            className="text-xs bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 px-2 py-0.5 rounded"
                          >
                            {service}
                          </span>
                        ))}
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Patterns + strategies */}
        <div className="space-y-5">
          <div className={`${CARD_SURFACE} p-4`}>
            <h2 className="text-sm font-semibold text-stone-900 dark:text-white mb-3">
              Patterns
            </h2>
            {data.issue_type_counts.length === 0 ? (
              <p className="text-sm text-stone-500">No issue types recorded yet.</p>
            ) : (
              <ul className="space-y-2">
                {data.issue_type_counts.map((row) => (
                  <li
                    key={row.issue_type}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-stone-700 dark:text-stone-300 truncate pr-2">
                      {row.issue_type}
                    </span>
                    <span className="shrink-0 text-stone-500 tabular-nums">
                      {row.count}×
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className={`${CARD_SURFACE} p-4`}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-stone-900 dark:text-white flex items-center gap-1.5">
                <TrendingUp className="w-4 h-4 text-forest" />
                Top strategies
              </h2>
              <Link
                href="/team/memory/strategies"
                className="text-xs text-forest hover:text-forest-dark font-medium"
              >
                View all
              </Link>
            </div>

            {data.latest_strategies.length === 0 ? (
              <p className="text-sm text-stone-500">
                No strategies generated yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {data.latest_strategies.map((st) => (
                  <li key={st.strategy_id}>
                    <Link
                      href="/team/memory/strategies"
                      className="block text-sm hover:bg-stone-50 dark:hover:bg-stone-700/50 -mx-2 px-2 py-1.5 rounded-lg transition-colors"
                    >
                      <span className="font-medium text-stone-900 dark:text-white">
                        {st.issue_type || 'unknown'}
                      </span>
                      {st.component_key && (
                        <span className="text-stone-500"> · {st.component_key}</span>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
