'use client';

import { Database, GitBranch, Layers } from 'lucide-react';

export interface TreeCardProps {
  treeName: string;
  level: string; // "org" | "group" | "team"
  nodeName: string;
  nodeId: string;
  inherited: boolean;
  isSelected: boolean;
  stats?: { nodes: number; layers: number };
  onSelect: () => void;
}

export function TreeCard({
  treeName,
  level,
  nodeName,
  inherited,
  isSelected,
  stats,
  onSelect,
}: TreeCardProps) {
  const levelColors: Record<string, string> = {
    org: 'bg-emerald-100/55 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400',
    group: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400',
    team: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  };

  return (
    <button
      onClick={onSelect}
      className={`
        w-full text-left p-4 rounded-[1.5rem] border transition-all
        ${
          isSelected
            ? 'border-emerald-500 bg-emerald-100/50 dark:bg-emerald-900/20 ring-2 ring-emerald-500/20'
            : 'border-slate-200/70 dark:border-slate-600 bg-white dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600'
        }
      `}
    >
      <div className="flex items-start gap-3">
        <div
          className={`
            w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0
            ${isSelected ? 'bg-emerald-100/55 text-emerald-700' : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400'}
          `}
        >
          <Database className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            {inherited && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-500">
                Inherited
              </span>
            )}
            <span className={`text-xs px-1.5 py-0.5 rounded capitalize ${levelColors[level] || levelColors.team}`}>
              {level}
            </span>
          </div>
          <h3 className="font-medium text-slate-900 dark:text-white truncate">{treeName}</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
            From {nodeName}
          </p>
          {stats && (
            <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
              <span className="flex items-center gap-1">
                <GitBranch className="w-3 h-3" />
                {stats.nodes.toLocaleString()} nodes
              </span>
              <span className="flex items-center gap-1">
                <Layers className="w-3 h-3" />
                {stats.layers} layers
              </span>
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
