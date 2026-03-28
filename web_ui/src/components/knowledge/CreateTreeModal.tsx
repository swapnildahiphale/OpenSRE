'use client';

import { useState } from 'react';
import { Loader2, X, Database } from 'lucide-react';

interface CreateTreeModalProps {
  onClose: () => void;
  onCreated: (treeName: string) => void;
}

export function CreateTreeModal({ onClose, onCreated }: CreateTreeModalProps) {
  const [treeName, setTreeName] = useState('');
  const [description, setDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValidName = /^[a-zA-Z0-9_-]+$/.test(treeName);

  const handleCreate = async () => {
    if (!treeName || !isValidName) return;

    setCreating(true);
    setError(null);

    try {
      const res = await fetch('/api/team/knowledge/tree/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tree_name: treeName, description }),
      });

      if (res.ok) {
        onCreated(treeName);
        onClose();
      } else {
        const data = await res.json();
        setError(data.error || data.detail || 'Failed to create tree');
      }
    } catch (e) {
      setError('Failed to create tree');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-stone-800 rounded-2xl w-full max-w-md p-6 shadow-xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-forest flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            <h2 className="text-lg font-semibold text-stone-900 dark:text-white">
              Create Knowledge Tree
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-stone-400 hover:text-stone-600 dark:hover:text-stone-300"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
              Tree Name
            </label>
            <input
              type="text"
              value={treeName}
              onChange={(e) => setTreeName(e.target.value)}
              placeholder="e.g., team-sre-runbooks"
              className={`w-full px-3 py-2 rounded-lg border bg-white dark:bg-stone-700 ${
                treeName && !isValidName
                  ? 'border-clay focus:ring-clay'
                  : 'border-stone-200 dark:border-stone-600 focus:ring-forest'
              } focus:outline-none focus:ring-2`}
            />
            {treeName && !isValidName && (
              <p className="text-xs text-clay mt-1">
                Only letters, numbers, hyphens, and underscores allowed
              </p>
            )}
            <p className="text-xs text-stone-500 mt-1">
              This will be the unique identifier for your tree
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="What kind of knowledge will this tree contain?"
              className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 focus:outline-none focus:ring-2 focus:ring-forest"
            />
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-clay-light/10 dark:bg-clay/20 border border-clay-light/40 dark:border-clay-dark text-clay-dark dark:text-clay-light text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-white"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!treeName || !isValidName || creating}
            className="px-4 py-2 bg-forest text-white rounded-lg hover:bg-forest-dark disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {creating && <Loader2 className="w-4 h-4 animate-spin" />}
            {creating ? 'Creating...' : 'Create Tree'}
          </button>
        </div>
      </div>
    </div>
  );
}
