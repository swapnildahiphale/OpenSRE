'use client';

import Link from 'next/link';
import { Brain, List, Search, TrendingUp } from 'lucide-react';
import { useState, useEffect } from 'react';

interface MemoryStats {
  total_episodes: number;
  resolved_episodes: number;
  unresolved_episodes: number;
  strategies_count: number;
}

export default function MemoryPage() {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/memory/stats')
      .then(r => r.json())
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, []);

  const cards = [
    {
      title: 'Episodes',
      description: 'Browse past investigation episodes',
      icon: List,
      href: '/team/memory/episodes',
      stat: stats?.total_episodes ?? 0,
      statLabel: 'stored',
    },
    {
      title: 'Similarity Search',
      description: 'Find similar past investigations',
      icon: Search,
      href: '/team/memory/search',
      stat: stats?.resolved_episodes ?? 0,
      statLabel: 'resolved',
    },
    {
      title: 'Strategies',
      description: 'View auto-generated investigation strategies',
      icon: TrendingUp,
      href: '/team/memory/strategies',
      stat: stats?.strategies_count ?? 0,
      statLabel: 'generated',
    },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Brain className="w-8 h-8 text-purple-500" />
        <div>
          <h1 className="text-2xl font-bold">Episodic Memory</h1>
          <p className="text-stone-500">
            Learn from past investigations to improve future ones
          </p>
        </div>
      </div>

      {loading ? (
        <div className="text-stone-500">Loading memory stats...</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white dark:bg-stone-700 rounded-lg border p-4">
              <div className="text-3xl font-bold">{stats?.total_episodes ?? 0}</div>
              <div className="text-stone-500 text-sm">Total Episodes</div>
            </div>
            <div className="bg-white dark:bg-stone-700 rounded-lg border p-4">
              <div className="text-3xl font-bold text-green-600">{stats?.resolved_episodes ?? 0}</div>
              <div className="text-stone-500 text-sm">Resolved</div>
            </div>
            <div className="bg-white dark:bg-stone-700 rounded-lg border p-4">
              <div className="text-3xl font-bold text-orange-500">{stats?.unresolved_episodes ?? 0}</div>
              <div className="text-stone-500 text-sm">Unresolved</div>
            </div>
            <div className="bg-white dark:bg-stone-700 rounded-lg border p-4">
              <div className="text-3xl font-bold text-purple-600">{stats?.strategies_count ?? 0}</div>
              <div className="text-stone-500 text-sm">Strategies</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {cards.map(card => (
              <Link
                key={card.title}
                href={card.href}
                className="bg-white dark:bg-stone-700 rounded-lg border p-6 hover:border-purple-500 transition-colors"
              >
                <div className="flex items-center gap-3 mb-3">
                  <card.icon className="w-5 h-5 text-purple-500" />
                  <h2 className="font-semibold">{card.title}</h2>
                </div>
                <p className="text-stone-500 text-sm mb-4">{card.description}</p>
                <div className="text-sm">
                  <span className="font-medium">{card.stat}</span>{' '}
                  <span className="text-stone-400">{card.statLabel}</span>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
