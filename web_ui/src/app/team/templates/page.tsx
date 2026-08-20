'use client';

import { useEffect, useState } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import {
  LayoutTemplate,
  Search,
  Filter,
  Star,
  Users,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Sparkles,
  AlertCircle,
} from 'lucide-react';
import { apiFetch } from '@/lib/apiClient';
import { PageHeader, Button, Skeleton } from '@/components/ui-flow';

interface Template {
  id: string;
  name: string;
  slug: string;
  description: string;
  category: string;
  icon_url?: string;
  example_scenarios: string[];
  required_mcps: string[];
  usage_count: number;
  avg_rating?: number;
  version: string;
}

interface TemplateDetail extends Template {
  detailed_description?: string;
  template_json: any;
  demo_video_url?: string;
  required_tools: string[];
}

interface CurrentTemplate {
  id: string;
  template_id: string;
  template_name: string;
  applied_at: string;
  template_version: string;
  has_customizations: boolean;
}

const CATEGORIES = [
  { value: '', label: 'All Categories' },
  { value: 'incident-response', label: 'Incident Response' },
  { value: 'ci-cd', label: 'CI/CD' },
  { value: 'finops', label: 'FinOps' },
  { value: 'coding', label: 'Coding' },
  { value: 'data', label: 'Data' },
  { value: 'observability', label: 'Observability' },
  { value: 'reliability', label: 'Reliability' },
  { value: 'demo', label: 'Demo' },
];

const CATEGORY_ICONS: Record<string, string> = {
  'incident-response': '🚨',
  'ci-cd': '🔧',
  'finops': '💰',
  'coding': '💻',
  'data': '🗄️',
  'observability': '📊',
  'reliability': '🛡️',
  'demo': '🎉',
};

