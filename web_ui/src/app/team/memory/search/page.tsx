'use client';

import { useState, useMemo, useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Search } from 'lucide-react';
import { Button, Panel, Skeleton, listRowHoverClass } from '@/components/ui-flow';

interface Component {
  type: string;
  name: string;
}

interface SearchResult {
  episode_id: string;
  issue_type: string;
  issue_description: string;
  components: Component[];
  services: string[];
  resolved: boolean;
  root_cause: string | null;
  summary: string;
  effectiveness_score: number;
  score: number;
  skills_used: string[];
}

const EXAMPLE_QUERIES = [
  '503 errors on payments-service',
  'pod crashloop in cart namespace',
  'high database query latency',
];

const NEUTRAL_CHIP =
  'inline-flex items-center h-6 px-2.5 rounded-full text-[11px] font-medium bg-slate-50 text-slate-600 border border-slate-200/80';

const inputClass =
  'w-full border border-slate-200/70 rounded-xl bg-white text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-300';

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

export default function MemorySearchPage() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get('q') ?? '';

  const [query, setQuery] = useState(initialQuery);
  const [issueTypeFilter, setIssueTypeFilter] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (searchQuery?: string) => {
    const q = (searchQuery ?? query).trim();
    if (!q) return;
    setLoading(true);
    setSearched(true);
    try {
      const resp = await fetch('/api/memory/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      });
      const data = await resp.json();
      let hits: SearchResult[] = data.results || [];
      if (issueTypeFilter) {
        const needle = issueTypeFilter.toLowerCase();
        hits = hits.filter((h) => (h.issue_type || '').toLowerCase().includes(needle));
      }
      setResults(hits);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!initialQuery.trim()) return;
    setQuery(initialQuery);
    handleSearch(initialQuery);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  const sortedResults = useMemo(
    () => [...results].sort((a, b) => b.score - a.score),
    [results],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSearch();
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <div className="rounded-[2rem] bg-white border border-slate-200/70 p-6 shadow-[0_20px_40px_-15px_rgba(15,23,42,0.05)]">
        <div className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Incident description
            </label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe the incident symptoms, affected services, and error patterns…"
              className={`${inputClass} p-3 resize-none`}
              rows={4}
            />
          </div>

          <div>
            <p className="text-xs text-slate-500 mb-2">Try an example:</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_QUERIES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setQuery(example)}
                  className="text-xs px-2.5 py-1 rounded-full border border-slate-200 text-slate-600 hover:border-emerald-300 hover:text-emerald-700 transition"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Pattern filter{' '}
              <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <input
              value={issueTypeFilter}
              onChange={(e) => setIssueTypeFilter(e.target.value)}
              placeholder="e.g., connection-pool-exhaustion"
              className={`${inputClass} h-9 px-3`}
            />
          </div>

          <Button
            variant="primary"
            onClick={() => handleSearch()}
            disabled={loading || !query.trim()}
            className="w-full justify-center h-10 rounded-xl"
          >
            <Search className="w-4 h-4" />
            {loading ? 'Searching…' : 'Search memory'}
          </Button>
          <p className="text-xs text-slate-400 text-center">Press Enter to search</p>
        </div>
      </div>

      <div className="space-y-4">
        {!searched && !loading && (
          <details className="rounded-xl border border-slate-200/60 bg-slate-50/50 px-4 py-3 text-sm text-slate-500">
            <summary className="cursor-pointer font-medium text-slate-600">
              How similarity search works
            </summary>
            <ul className="list-disc list-inside mt-2 space-y-1 text-xs">
              <li>Describe symptoms, affected services, and error patterns</li>
              <li>More specific queries yield better matches</li>
              <li>Results ranked by semantic similarity to past episodes</li>
              <li>Use the pattern filter to narrow results after searching</li>
            </ul>
          </details>
        )}

        {loading && (
          <>
            {[1, 2].map((i) => (
              <Skeleton key={i} className="h-48 w-full rounded-[1.5rem]" />
            ))}
          </>
        )}

        {searched && !loading && sortedResults.length === 0 && (
          <Panel className="rounded-[1.5rem] p-8 text-center shadow-[0_12px_30px_-12px_rgba(15,23,42,0.06)]">
            <p className="text-slate-700 font-medium mb-2">No similar investigations found</p>
            <p className="text-sm text-slate-500 mb-3">
              Try broadening your description or removing the pattern filter.
            </p>
            <ul className="text-sm text-slate-400 space-y-1">
              <li>Include service names and error codes when possible</li>
              <li>Check that past investigations have been stored as episodes</li>
            </ul>
          </Panel>
        )}

        {searched && !loading && sortedResults.length > 0 && (
          <>
            <p className="text-sm text-slate-500">
              {sortedResults.length} similar investigation
              {sortedResults.length !== 1 ? 's' : ''} found
            </p>
            {sortedResults.map((r) => {
              const matchPct = Math.round(r.score * 100);
              return (
                <div
                  key={r.episode_id}
                  className={`rounded-[1.5rem] bg-white border border-slate-200/70 p-5 shadow-[0_12px_30px_-12px_rgba(15,23,42,0.06)] ${listRowHoverClass}`}
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <span className="text-2xl font-semibold text-emerald-600 font-mono tabular-nums">
                      {matchPct}%
                    </span>
                    <span className="text-xs text-slate-400">match</span>
                  </div>

                  <div className="h-1 bg-slate-100 rounded-full mb-4 overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{ width: `${matchPct}%` }}
                    />
                  </div>

                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <ResolutionPill resolved={r.resolved} />
                    <span className="text-[14.5px] text-slate-900">
                      {r.issue_type || 'unknown'}
                    </span>
                  </div>

                  {r.issue_description && (
                    <p className="text-sm text-slate-600 mb-3">{r.issue_description}</p>
                  )}

                  {r.services?.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap mb-2">
                      {r.services.map((s) => (
                        <span key={s} className={NEUTRAL_CHIP}>
                          {s}
                        </span>
                      ))}
                    </div>
                  )}

                  {r.skills_used?.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap mb-4">
                      {r.skills_used.map((s) => (
                        <span key={s} className={NEUTRAL_CHIP}>
                          {s}
                        </span>
                      ))}
                    </div>
                  )}

                  <Link
                    href={`/team/memory/episodes?episode=${encodeURIComponent(r.episode_id)}`}
                    className="text-sm text-emerald-700 font-medium hover:underline"
                  >
                    Open episode →
                  </Link>
                </div>
              );
            })}

            <details className="rounded-xl border border-slate-200/60 bg-slate-50/50 px-4 py-3 text-sm text-slate-500">
              <summary className="cursor-pointer font-medium text-slate-600">
                How similarity search works
              </summary>
              <ul className="list-disc list-inside mt-2 space-y-1 text-xs">
                <li>Describe symptoms, affected services, and error patterns</li>
                <li>More specific queries yield better matches</li>
                <li>Results ranked by semantic similarity to past episodes</li>
              </ul>
            </details>
          </>
        )}
      </div>
    </div>
  );
}
