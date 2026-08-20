'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { apiFetch } from '@/lib/apiClient';
import MarkdownFallback from '@/components/MarkdownFallback';
import {
  type TeamContextSection,
  SUGGESTED_SECTIONS,
  renderTeamContextPreview,
  renderedTeamContextLength,
  newSectionId,
  applyStarterTemplate,
  TEAM_CONTEXT_HARD_CAP,
} from '@/lib/teamContext';
import {
  ScrollText,
  Plus,
  Save,
  CheckCircle,
  XCircle,
  ChevronUp,
  ChevronDown,
  Trash2,
  LayoutTemplate,
  Pencil,
  AlertTriangle,
} from 'lucide-react';
import { PageHeader, Button, Skeleton, TeamPageShell } from '@/components/ui-flow';

type PageMode = 'view' | 'edit';

function parseTeamContextSections(data: unknown): TeamContextSection[] {
  if (!data || typeof data !== 'object') return [];
  const obj = data as Record<string, unknown>;
  const tc = obj.team_context;
  if (!tc) return [];
  if (Array.isArray(tc)) {
    return tc
      .filter((s): s is Record<string, unknown> => s && typeof s === 'object')
      .map((s) => ({
        id: String(s.id || ''),
        title: String(s.title || ''),
        content: String(s.content || ''),
      }));
  }
  if (typeof tc === 'object' && tc !== null) {
    const sections = (tc as Record<string, unknown>).sections;
    if (Array.isArray(sections)) {
      return sections
        .filter((s): s is Record<string, unknown> => s && typeof s === 'object')
        .map((s) => ({
          id: String(s.id || ''),
          title: String(s.title || s.id || ''),
          content: String(s.content || ''),
        }));
    }
  }
  return [];
}

function hasContent(sections: TeamContextSection[]): boolean {
  return sections.some((s) => s.content.trim().length > 0);
}

const cardClass =
  'bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden';

const ghostBtnClass =
  'inline-flex items-center gap-2 h-9 px-3.5 rounded-full text-[13.5px] font-medium border border-slate-200/70 bg-white text-slate-900 hover:bg-slate-50 transition';

