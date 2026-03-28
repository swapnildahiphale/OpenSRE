'use client';

import { Plus, Loader2 } from 'lucide-react';
import { TreeCard } from './TreeCard';

export interface EffectiveTree {
  tree_name: string;
  level: string; // "org" | "group" | "team"
  node_name: string;
  node_id: string;
  inherited: boolean;
}

export interface TreeStats {
  tree: string;
  total_nodes: number;
  layers: number;
}

interface TreeSelectorProps {
  trees: EffectiveTree[];
  treeStats: Record<string, TreeStats>;
  selectedTree: string | null;
  onSelectTree: (treeName: string) => void;
  loading?: boolean;
  onCreateTree?: () => void;
}

export function TreeSelector({
  trees,
  treeStats,
  selectedTree,
  onSelectTree,
  loading,
  onCreateTree,
}: TreeSelectorProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-stone-400" />
        <span className="ml-2 text-stone-500">Loading trees...</span>
      </div>
    );
  }

  if (trees.length === 0) {
    return (
      <div className="bg-stone-50 dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-8 text-center">
        <p className="text-stone-500">No knowledge trees configured.</p>
        <p className="text-sm text-stone-400 mt-1">
          Ask your org admin to set up a knowledge tree for your team.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-medium text-stone-700 dark:text-stone-300">
            Your Knowledge Trees
          </h2>
          <p className="text-xs text-stone-500 mt-0.5">
            {trees.length} tree{trees.length !== 1 ? 's' : ''} available
            {trees.some((t) => t.inherited) && ' (including inherited)'}
          </p>
        </div>
        {onCreateTree && (
          <button
            onClick={onCreateTree}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Tree
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {trees.map((tree) => {
          const stats = treeStats[tree.tree_name];
          return (
            <TreeCard
              key={`${tree.node_id}-${tree.tree_name}`}
              treeName={tree.tree_name}
              level={tree.level}
              nodeName={tree.node_name}
              nodeId={tree.node_id}
              inherited={tree.inherited}
              isSelected={selectedTree === tree.tree_name}
              stats={
                stats
                  ? { nodes: stats.total_nodes, layers: stats.layers }
                  : undefined
              }
              onSelect={() => onSelectTree(tree.tree_name)}
            />
          );
        })}
      </div>
    </div>
  );
}