export default function TemplatesPage() {
  const { identity } = useIdentity();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateDetail | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [applying, setApplying] = useState(false);
  const [currentTemplate, setCurrentTemplate] = useState<CurrentTemplate | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Load templates
  useEffect(() => {
    loadTemplates();
    loadCurrentTemplate();
  }, [selectedCategory, searchQuery]);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedCategory) params.set('category', selectedCategory);
      if (searchQuery) params.set('search', searchQuery);

      const res = await apiFetch(`/api/team/templates?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setTemplates(data.templates || []);
      }
    } catch (e) {
      console.error('Failed to load templates:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadCurrentTemplate = async () => {
    try {
      const res = await apiFetch('/api/team/templates/current');
      if (res.ok) {
        const data = await res.json();
        setCurrentTemplate(data.application || null);
      }
    } catch (e) {
      console.error('Failed to load current template:', e);
    }
  };

  const handlePreview = async (templateId: string) => {
    try {
      const res = await apiFetch(`/api/team/templates/${templateId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedTemplate(data);
        setShowPreview(true);
      }
    } catch (e) {
      console.error('Failed to load template details:', e);
    }
  };

  const handleApply = async (templateId: string) => {
    if (!confirm('Apply this template to your team? This will update your agent configuration.')) {
      return;
    }

    setApplying(true);
    setMessage(null);

    try {
      const res = await apiFetch(`/api/team/templates/${templateId}/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customize: {} }),
      });

      const data = await res.json();

      if (res.ok) {
        setMessage({
          type: 'success',
          text: `Template applied successfully! ${data.message || ''}`,
        });
        setShowPreview(false);
        loadCurrentTemplate();
        // Reload page after 2 seconds to show updated config
        setTimeout(() => window.location.reload(), 2000);
      } else {
        setMessage({
          type: 'error',
          text: data.error || 'Failed to apply template',
        });
      }
    } catch (e: any) {
      setMessage({
        type: 'error',
        text: e?.message || 'Failed to apply template',
      });
    } finally {
      setApplying(false);
    }
  };

  const filteredTemplates = templates;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <PageHeader
        eyebrow="Team console"
        title="Templates"
        subtitle="Pre-configured agent systems optimized for specific use cases"
      />

        {/* Current Template Badge */}
        {currentTemplate && (
          <div className="mt-6 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-[1.5rem] p-4 flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-green-900 dark:text-green-100">
                Current Template: {currentTemplate.template_name}
              </p>
              <p className="text-xs text-green-700 dark:text-green-300 mt-1">
                Applied on {new Date(currentTemplate.applied_at).toLocaleDateString()}
                {currentTemplate.has_customizations && ' • Customized'}
              </p>
            </div>
          </div>
        )}

        {/* Message */}
        {message && (
          <div
            className={`mt-4 p-4 rounded-lg border flex items-start gap-3 ${
              message.type === 'success'
                ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                : 'bg-rose-50 dark:bg-rose-900/20 border-rose-200 dark:border-rose-500'
            }`}
          >
            {message.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 mt-0.5" />
            ) : (
              <XCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 mt-0.5" />
            )}
            <p
              className={`text-sm ${
                message.type === 'success'
                  ? 'text-green-900 dark:text-green-100'
                  : 'text-rose-700 dark:text-rose-400'
              }`}
            >
              {message.text}
            </p>
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-4 mt-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input
              type="text"
              placeholder="Search templates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-200/70 rounded-full bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
            />
          </div>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-4 py-2 border border-slate-200/70 rounded-full bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
          >
            {CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </select>
        </div>

      {/* Templates Grid */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 gap-3 w-full max-w-2xl mx-auto">
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      ) : filteredTemplates.length === 0 ? (
        <div className="text-center py-12">
          <LayoutTemplate className="w-16 h-16 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-600 dark:text-slate-400">No templates found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates.map((template) => (
            <div
              key={template.id}
              className="bg-white dark:bg-slate-800 border border-slate-200/70 rounded-[1.5rem] p-6 hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => handlePreview(template.id)}
            >
              {/* Category Badge */}
              <div className="flex items-center justify-between mb-4">
                <span className="text-2xl">{CATEGORY_ICONS[template.category] || '📦'}</span>
                <span className="text-xs px-2 py-1 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded">
                  {template.category}
                </span>
              </div>

              {/* Title */}
              <h3 className="text-[14.5px] text-slate-900 dark:text-white mb-2">
                {template.name}
              </h3>

              {/* Description */}
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 line-clamp-3">
                {template.description}
              </p>

              {/* Stats */}
              <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400 mb-4">
                <div className="flex items-center gap-1">
                  <Users className="w-4 h-4" />
                  {template.usage_count}
                </div>
                {template.avg_rating && (
                  <div className="flex items-center gap-1">
                    <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                    {template.avg_rating.toFixed(1)}
                  </div>
                )}
              </div>

              {/* Required MCPs */}
              <div className="flex flex-wrap gap-2">
                {template.required_mcps.slice(0, 3).map((mcp) => (
                  <span
                    key={mcp}
                    className="text-xs px-2 py-1 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 rounded"
                  >
                    {mcp}
                  </span>
                ))}
                {template.required_mcps.length > 3 && (
                  <span className="text-xs px-2 py-1 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded">
                    +{template.required_mcps.length - 3} more
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview Modal */}
      {showPreview && selectedTemplate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-slate-700 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            {/* Header */}
            <div className="p-6 border-b border-slate-200 dark:border-slate-600">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <span className="text-4xl">
                    {CATEGORY_ICONS[selectedTemplate.category] || '📦'}
                  </span>
                  <div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                      {selectedTemplate.name}
                    </h2>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                      {selectedTemplate.category} • v{selectedTemplate.version}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowPreview(false)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  <XCircle className="w-6 h-6" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6 space-y-6">
              {/* Description */}
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">
                  Description
                </h3>
                <p className="text-slate-600 dark:text-slate-400">
                  {selectedTemplate.description}
                </p>
              </div>

              {/* Example Scenarios */}
              {selectedTemplate.example_scenarios.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">
                    Example Scenarios
                  </h3>
                  <ul className="list-disc list-inside space-y-1">
                    {selectedTemplate.example_scenarios.map((scenario, idx) => (
                      <li key={idx} className="text-slate-600 dark:text-slate-400">
                        {scenario}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Required Integrations */}
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">
                  Required Integrations
                </h3>
                <div className="flex flex-wrap gap-2">
                  {selectedTemplate.required_mcps.map((mcp) => (
                    <span
                      key={mcp}
                      className="px-3 py-1 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 rounded-lg text-sm"
                    >
                      {mcp}
                    </span>
                  ))}
                </div>
              </div>

              {/* Agents */}
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">
                  Agents Included
                </h3>
                <div className="space-y-2">
                  {Object.keys(selectedTemplate.template_json.agents || {}).map((agentKey) => {
                    const agent = selectedTemplate.template_json.agents[agentKey];
                    return (
                      <div
                        key={agentKey}
                        className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg"
                      >
                        <p className="font-medium text-slate-900 dark:text-white">
                          {agent.name}
                        </p>
                        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                          {agent.description}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Stats */}
              <div className="flex items-center gap-6 text-sm text-slate-600 dark:text-slate-400">
                <div className="flex items-center gap-2">
                  <Users className="w-5 h-5" />
                  <span>{selectedTemplate.usage_count} teams using this</span>
                </div>
                {selectedTemplate.avg_rating && (
                  <div className="flex items-center gap-2">
                    <Star className="w-5 h-5 fill-yellow-400 text-yellow-400" />
                    <span>{selectedTemplate.avg_rating.toFixed(1)} rating</span>
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="p-6 border-t border-slate-200 dark:border-slate-600 flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setShowPreview(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={() => handleApply(selectedTemplate.id)}
                disabled={applying}
              >
                {applying ? (
                  <>
                    <span className="live-dot w-2 h-2 rounded-full shrink-0" aria-hidden />
                    Applying...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Apply to My Team
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
