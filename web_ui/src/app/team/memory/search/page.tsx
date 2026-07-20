'use client';

import { useState, useMemo, useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Search } from 'lucide-react';

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

const cardClass =
  'bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl shadow-sm p-4';

const inputClass =
  'w-full border border-stone-200 dark:border-stone-600 rounded-lg p-2.5 text-sm bg-white dark:bg-stone-800';

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
        hits = hits.filter((h) =>
          (h.issue_type || '').toLowerCase().includes(needle),
        );
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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: search form */}
        <div className={cardClass}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1.5">
                Incident description
              </label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe the incident symptoms, affected services, and error patterns..."
                className={`${inputClass} resize-none`}
                rows={4}
              />
            </div>

            <div>
              <p className="text-xs text-stone-500 mb-2">Try an example:</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_QUERIES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => setQuery(example)}
                    className="text-xs px-2.5 py-1 rounded-full border border-stone-200 dark:border-stone-600 text-stone-600 dark:text-stone-300 hover:border-clay hover:text-clay transition-colors"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1.5">
                Issue type filter{' '}
                <span className="font-normal text-stone-400">(optional)</span>
              </label>
              <input
                value={issueTypeFilter}
                onChange={(e) => setIssueTypeFilter(e.target.value)}
                placeholder="e.g., http_error"
                className={inputClass}
              />
            </div>

            <button
              type="button"
              onClick={() => handleSearch()}
              disabled={loading || !query.trim()}
              className="w-full flex items-center justify-center gap-2 bg-forest hover:bg-forest-dark text-white px-4 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 transition-colors active:scale-[0.98]"
            >
              <Search className="w-4 h-4" />
              {loading ? 'Searching...' : 'Search memory'}
            </button>

            <p className="text-xs text-stone-400 text-center">
              Press Enter to search
            </p>
          </div>
        </div>

        {/* Right: results area */}
        <div className="space-y-3">
          {!searched && !loading && (
            <div className={`${cardClass} text-sm text-stone-500 space-y-3`}>
              <p className="font-medium text-stone-700 dark:text-stone-300">
                How similarity search works
              </p>
              <ul className="list-disc list-inside space-y-1.5 text-stone-500">
                <li>Describe symptoms, affected services, and error patterns</li>
                <li>More specific queries yield better matches</li>
                <li>Results are ranked by semantic similarity to past episodes</li>
                <li>Use the issue type filter to narrow results after searching</li>
              </ul>
              <p className="text-stone-400">
                Click an example chip or type your own description, then search.
              </p>
            </div>
          )}

          {loading && (
            <>
              {[1, 2].map((i) => (
                <div
                  key={i}
                  className={`${cardClass} animate-pulse space-y-3`}
                >
                  <div className="h-8 w-20 bg-stone-200 dark:bg-stone-700 rounded" />
                  <div className="h-1 w-full bg-stone-200 dark:bg-stone-700 rounded" />
                  <div className="flex gap-2">
                    <div className="h-5 w-16 bg-stone-200 dark:bg-stone-700 rounded-full" />
                    <div className="h-5 w-24 bg-stone-200 dark:bg-stone-700 rounded-full" />
                  </div>
                  <div className="h-4 w-full bg-stone-200 dark:bg-stone-700 rounded" />
                  <div className="h-4 w-3/4 bg-stone-200 dark:bg-stone-700 rounded" />
                </div>
              ))}
            </>
          )}

          {searched && !loading && sortedResults.length === 0 && (
            <div className={`${cardClass} text-center py-8 space-y-3`}>
              <p className="text-stone-700 dark:text-stone-300 font-medium">
                No similar investigations found
              </p>
              <p className="text-sm text-stone-500">
                Try broadening your description or removing the issue type filter.
              </p>
              <ul className="text-sm text-stone-400 space-y-1">
                <li>Include service names and error codes when possible</li>
                <li>Check that past investigations have been stored as episodes</li>
              </ul>
            </div>
          )}

          {searched && !loading && sortedResults.length > 0 && (
            <>
              <p className="text-sm text-stone-500">
                {sortedResults.length} similar investigation
                {sortedResults.length !== 1 ? 's' : ''} found
              </p>
              {sortedResults.map((r) => {
                const matchPct = Math.round(r.score * 100);
                return (
                  <div key={r.episode_id} className={cardClass}>
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <span className="text-2xl font-semibold text-forest">
                        {matchPct}%
                      </span>
                      <span className="text-xs text-stone-400">match</span>
                    </div>

                    <div className="h-1 bg-stone-100 dark:bg-stone-700 rounded-full mb-3 overflow-hidden">
                      <div
                        className="h-full bg-forest rounded-full"
                        style={{ width: `${matchPct}%` }}
                      />
                    </div>

                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          r.resolved
                            ? 'bg-forest-light/15 text-forest-dark dark:bg-forest/30 dark:text-forest-light'
                            : 'bg-clay-light/15 text-clay-dark dark:bg-clay/20 dark:text-clay-light'
                        }`}
                      >
                        {r.resolved ? 'resolved' : 'unresolved'}
                      </span>
                      <span className="text-sm font-medium text-stone-900 dark:text-white">
                        {r.issue_type || 'unknown'}
                      </span>
                    </div>

                    {r.issue_description && (
                      <p className="text-sm text-stone-600 dark:text-stone-300 mb-2">
                        {r.issue_description}
                      </p>
                    )}

                    {r.services?.length > 0 && (
                      <div className="flex gap-1.5 flex-wrap mb-2">
                        {r.services.map((s) => (
                          <span
                            key={s}
                            className="text-xs bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 px-2 py-0.5 rounded"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    )}

                    {r.skills_used?.length > 0 && (
                      <div className="flex gap-1.5 flex-wrap mb-3">
                        {r.skills_used.map((s) => (
                          <span
                            key={s}
                            className="text-xs bg-forest-light/15 text-forest-dark dark:bg-forest/30 dark:text-forest-light px-2 py-0.5 rounded"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    )}

                    <Link
                      href={`/team/memory/episodes?episode=${encodeURIComponent(r.episode_id)}`}
                      className="text-sm text-forest hover:text-forest-dark font-medium"
                    >
                      Open episode
                    </Link>
                  </div>
                );
              })}
            </>
          )}
        </div>
    </div>
  );
}
