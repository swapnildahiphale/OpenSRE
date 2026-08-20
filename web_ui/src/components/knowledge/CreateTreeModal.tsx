'use client';

import { useState } from 'react';
import { Loader2, X } from 'lucide-react';

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
      <div className="bg-white dark:bg-slate-800 rounded-[1.5rem] w-full max-w-md p-6 shadow-xl border border-slate-200/70">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            Create Knowledge Tree
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Tree Name
            </label>
            <input
              type="text"
              value={treeName}
              onChange={(e) => setTreeName(e.target.value)}
              placeholder="e.g., team-sre-runbooks"
              className={`w-full px-3 py-2 rounded-lg border bg-white dark:bg-slate-700 ${
                treeName && !isValidName
                  ? 'border-rose-300 focus:ring-rose-500'
                  : 'border-slate-200 dark:border-slate-600 focus:ring-emerald-500'
              } focus:outline-none focus:ring-2`}
            />
            {treeName && !isValidName && (
              <p className="text-xs text-rose-600 mt-1">
                Only letters, numbers, hyphens, and underscores allowed
              </p>
            )}
            <p className="text-xs text-slate-500 mt-1">
              This will be the unique identifier for your tree
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="What kind of knowledge will this tree contain?"
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-900/20 border border-rose-200/40 dark:border-rose-700 text-rose-700 dark:text-rose-400 text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!treeName || !isValidName || creating}
            className="px-4 py-2 bg-emerald-100/50 text-emerald-700 rounded-lg hover:bg-emerald-100/80 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {creating && <Loader2 className="w-4 h-4 animate-spin" />}
            {creating ? 'Creating...' : 'Create Tree'}
          </button>
        </div>
      </div>
    </div>
  );
}
