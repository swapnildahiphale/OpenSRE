'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { ArrowLeft, TrendingUp, RefreshCw } from 'lucide-react';

interface Strategy {
  id: string;
  org_id: string;
  team_node_id: string | null;
  alert_type: string | null;
  service_name: string | null;
  strategy_text: string;
  source_episode_ids: string[];
  episode_count: number | null;
  generated_at: string | null;
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [alertType, setAlertType] = useState('');
  const [serviceName, setServiceName] = useState('');

  const fetchStrategies = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (alertType) params.set('alert_type', alertType);
    if (serviceName) params.set('service_name', serviceName);
    fetch(`/api/memory/strategies?${params}`)
      .then(r => r.json())
      .then(data => setStrategies(data.strategies || []))
      .catch(() => setStrategies([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchStrategies();
  }, []);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/team/memory" className="text-stone-400 hover:text-stone-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-2xl font-bold">Investigation Strategies</h1>
      </div>

      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <label className="text-sm font-medium">Alert Type:</label>
        <input
          value={alertType}
          onChange={e => setAlertType(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && fetchStrategies()}
          className="border rounded-md px-3 py-1.5 text-sm bg-transparent"
          placeholder="e.g., high_latency"
        />
        <label className="text-sm font-medium">Service:</label>
        <input
          value={serviceName}
          onChange={e => setServiceName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && fetchStrategies()}
          className="border rounded-md px-3 py-1.5 text-sm bg-transparent"
          placeholder="e.g., cart-service"
        />
        <button
          onClick={fetchStrategies}
          className="bg-purple-600 text-white px-3 py-1.5 rounded-md text-sm hover:bg-purple-700 flex items-center gap-1"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Load
        </button>
      </div>

      {loading ? (
        <div className="text-stone-500">Loading strategies...</div>
      ) : strategies.length === 0 ? (
        <div className="text-center py-12 text-stone-500">
          <p className="text-lg mb-2">No strategies found</p>
          <p className="text-sm">Strategies are auto-generated after multiple similar investigations.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {strategies.map(s => (
            <div
              key={s.id}
              className="bg-white dark:bg-stone-700 rounded-lg border p-5"
            >
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-purple-500" />
                <span className="font-medium">
                  {s.alert_type || 'General'}
                </span>
                {s.service_name && s.service_name !== '*' && (
                  <>
                    <span className="text-stone-400">/</span>
                    <span className="text-stone-500">{s.service_name}</span>
                  </>
                )}
              </div>

              <div className="prose prose-sm dark:prose-invert max-w-none mb-3 text-stone-700 dark:text-stone-300 whitespace-pre-wrap">
                {s.strategy_text}
              </div>

              <div className="flex items-center gap-4 text-xs text-stone-400 border-t pt-2 mt-2">
                {s.episode_count != null && (
                  <span>Based on {s.episode_count} episode(s)</span>
                )}
                {s.generated_at && (
                  <span>Generated: {new Date(s.generated_at).toLocaleString()}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
