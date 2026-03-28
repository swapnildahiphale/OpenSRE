'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Search, CheckCircle, XCircle } from 'lucide-react';

interface SearchResult {
  episode_id: string;
  alert_type: string;
  service_name: string;
  agents_used: string[];
  resolved: boolean;
  root_cause: string | null;
  effectiveness_score: number;
}

export default function MemorySearchPage() {
  const [query, setQuery] = useState('');
  const [serviceName, setServiceName] = useState('');
  const [alertType, setAlertType] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const resp = await fetch('/api/memory/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: query,
          service_name: serviceName,
          alert_type: alertType,
        }),
      });
      const data = await resp.json();
      setResults(data.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/team/memory" className="text-stone-400 hover:text-stone-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-2xl font-bold">Similarity Search</h1>
      </div>

      <div className="bg-white dark:bg-stone-700 rounded-lg border p-4 mb-6">
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Describe the incident (e.g., '503 errors on payments-service')"
              className="w-full border rounded-md p-2 text-sm bg-transparent"
              rows={3}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Service name</label>
              <input
                value={serviceName}
                onChange={e => setServiceName(e.target.value)}
                placeholder="e.g., payments-service"
                className="w-full border rounded-md p-2 text-sm bg-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Alert type</label>
              <input
                value={alertType}
                onChange={e => setAlertType(e.target.value)}
                placeholder="e.g., http_503"
                className="w-full border rounded-md p-2 text-sm bg-transparent"
              />
            </div>
          </div>
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-md text-sm hover:bg-purple-700 disabled:opacity-50"
          >
            <Search className="w-4 h-4" />
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </div>

      {searched && !loading && results.length === 0 && (
        <div className="text-center py-8 text-stone-500">
          No similar investigations found.
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-medium text-stone-500 text-sm">
            Found {results.length} similar investigation(s)
          </h2>
          {results.map(r => (
            <div
              key={r.episode_id}
              className="bg-white dark:bg-stone-700 rounded-lg border p-4"
            >
              <div className="flex items-center gap-2 mb-1">
                {r.resolved ? (
                  <CheckCircle className="w-4 h-4 text-green-500" />
                ) : (
                  <XCircle className="w-4 h-4 text-clay" />
                )}
                <span className="font-medium">{r.service_name}</span>
                <span className="text-stone-400">|</span>
                <span className="text-stone-500 text-sm">{r.alert_type}</span>
              </div>
              {r.root_cause && (
                <p className="text-sm text-stone-600 dark:text-stone-300 mt-1">
                  {r.root_cause}
                </p>
              )}
              <div className="text-xs text-stone-400 mt-2">
                Effectiveness: {(r.effectiveness_score * 100).toFixed(0)}%
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