export default function TeamContextPage() {
  const { identity } = useIdentity();
  const teamId = identity?.team_node_id;

  const [sections, setSections] = useState<TeamContextSection[]>([]);
  const [mode, setMode] = useState<PageMode>('edit');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showTemplateConfirm, setShowTemplateConfirm] = useState(false);

  const renderedChars = useMemo(() => renderedTeamContextLength(sections), [sections]);
  const renderedPreview = useMemo(() => renderTeamContextPreview(sections), [sections]);
  const overCap = renderedChars > TEAM_CONTEXT_HARD_CAP;
  const nearCap = renderedChars > TEAM_CONTEXT_HARD_CAP * 0.9;
  const budgetPct = Math.min(100, (renderedChars / TEAM_CONTEXT_HARD_CAP) * 100);

  const loadConfig = useCallback(async () => {
    if (!teamId) return;
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch('/api/team/config');
      if (res.ok) {
        const data = await res.json();
        const parsed = parseTeamContextSections(data);
        setSections(parsed);
        setMode(hasContent(parsed) ? 'view' : 'edit');
      } else {
        setMessage({ type: 'error', text: `Failed to load config (${res.status})` });
      }
    } catch (e) {
      console.error('Failed to load team context:', e);
      setMessage({ type: 'error', text: 'Failed to load team context' });
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const updateSection = (index: number, patch: Partial<TeamContextSection>) => {
    setSections((prev) =>
      prev.map((sec, i) => (i !== index ? sec : { ...sec, ...patch })),
    );
  };

  const addSection = () => {
    setMode('edit');
    setSections((prev) => [
      ...prev,
      { id: newSectionId('New section'), title: 'New section', content: '' },
    ]);
  };

  const deleteSection = (index: number) => {
    setSections((prev) => prev.filter((_, i) => i !== index));
  };

  const moveSection = (index: number, direction: 'up' | 'down') => {
    const target = direction === 'up' ? index - 1 : index + 1;
    if (target < 0 || target >= sections.length) return;
    setSections((prev) => {
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const applyTemplate = () => {
    if (sections.length > 0) {
      setShowTemplateConfirm(true);
      return;
    }
    setSections(applyStarterTemplate());
    setMode('edit');
  };

  const confirmApplyTemplate = () => {
    setSections(applyStarterTemplate());
    setMode('edit');
    setShowTemplateConfirm(false);
  };

  const save = async () => {
    if (overCap) return;
    setSaving(true);
    setMessage(null);
    try {
      const res = await apiFetch('/api/team/config', {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ team_context: { sections } }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
      setMessage({ type: 'success', text: 'Team context saved successfully' });
      setMode('view');
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      setMessage({ type: 'error', text: errorMessage });
    } finally {
      setSaving(false);
    }
  };

  const hintForSection = (id: string) =>
    SUGGESTED_SECTIONS.find((s) => s.id === id)?.hint;

  const progressBarColor = overCap
    ? 'bg-red-500'
    : nearCap
      ? 'bg-amber-500'
      : 'bg-emerald-500';

  if (!teamId) {
    return (
      <TeamPageShell>
        <p className="text-slate-500">Sign in as a team user to edit team context.</p>
      </TeamPageShell>
    );
  }

  return (
    <TeamPageShell
      header={
        <PageHeader
          eyebrow="Team console"
          title="Context"
          subtitle="Operating facts injected into every investigation's system prompt"
          actions={
            mode === 'view' ? (
              <Button type="button" onClick={() => setMode('edit')}>
                <Pencil className="w-4 h-4" />
                Edit
              </Button>
            ) : (
              <>
                <Button type="button" variant="secondary" onClick={applyTemplate}>
                  <LayoutTemplate className="w-4 h-4" />
                  Start from template
                </Button>
                <Button type="button" variant="secondary" onClick={addSection}>
                  <Plus className="w-4 h-4" />
                  Add section
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  onClick={save}
                  disabled={saving || overCap || loading}
                >
                  {saving ? (
                    <span className="live-dot w-2 h-2 rounded-full shrink-0" aria-hidden />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  Save
                </Button>
              </>
            )
          }
        />
      }
    >
      {message && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
            message.type === 'success'
              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
              : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
          }`}
        >
          {message.type === 'success' ? (
            <CheckCircle className="w-4 h-4 shrink-0" />
          ) : (
            <XCircle className="w-4 h-4 shrink-0" />
          )}
          {message.text}
        </div>
      )}

      {/* Budget meter */}
      {!loading && sections.length > 0 && (
        <div
          className={`px-4 py-3 rounded-xl border ${
            overCap
              ? 'border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20'
              : nearCap
                ? 'border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20'
                : 'border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800'
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2 text-sm">
            <div className="flex items-center gap-2">
              {overCap && (
                <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0" />
              )}
              <span className="text-slate-600 dark:text-slate-400">
                Injected prompt size:{' '}
                <span
                  className={`font-semibold ${
                    overCap
                      ? 'text-red-600 dark:text-red-400'
                      : nearCap
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-slate-900 dark:text-white'
                  }`}
                >
                  {renderedChars.toLocaleString()}
                </span>
                {' / '}
                {TEAM_CONTEXT_HARD_CAP.toLocaleString()}
              </span>
            </div>
            {mode === 'edit' && overCap && (
              <span className="text-xs text-red-600 dark:text-red-400">
                Reduce content before saving
              </span>
            )}
          </div>
          <div className="h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${progressBarColor}`}
              style={{ width: `${budgetPct}%` }}
            />
          </div>
        </div>
      )}

      {loading ? (
        <div className="py-12 space-y-3 max-w-3xl">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      ) : sections.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-slate-300 dark:border-slate-600 rounded-xl bg-slate-50 dark:bg-slate-800/50">
          <ScrollText className="w-10 h-10 text-slate-400 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400 mb-1">No sections yet</p>
          <p className="text-slate-500 text-sm mb-6">
            Add custom sections or start from the suggested template
          </p>
          <div className="flex justify-center gap-2">
            <button type="button" onClick={addSection} className={ghostBtnClass}>
              <Plus className="w-4 h-4" />
              Add section
            </button>
            <button
              type="button"
              onClick={() => {
                setSections(applyStarterTemplate());
                setMode('edit');
              }}
              className="inline-flex items-center gap-2 h-9 px-3.5 rounded-full text-[13.5px] font-medium bg-emerald-100/50 text-emerald-700 hover:bg-emerald-100/80 transition"
            >
              <LayoutTemplate className="w-4 h-4" />
              Use starter template
            </button>
          </div>
        </div>
      ) : mode === 'view' ? (
        <div className={`${cardClass} p-6`}>
          {renderedPreview ? (
            <MarkdownFallback content={renderedPreview} bare />
          ) : (
            <p className="text-sm text-slate-500">
              All sections are empty — nothing will be injected into the agent prompt.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {sections.map((section, index) => {
            const hint = hintForSection(section.id);
            return (
              <div key={`${section.id}-${index}`} className={cardClass}>
                <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80">
                  <input
                    type="text"
                    value={section.title}
                    onChange={(e) => updateSection(index, { title: e.target.value })}
                    className="flex-1 min-w-0 text-sm font-semibold bg-transparent border-b border-transparent hover:border-slate-300 focus:border-emerald-500 focus:outline-none text-slate-900 dark:text-white"
                    placeholder="Section title"
                  />
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={() => moveSection(index, 'up')}
                      disabled={index === 0}
                      className="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-30 text-slate-500"
                      title="Move up"
                    >
                      <ChevronUp className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => moveSection(index, 'down')}
                      disabled={index === sections.length - 1}
                      className="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-30 text-slate-500"
                      title="Move down"
                    >
                      <ChevronDown className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteSection(index)}
                      className="p-1.5 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 text-slate-500 hover:text-red-600 dark:hover:text-red-400"
                      title="Delete section"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="p-4">
                  {hint ? <p className="text-xs text-slate-500 mb-2">{hint}</p> : null}
                  <textarea
                    value={section.content}
                    onChange={(e) => updateSection(index, { content: e.target.value })}
                    rows={8}
                    className="w-full text-sm font-mono bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-600 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 text-slate-800 dark:text-slate-200 resize-y min-h-[160px]"
                    placeholder="Markdown content for this section…"
                  />
                  <div className="mt-2 text-xs text-slate-400 text-right">
                    {(section.content?.length || 0).toLocaleString()} chars
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showTemplateConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-600 shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
              Replace existing sections?
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
              Starting from the template will replace all {sections.length} current section
              {sections.length === 1 ? '' : 's'} with the suggested starter set.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowTemplateConfirm(false)}
                className="px-4 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmApplyTemplate}
                className="px-4 py-2 text-sm bg-emerald-100/50 text-emerald-700 rounded-lg hover:bg-emerald-100/80"
              >
                Replace with template
              </button>
            </div>
          </div>
        </div>
      )}
    </TeamPageShell>
  );
}
