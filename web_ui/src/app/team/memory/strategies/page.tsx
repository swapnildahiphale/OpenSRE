'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { ChevronDown, Pencil, RotateCw, Trash2, X } from 'lucide-react';
import { clsx } from 'clsx';
import MarkdownFallback from '@/components/MarkdownFallback';
import { Button, Chip, EmptyState, Skeleton, listRowHoverClass } from '@/components/ui-flow';

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
  'w-full h-9 px-3 text-sm rounded-xl border border-slate-200/70 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-300';

const textareaClass =
  'w-full px-3 py-2 text-sm rounded-xl border border-slate-200/70 bg-white text-slate-900 font-mono leading-relaxed focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-300';

const NEUTRAL_CHIP =
  'inline-flex items-center h-6 px-2.5 rounded-full text-[11px] font-medium bg-slate-50 text-slate-600 border border-slate-200/80';

function FilterSectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500 mb-3">{children}</div>
  );
}

export default function StrategiesPage() {
  const [allStrategies, setAllStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [issueType, setIssueType] = useState('all');
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

  const patternFreqs = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of allStrategies) {
      const key = s.issue_type || 'General';
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => b.count - a.count);
  }, [allStrategies]);

  const filteredStrategies = useMemo(() => {
    return allStrategies.filter((s) => {
      if (issueType !== 'all' && (s.issue_type || 'General') !== issueType) {
        return false;
      }
      if (
        componentKey &&
        !(s.component_key || '').toLowerCase().includes(componentKey.toLowerCase())
      ) {
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

  const hasActiveFilters = issueType !== 'all' || componentKey.trim().length > 0;

  const clearAllFilters = () => {
    setIssueType('all');
    setComponentKey('');
  };

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
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

  if (loading) {
    return (
      <div className="grid grid-cols-12 gap-10">
        <Skeleton className="col-span-12 lg:col-span-3 h-48 rounded-xl" />
        <div className="col-span-12 lg:col-span-9 space-y-4">
          <Skeleton className="h-32 w-full rounded-[1.5rem]" />
          <Skeleton className="h-32 w-full rounded-[1.5rem]" />
        </div>
      </div>
    );
  }

  if (allStrategies.length === 0) {
    return (
      <EmptyState
        title="No strategies yet"
        description="Strategies are auto-generated after multiple similar investigations. Run more episodes with the same issue type and component to unlock playbooks."
      />
    );
  }

  return (
    <div className="grid grid-cols-12 gap-10">
      <aside className="col-span-12 lg:col-span-3">
        <div className="sticky top-[80px] space-y-8">
          <div>
            <FilterSectionLabel>Patterns</FilterSectionLabel>
            <div className="flex flex-wrap gap-1.5">
              <Chip
                active={issueType === 'all'}
                onClick={() => setIssueType('all')}
                className="h-auto px-2.5 py-1 normal-case"
              >
                all
              </Chip>
              {patternFreqs.map(({ value, count }) => (
                <Chip
                  key={value}
                  active={issueType === value}
                  onClick={() => setIssueType(value)}
                  title={value}
                  className="h-auto max-w-full px-2.5 py-1 font-mono normal-case text-left whitespace-normal break-words"
                >
                  {value} ·{count}
                </Chip>
              ))}
            </div>
          </div>

          <div>
            <FilterSectionLabel>Component</FilterSectionLabel>
            <input
              type="text"
              value={componentKey}
              onChange={(e) => setComponentKey(e.target.value)}
              placeholder="e.g., service:checkout"
              className={inputClass}
            />
          </div>

          {hasActiveFilters && (
            <div>
              <button
                type="button"
                onClick={clearAllFilters}
                className="text-[12px] text-slate-500 hover:text-slate-800 transition-colors"
              >
                clear all
              </button>
            </div>
          )}
        </div>
      </aside>

      <div className="col-span-12 lg:col-span-9 space-y-6">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-slate-400">
            {filteredStrategies.length} of {allStrategies.length} shown
          </p>
          <button
            type="button"
            onClick={fetchStrategies}
            disabled={refreshing}
            className="p-2 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition disabled:opacity-50"
            aria-label="Refresh strategies"
            title="Refresh"
          >
            <RotateCw className={clsx('w-[18px] h-[18px]', refreshing && 'animate-spin')} />
          </button>
        </div>

        {filteredStrategies.length === 0 ? (
          <EmptyState
            title="No strategies match your filters"
            action={
              hasActiveFilters ? (
                <Button variant="secondary" onClick={clearAllFilters}>
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="space-y-6">
            {groupedStrategies.map(([groupIssueType, strategies]) => (
              <section key={groupIssueType}>
                <h2 className="text-sm font-semibold text-slate-700 mb-3 font-mono">
                  {groupIssueType}{' '}
                  <span className="font-sans font-normal text-slate-400">({strategies.length})</span>
                </h2>
                <div className="space-y-3">
                  {strategies.map((strategy) => {
                    const expanded = expandedIds.has(strategy.strategy_id);
                    const editing = editingId === strategy.strategy_id;
                    const saving = savingId === strategy.strategy_id;
                    const deleting = deletingId === strategy.strategy_id;

                    return (
                      <div
                        key={strategy.strategy_id}
                        className={`rounded-[1.5rem] bg-white border border-slate-200/70 shadow-[0_12px_30px_-12px_rgba(15,23,42,0.06)] overflow-hidden ${listRowHoverClass}`}
                      >
                        <div className="flex items-center gap-2 p-4">
                          <button
                            type="button"
                            onClick={() => toggleExpanded(strategy.strategy_id)}
                            className="flex flex-1 items-center gap-3 min-w-0 text-left"
                          >
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                {strategy.component_key ? (
                                  <span className="font-mono text-sm font-medium text-slate-900">
                                    {strategy.component_key}
                                  </span>
                                ) : null}
                                {strategy.component_key && strategy.issue_type ? (
                                  <span className="text-slate-400">/</span>
                                ) : null}
                                <span className="text-sm text-slate-600">
                                  {strategy.issue_type || 'General'}
                                </span>
                              </div>
                            </div>

                            {strategy.episode_count != null && (
                              <span className={NEUTRAL_CHIP}>
                                {strategy.episode_count} episode
                                {strategy.episode_count === 1 ? '' : 's'}
                              </span>
                            )}

                            <ChevronDown
                              className={clsx(
                                'w-5 h-5 text-slate-400 shrink-0 transition-transform',
                                expanded && 'rotate-180',
                              )}
                            />
                          </button>

                          <button
                            type="button"
                            onClick={(e) => startEditing(e, strategy)}
                            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 shrink-0"
                            aria-label="Edit strategy"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>

                          <button
                            type="button"
                            onClick={(e) => handleDelete(e, strategy)}
                            disabled={deleting}
                            className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 shrink-0 disabled:opacity-50"
                            aria-label="Delete strategy"
                          >
                            <Trash2 className={clsx('w-4 h-4', deleting && 'animate-pulse')} />
                          </button>
                        </div>

                        {expanded && (
                          <div className="px-4 pb-5 border-t border-slate-100">
                            {editing ? (
                              <div className="pt-4 space-y-3">
                                <label
                                  htmlFor={`strategy-edit-${strategy.strategy_id}`}
                                  className="block text-xs font-medium text-slate-500"
                                >
                                  Edit playbook (Markdown)
                                </label>
                                <textarea
                                  id={`strategy-edit-${strategy.strategy_id}`}
                                  value={editDraft}
                                  onChange={(e) => setEditDraft(e.target.value)}
                                  rows={14}
                                  className={textareaClass}
                                />
                                {saveError ? (
                                  <p className="text-sm text-red-600">{saveError}</p>
                                ) : null}
                                <div className="flex items-center gap-2">
                                  <Button
                                    variant="primary"
                                    onClick={() => saveStrategy(strategy.strategy_id)}
                                    disabled={saving}
                                  >
                                    {saving ? 'Saving…' : 'Save'}
                                  </Button>
                                  <Button
                                    variant="secondary"
                                    onClick={cancelEditing}
                                    disabled={saving}
                                  >
                                    <X className="w-4 h-4" />
                                    Cancel
                                  </Button>
                                </div>
                              </div>
                            ) : (
                              <>
                                <div className="pt-4">
                                  <MarkdownFallback content={strategy.strategy_text} bare />
                                </div>
                                <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-400 space-y-1">
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
      </div>
    </div>
  );
}
