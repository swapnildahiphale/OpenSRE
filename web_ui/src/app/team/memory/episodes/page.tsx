'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { ArrowLeft, CheckCircle, XCircle, Clock, ExternalLink } from 'lucide-react';

interface Episode {
  id: string;
  agent_run_id: string | null;
  alert_type: string | null;
  alert_description: string | null;
  severity: string | null;
  services: string[];
  agents_used: string[];
  skills_used: string[];
  key_findings: { skill: string; query: string; finding: string }[];
  resolved: boolean;
  root_cause: string | null;
  summary: string | null;
  effectiveness_score: number | null;
  confidence: number | null;
  duration_seconds: number | null;
  created_at: string | null;
}

const severityColors: Record<string, string> = {
  critical: 'bg-clay-light/15 text-clay-dark dark:bg-clay/20 dark:text-clay-light',
  warning: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  info: 'bg-forest-light/15 text-forest-dark dark:bg-forest/30 dark:text-forest-light',
};

export default function EpisodesPage() {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/memory/episodes')
      .then(r => r.json())
      .then(data => setEpisodes(data.episodes || []))
      .catch(() => setEpisodes([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/team/memory" className="text-stone-400 hover:text-stone-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-2xl font-bold">Investigation Episodes</h1>
      </div>

      {loading ? (
        <div className="text-stone-500">Loading episodes...</div>
      ) : episodes.length === 0 ? (
        <div className="text-center py-12 text-stone-500">
          <p className="text-lg mb-2">No episodes stored yet</p>
          <p className="text-sm">Episodes are created automatically after investigations.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {episodes.map(ep => (
            <div
              key={ep.id}
              className="bg-white dark:bg-stone-700 rounded-lg border p-4"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    {ep.resolved ? (
                      <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-clay flex-shrink-0" />
                    )}
                    {ep.severity && (
                      <span className={`text-xs px-2 py-0.5 rounded-full ${severityColors[ep.severity] || 'bg-stone-100 text-stone-700'}`}>
                        {ep.severity}
                      </span>
                    )}
                    <span className="text-stone-500 text-sm">{ep.alert_type || 'unknown'}</span>
                    {ep.agent_run_id && (
                      <Link
                        href={`/team/runs/${ep.agent_run_id}`}
                        className="text-purple-500 hover:text-purple-700"
                        title="View agent run"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </Link>
                    )}
                  </div>

                  {ep.services.length > 0 && (
                    <div className="flex gap-1.5 mb-2 flex-wrap">
                      {ep.services.map(s => (
                        <span key={s} className="text-xs bg-stone-100 dark:bg-stone-700 px-2 py-0.5 rounded">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}

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

                  {ep.skills_used.length > 0 && (
                    <div className="flex gap-1.5 mb-2 flex-wrap">
                      {ep.skills_used.map(s => (
                        <span key={s} className="text-xs bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 px-2 py-0.5 rounded">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center gap-3 mt-2 text-xs text-stone-400">
                    {ep.duration_seconds != null && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {ep.duration_seconds < 60
                          ? `${ep.duration_seconds.toFixed(0)}s`
                          : `${(ep.duration_seconds / 60).toFixed(1)}m`}
                      </span>
                    )}
                    {ep.effectiveness_score != null && (
                      <span>Effectiveness: {(ep.effectiveness_score * 100).toFixed(0)}%</span>
                    )}
                    {ep.created_at && (
                      <span>{new Date(ep.created_at).toLocaleString()}</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
