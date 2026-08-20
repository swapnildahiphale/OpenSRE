'use client';

import { useState, useEffect, FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, Search } from 'lucide-react';
import { formatRelativeTime } from '@/lib/formatRelativeTime';
import { Panel, Skeleton, listRowHoverClass } from '@/components/ui-flow';

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

const SPARK_HEIGHTS = [30, 45, 35, 60, 50, 90, 75];

function issueTypeTone(issueType?: string | null): string {
  if (!issueType) return 'text-slate-600';
  const key = issueType.toLowerCase();
  if (key.includes('auth') || key.includes('security')) return 'text-rose-700';
  if (key.includes('resource') || key.includes('oom')) return 'text-amber-700';
  if (key.includes('latency') || key.includes('performance')) return 'text-emerald-700';
  return 'text-slate-600';
}

const ISSUE_TYPE_INITIAL = 5;
const ISSUE_TYPE_BATCH = 5;
const ISSUE_TYPE_MAX = 12;

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

export default function MemoryPage() {
  const router = useRouter();
  const [overview, setOverview] = useState<MemoryOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [issueTypeVisibleCount, setIssueTypeVisibleCount] = useState(ISSUE_TYPE_INITIAL);

  useEffect(() => {
    fetch('/api/memory/overview')
      .then((r) => r.json())
      .then(setOverview)
      .catch(() => setOverview(null))
      .finally(() => setLoading(false));
  }, []);

  const handleSidebarSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;
    router.push(`/team/memory/search?q=${encodeURIComponent(q)}`);
  };

  if (loading) {
    return (
      <div className="space-y-10">
        <div className="grid grid-cols-12 gap-8">
          <Skeleton className="col-span-12 md:col-span-4 h-56 rounded-[2rem]" />
          <div className="col-span-12 md:col-span-8 grid grid-cols-3 gap-x-10">
            <Skeleton className="h-24 rounded-lg" />
            <Skeleton className="h-24 rounded-lg" />
            <Skeleton className="h-24 rounded-lg" />
          </div>
        </div>
        <Skeleton className="h-72 w-full rounded-[2rem]" />
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

  const topPattern = data.issue_type_counts[0];
  const patternCount = data.issue_type_counts.length;
  const visibleIssueTypes = data.issue_type_counts.slice(
    0,
    Math.min(issueTypeVisibleCount, ISSUE_TYPE_MAX),
  );
  const canExpandIssueTypes =
    issueTypeVisibleCount < Math.min(data.issue_type_counts.length, ISSUE_TYPE_MAX);

  const expandIssueTypes = () => {
    setIssueTypeVisibleCount((n) =>
      Math.min(n + ISSUE_TYPE_BATCH, ISSUE_TYPE_MAX, data.issue_type_counts.length),
    );
  };

  return (
    <div className="space-y-10">
      {/* Stats row — Option 1 Corpus */}
      <section className="grid grid-cols-12 gap-8 items-start">
        <div className="col-span-12 md:col-span-4">
          <div
            className="relative overflow-hidden rounded-[2rem] border border-slate-200/70 p-6 shadow-[0_20px_40px_-15px_rgba(15,23,42,0.05)] flex flex-col min-h-[224px]"
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
                  Total episodes
                </span>
                {data.episodes_this_week > 0 && (
                  <span className="inline-flex items-center h-7 px-3 rounded-full text-xs font-medium bg-emerald-100/70 text-emerald-800 border border-emerald-200/80">
                    Growing
                  </span>
                )}
              </div>
              <div className="mt-4 flex items-baseline gap-2.5">
                <span className="text-6xl font-medium tracking-tighter text-emerald-800 font-mono tabular-nums leading-none">
                  {data.total_episodes}
                </span>
                {data.episodes_this_week > 0 && (
                  <span className="text-emerald-600 font-mono text-sm font-medium">
                    / +{data.episodes_this_week} this week
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
              <div className="mt-auto pt-5 grid grid-cols-3 gap-3 text-sm">
                <div>
                  <div className="font-mono tabular-nums text-slate-900 text-base font-medium">
                    {data.resolved}
                  </div>
                  <div className="text-slate-500 mt-0.5 text-[11px] uppercase tracking-wider">
                    resolved
                  </div>
                </div>
                <div>
                  <div className="font-mono tabular-nums text-slate-900 text-base font-medium">
                    {data.unresolved}
                  </div>
                  <div className="text-slate-500 mt-0.5 text-[11px] uppercase tracking-wider">
                    unresolved
                  </div>
                </div>
                <div>
                  <div className="font-mono tabular-nums text-slate-900 text-base font-medium">
                    {patternCount}
                  </div>
                  <div className="text-slate-500 mt-0.5 text-[11px] uppercase tracking-wider">
                    patterns
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="col-span-12 md:col-span-8 grid grid-cols-3 gap-x-10 px-2 content-start">
          <Link
            href="/team/memory/episodes"
            className="border-t border-slate-200 pt-6 block hover:text-emerald-700 transition-colors"
          >
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Resolution</div>
            <div className="mt-4 text-4xl font-medium tracking-tight font-mono tabular-nums text-slate-900">
              {data.resolution_rate}%
            </div>
            <div className="mt-2 text-xs text-slate-400">root cause identified</div>
          </Link>
          <Link
            href="/team/memory/strategies"
            className="border-t border-slate-200 pt-6 block hover:text-emerald-700 transition-colors"
          >
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Strategies</div>
            <div className="mt-4 text-4xl font-medium tracking-tight font-mono tabular-nums text-slate-900">
              {data.strategy_count}
            </div>
            <div className="mt-2 text-xs text-slate-400">playbooks learned</div>
          </Link>
          <div className="border-t border-slate-200 pt-6">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Top pattern</div>
            {topPattern ? (
              <>
                <div className="mt-4 text-4xl font-medium tracking-tight font-mono tabular-nums text-slate-900">
                  {topPattern.count}
                </div>
                <div
                  className="mt-2 text-xs text-slate-400 truncate"
                  title={topPattern.issue_type}
                >
                  {topPattern.issue_type}
                </div>
              </>
            ) : (
              <div className="mt-4 text-4xl font-medium tracking-tight font-mono tabular-nums text-slate-400">
                —
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Recent episodes + issue-type tag cloud */}
      <section className="grid grid-cols-12 gap-8">
        <div className="col-span-12 md:col-span-8">
          <div className="flex items-end justify-between mb-4">
            <h2 className="text-xl font-medium tracking-tight text-slate-900">Recent episodes</h2>
            <Link
              href="/team/memory/episodes"
              className="text-sm text-emerald-700 font-medium hover:underline inline-flex items-center gap-1"
            >
              All episodes
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <Panel className="rounded-[2.5rem] shadow-[0_20px_40px_-15px_rgba(15,23,42,0.05)]">
            {data.recent_episodes.length === 0 ? (
              <p className="px-5 py-10 text-sm text-slate-500 text-center">
                No episodes yet. Run an investigation to start building memory.
              </p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.recent_episodes.map((ep, idx) => {
                  const services = (ep.services ?? []).filter(Boolean).slice(0, 3);
                  const isFirst = idx === 0;
                  const isLast = idx === data.recent_episodes.length - 1;

                  return (
                    <li key={ep.episode_id}>
                      <Link
                        href={`/team/memory/episodes?episode=${encodeURIComponent(ep.episode_id)}`}
                        className={`block px-5 py-4 ${listRowHoverClass} ${
                          isFirst ? 'rounded-t-[1.75rem]' : ''
                        } ${isLast ? 'rounded-b-[1.75rem]' : ''}`}
                      >
                        <div className="flex items-start gap-3">
                          <ResolutionPill resolved={ep.resolved} />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2 mb-1 text-xs text-slate-500">
                              <span
                                className={`font-medium ${issueTypeTone(ep.issue_type)}`}
                              >
                                {ep.issue_type || 'unknown'}
                              </span>
                              {ep.updated_at && (
                                <span className="font-mono tabular-nums">
                                  {formatRelativeTime(ep.updated_at)}
                                </span>
                              )}
                            </div>
                            {ep.issue_description ? (
                              <p className="text-sm text-slate-600 leading-snug line-clamp-2">
                                {ep.issue_description}
                              </p>
                            ) : (
                              <p className="text-sm text-slate-400">—</p>
                            )}
                            {services.length > 0 && (
                              <div className="mt-2 flex gap-1.5 flex-wrap">
                                {services.map((service) => (
                                  <span
                                    key={service}
                                    className="inline-flex items-center h-6 px-2.5 rounded-full text-[11px] font-medium bg-slate-50 text-slate-600 border border-slate-200/80"
                                  >
                                    {service}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
        </div>

        <aside className="col-span-12 md:col-span-4 space-y-8">
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500 mb-4">
              Issue types
            </div>
            {data.issue_type_counts.length === 0 ? (
              <p className="text-sm text-slate-500">No issue types recorded yet.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {visibleIssueTypes.map((row, i) => (
                  <Link
                    key={row.issue_type}
                    href={`/team/memory/episodes?issue_type=${encodeURIComponent(row.issue_type)}`}
                    className={`inline-flex items-center h-7 px-2.5 rounded-full text-xs font-medium font-mono transition ${
                      i < 3
                        ? 'bg-emerald-100/70 text-emerald-800 border border-emerald-200/80'
                        : 'bg-slate-50 text-slate-600 border border-slate-200/80 hover:bg-slate-100'
                    }`}
                  >
                    #{row.issue_type} ·{row.count}
                  </Link>
                ))}
                {canExpandIssueTypes && (
                  <button
                    type="button"
                    onClick={expandIssueTypes}
                    className="inline-flex items-center h-7 px-2.5 rounded-full text-xs font-medium font-mono border border-slate-200/70 bg-slate-50 text-slate-500 hover:bg-slate-100 hover:border-slate-300 hover:text-slate-600 transition"
                    aria-label="Show more issue types"
                    title="Show more issue types"
                  >
                    …
                  </button>
                )}
              </div>
            )}
          </div>

          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500 mb-4">
              Semantic search
            </div>
            <form onSubmit={handleSidebarSearch} className="relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search past investigations…"
                className="w-full h-11 pl-10 pr-4 rounded-full border border-slate-200/80 bg-white text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-300"
              />
            </form>
            <p className="mt-2 text-xs text-slate-400">Opens the Search tab with your query</p>
          </div>
        </aside>
      </section>

      {/* Pattern activity + latest strategies */}
      <section className="grid grid-cols-12 gap-8">
        <div className="col-span-12 md:col-span-5">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500 mb-4">
            Pattern activity · 14d
          </div>
          <div className="rounded-[2.5rem] border border-slate-200/70 p-6 overflow-hidden relative bg-white shadow-[0_20px_40px_-15px_rgba(15,23,42,0.05)]">
            {data.issue_type_counts.length === 0 ? (
              <p className="text-sm text-slate-500">No pattern activity yet.</p>
            ) : (
              <>
                <div className="absolute right-6 top-6 font-mono text-[11px] text-slate-400">
                  live ·
                </div>
                <div className="relative h-24 overflow-hidden">
                  <div className="absolute inset-0 flex items-center gap-6 whitespace-nowrap carousel-track">
                    {[...data.issue_type_counts, ...data.issue_type_counts].map((row, i) => (
                      <span key={`${row.issue_type}-${i}`} className="inline-flex items-center gap-2">
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            i % 2 === 0 ? 'bg-emerald-500' : 'bg-slate-400'
                          }`}
                        />
                        <span className="text-sm text-slate-700">{row.issue_type}</span>
                        <span className="font-mono text-xs text-slate-400">
                          {row.count} episode{row.count === 1 ? '' : 's'}
                        </span>
                      </span>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="col-span-12 md:col-span-7">
          <div className="flex items-end justify-between mb-4">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
              Latest strategies
            </div>
            <Link
              href="/team/memory/strategies"
              className="text-sm text-emerald-700 font-medium hover:underline"
            >
              Strategies →
            </Link>
          </div>
          {data.latest_strategies.length === 0 ? (
            <p className="text-sm text-slate-500">No strategies generated yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.latest_strategies.map((st) => (
                <li key={st.strategy_id} className="py-4 flex gap-5">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2 mb-1">
                      <span className="font-mono text-[12px] text-slate-500">
                        {st.issue_type || 'unknown'}
                      </span>
                      {st.component_key && (
                        <>
                          <span className="text-slate-400">·</span>
                          <span className="text-xs text-slate-400">{st.component_key}</span>
                        </>
                      )}
                    </div>
                    <Link
                      href="/team/memory/strategies"
                      className="text-sm text-slate-700 leading-relaxed hover:text-emerald-700 transition-colors"
                    >
                      View playbook →
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
