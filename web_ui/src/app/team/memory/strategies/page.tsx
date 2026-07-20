'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { TrendingUp, RefreshCcw, ChevronDown, Pencil, X, Trash2 } from 'lucide-react';
import MarkdownFallback from '@/components/MarkdownFallback';

interface Strategy {
  strategy_id: string;
  org_id: string;
  team_node_id: string | null;
  issue_type: string;
  component_key: string;
  strategy_text: string;
  episode_count: number | null;
  generated_at: string | null;
  updated_at?: string | null;
  manually_edited?: boolean | null;
}

const inputClass =
  'px-3 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-800';

const cardClass =
  'bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl shadow-sm';

export default function StrategiesPage() {
  const [allStrategies, setAllStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [issueType, setIssueType] = useState('');
  const [componentKey, setComponentKey] = useState('');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/memory/strategies')
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setAllStrategies(data.strategies || []);
      })
      .catch(() => {
        if (!cancelled) setAllStrategies([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const fetchStrategies = useCallback(() => {
    setRefreshing(true);
    fetch('/api/memory/strategies')
      .then((r) => r.json())
      .then((data) => setAllStrategies(data.strategies || []))
      .catch(() => setAllStrategies([]))
      .finally(() => setRefreshing(false));
  }, []);

  const filteredStrategies = useMemo(() => {
    return allStrategies.filter((s) => {
      if (issueType && !(s.issue_type || '').toLowerCase().includes(issueType.toLowerCase())) {
        return false;
      }
      if (componentKey && !(s.component_key || '').toLowerCase().includes(componentKey.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [allStrategies, issueType, componentKey]);

  const groupedStrategies = useMemo(() => {
    const groups = new Map<string, Strategy[]>();
    for (const s of filteredStrategies) {
      const key = s.issue_type || 'General';
      const list = groups.get(key) ?? [];
      list.push(s);
      groups.set(key, list);
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [filteredStrategies]);

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleDelete = async (e: React.MouseEvent, strategy: Strategy) => {
    e.stopPropagation();
    const label = strategy.component_key || strategy.issue_type || 'this strategy';
    if (!window.confirm(`Delete strategy for ${label}? This cannot be undone.`)) {
      return;
    }

    setDeletingId(strategy.strategy_id);

    try {
      const res = await fetch(
        `/api/memory/strategies/${encodeURIComponent(strategy.strategy_id)}`,
        { method: 'DELETE' },
      );
      const data = await res.json();

      if (!res.ok || !data.success) {
        window.alert(data.error ?? 'Failed to delete strategy.');
        return;
      }

      setAllStrategies((prev) => prev.filter((s) => s.strategy_id !== strategy.strategy_id));
      setExpandedIds((prev) => {
        const next = new Set(prev);
        next.delete(strategy.strategy_id);
        return next;
      });
      if (editingId === strategy.strategy_id) {
        cancelEditing();
      }
    } catch {
      window.alert('Failed to delete strategy.');
    } finally {
      setDeletingId(null);
    }
  };

  const startEditing = (e: React.MouseEvent, strategy: Strategy) => {
    e.stopPropagation();
    setEditingId(strategy.strategy_id);
    setEditDraft(strategy.strategy_text);
    setSaveError(null);
    setExpandedIds((prev) => new Set(prev).add(strategy.strategy_id));
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditDraft('');
    setSaveError(null);
  };

  const saveStrategy = async (strategyId: string) => {
    const trimmed = editDraft.trim();
    if (!trimmed) {
      setSaveError('Strategy text cannot be empty.');
      return;
    }

    setSavingId(strategyId);
    setSaveError(null);

    try {
      const res = await fetch(`/api/memory/strategies/${encodeURIComponent(strategyId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy_text: trimmed }),
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        setSaveError(data.error ?? 'Failed to save strategy.');
        return;
      }

      setAllStrategies((prev) =>
        prev.map((s) =>
          s.strategy_id === strategyId
            ? {
                ...s,
                strategy_text: trimmed,
                updated_at: data.updated_at ?? s.updated_at,
                manually_edited: true,
              }
            : s,
        ),
      );
      setEditingId(null);
      setEditDraft('');
    } catch {
      setSaveError('Failed to save strategy.');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={fetchStrategies}
          disabled={refreshing}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-stone-600 dark:text-stone-300 border border-stone-200 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 disabled:opacity-50"
          aria-label="Refresh strategies"
        >
          <RefreshCcw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className={`animate-pulse ${cardClass} p-4`}>
              <div className="flex gap-3 mb-3">
                <div className="h-5 w-32 bg-stone-200 dark:bg-stone-700 rounded" />
                <div className="h-5 w-16 bg-stone-200 dark:bg-stone-700 rounded-full" />
              </div>
              <div className="h-4 w-full bg-stone-200 dark:bg-stone-700 rounded mb-2" />
              <div className="h-4 w-2/3 bg-stone-200 dark:bg-stone-700 rounded" />
            </div>
          ))}
        </div>
      ) : allStrategies.length === 0 ? (
        <div className={`${cardClass} p-12 text-center`}>
          <TrendingUp className="w-12 h-12 mx-auto text-stone-300 dark:text-stone-600 mb-4" />
          <p className="text-stone-500 dark:text-stone-400 mb-2">No strategies yet</p>
          <p className="text-sm text-stone-400 dark:text-stone-500 max-w-md mx-auto">
            Strategies are auto-generated after multiple similar investigations. Run more
            episodes with the same issue type and component to unlock playbooks.
          </p>
        </div>
      ) : (
        <>
          <div className={`${cardClass} p-4 space-y-3`}>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1 min-w-[160px]">
                <label
                  htmlFor="issue-type-filter"
                  className="block text-xs font-medium text-stone-500 mb-1"
                >
                  Issue type
                </label>
                <input
                  id="issue-type-filter"
                  type="text"
                  value={issueType}
                  onChange={(e) => setIssueType(e.target.value)}
                  placeholder="e.g., high_latency"
                  className={`w-full ${inputClass}`}
                />
              </div>
              <div className="flex-1 min-w-[160px]">
                <label
                  htmlFor="component-filter"
                  className="block text-xs font-medium text-stone-500 mb-1"
                >
                  Component
                </label>
                <input
                  id="component-filter"
                  type="text"
                  value={componentKey}
                  onChange={(e) => setComponentKey(e.target.value)}
                  placeholder="e.g., service:cart-service"
                  className={`w-full ${inputClass}`}
                />
              </div>
            </div>
            <p className="text-xs text-stone-400">
              {filteredStrategies.length} of {allStrategies.length} shown
            </p>
          </div>

          {filteredStrategies.length === 0 ? (
            <div className={`${cardClass} p-8 text-center text-stone-500`}>
              No strategies match your filters.
            </div>
          ) : (
            <div className="space-y-6">
              {groupedStrategies.map(([groupIssueType, strategies]) => (
                <section key={groupIssueType}>
                  <h2 className="text-sm font-semibold text-stone-700 dark:text-stone-300 mb-3">
                    {groupIssueType} ({strategies.length})
                  </h2>
                  <div className="space-y-3">
                    {strategies.map((strategy) => {
                      const expanded = expandedIds.has(strategy.strategy_id);
                      const editing = editingId === strategy.strategy_id;
                      const saving = savingId === strategy.strategy_id;
                      const deleting = deletingId === strategy.strategy_id;

                      return (
                        <div key={strategy.strategy_id} className={cardClass}>
                          <div className="flex items-center gap-2 p-4">
                            <button
                              type="button"
                              onClick={() => toggleExpanded(strategy.strategy_id)}
                              className="flex flex-1 items-center gap-3 min-w-0 text-left rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800/50 transition-colors -m-1 p-1"
                            >
                              <div className="w-8 h-8 rounded-lg bg-clay-light/15 dark:bg-clay/20 flex items-center justify-center flex-shrink-0">
                                <TrendingUp className="w-4 h-4 text-clay dark:text-clay-light" />
                              </div>

                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  {strategy.component_key ? (
                                    <span className="font-medium text-stone-900 dark:text-white font-mono text-sm">
                                      {strategy.component_key}
                                    </span>
                                  ) : null}
                                  {strategy.component_key && strategy.issue_type ? (
                                    <span className="text-stone-400">/</span>
                                  ) : null}
                                  <span className="text-sm text-stone-600 dark:text-stone-300">
                                    {strategy.issue_type || 'General'}
                                  </span>
                                </div>
                              </div>

                              {strategy.episode_count != null && (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 dark:bg-stone-700 text-stone-500 flex-shrink-0">
                                  {strategy.episode_count} episode
                                  {strategy.episode_count === 1 ? '' : 's'}
                                </span>
                              )}

                              <ChevronDown
                                className={`w-5 h-5 text-stone-400 flex-shrink-0 transition-transform ${
                                  expanded ? 'rotate-180' : ''
                                }`}
                              />
                            </button>

                            <button
                              type="button"
                              onClick={(e) => startEditing(e, strategy)}
                              className="p-1.5 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-700 flex-shrink-0"
                              aria-label="Edit strategy"
                            >
                              <Pencil className="w-4 h-4" />
                            </button>

                            <button
                              type="button"
                              onClick={(e) => handleDelete(e, strategy)}
                              disabled={deleting}
                              className="p-1.5 text-stone-400 hover:text-red-600 dark:hover:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/30 flex-shrink-0 disabled:opacity-50"
                              aria-label="Delete strategy"
                            >
                              <Trash2 className={`w-4 h-4 ${deleting ? 'animate-pulse' : ''}`} />
                            </button>
                          </div>

                          {expanded && (
                            <div className="px-4 pb-4 border-t border-stone-100 dark:border-stone-700">
                              {editing ? (
                                <div className="pt-4 space-y-3">
                                  <label
                                    htmlFor={`strategy-edit-${strategy.strategy_id}`}
                                    className="block text-xs font-medium text-stone-500"
                                  >
                                    Edit playbook (Markdown)
                                  </label>
                                  <textarea
                                    id={`strategy-edit-${strategy.strategy_id}`}
                                    value={editDraft}
                                    onChange={(e) => setEditDraft(e.target.value)}
                                    rows={14}
                                    className={`w-full ${inputClass} font-mono text-sm leading-relaxed`}
                                  />
                                  {saveError ? (
                                    <p className="text-sm text-red-600 dark:text-red-400">{saveError}</p>
                                  ) : null}
                                  <div className="flex items-center gap-2">
                                    <button
                                      type="button"
                                      onClick={() => saveStrategy(strategy.strategy_id)}
                                      disabled={saving}
                                      className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-forest hover:bg-forest-dark rounded-lg disabled:opacity-50"
                                    >
                                      {saving ? 'Saving…' : 'Save'}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={cancelEditing}
                                      disabled={saving}
                                      className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-stone-600 dark:text-stone-300 border border-stone-200 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 disabled:opacity-50"
                                    >
                                      <X className="w-4 h-4" />
                                      Cancel
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                <>
                                  <div className="pt-4">
                                    <MarkdownFallback content={strategy.strategy_text} bare />
                                  </div>
                                  <div className="mt-4 pt-3 border-t border-stone-100 dark:border-stone-700 text-xs text-stone-400 space-y-1">
                                    {strategy.generated_at ? (
                                      <p>Generated {new Date(strategy.generated_at).toLocaleString()}</p>
                                    ) : null}
                                    {strategy.updated_at ? (
                                      <p>Last edited {new Date(strategy.updated_at).toLocaleString()}</p>
                                    ) : null}
                                  </div>
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
