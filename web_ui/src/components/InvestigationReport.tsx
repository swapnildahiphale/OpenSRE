'use client';

import { useState } from 'react';
import {
  AlertTriangle,
  Shield,
  Clock,
  Target,
  Lightbulb,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

export interface InvestigationReportData {
  version?: number;
  title: string;
  severity?: string;
  status?: string;
  affected_services?: string[];
  executive_summary?: string;
  impact?: {
    user_facing?: string;
    service_impact?: string;
    blast_radius?: string;
  };
  timeline?: { time: string; event: string }[];
  root_cause?: {
    summary: string;
    confidence?: string;
    details?: string | null;
  };
  action_items?: { priority: string; action: string }[];
  lessons_learned?: string[];
}

const SEVERITY_COLORS: Record<string, { border: string; badge: string; text: string }> = {
  critical: {
    border: 'border-l-clay',
    badge: 'bg-clay-light/15 text-clay-dark dark:bg-clay/20 dark:text-clay-light',
    text: 'text-clay',
  },
  high: {
    border: 'border-l-orange-500',
    badge: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300',
    text: 'text-orange-500',
  },
  medium: {
    border: 'border-l-yellow-500',
    badge: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
    text: 'text-yellow-500',
  },
  low: {
    border: 'border-l-forest',
    badge: 'bg-forest-light/15 text-forest-dark dark:bg-forest/20 dark:text-forest-light',
    text: 'text-forest',
  },
  info: {
    border: 'border-l-stone-400',
    badge: 'bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-300',
    text: 'text-stone-400',
  },
};

const STATUS_COLORS: Record<string, string> = {
  resolved: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
  mitigated: 'bg-forest-light/15 text-forest-dark dark:bg-forest/20 dark:text-forest-light',
  ongoing: 'bg-clay-light/15 text-clay-dark dark:bg-clay/20 dark:text-clay-light',
  inconclusive: 'bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-300',
};

const CONFIDENCE_COLORS: Record<string, string> = {
  confirmed: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
  probable: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
  hypothesis: 'bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-300',
};

const PRIORITY_STYLES: Record<string, string> = {
  immediate: 'border-l-clay bg-clay-light/10 dark:bg-clay/10',
  short_term: 'border-l-yellow-500 bg-yellow-50 dark:bg-yellow-900/10',
  long_term: 'border-l-forest bg-forest-light/10 dark:bg-forest/20',
  // Also accept raw priority names from LLM output
  critical: 'border-l-clay bg-clay-light/10 dark:bg-clay/10',
  high: 'border-l-orange-500 bg-orange-50 dark:bg-orange-900/10',
  medium: 'border-l-yellow-500 bg-yellow-50 dark:bg-yellow-900/10',
  low: 'border-l-forest bg-forest-light/10 dark:bg-forest/20',
};

function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      {icon}
      <h4 className="text-sm font-semibold text-stone-700 dark:text-stone-300 uppercase tracking-wide">
        {title}
      </h4>
    </div>
  );
}

/** Normalize server data to handle field aliases, camelCase, and type mismatches. */
function normalizeReport(raw: InvestigationReportData & Record<string, any>): InvestigationReportData {
  const r = { ...raw };

  // camelCase -> snake_case aliases
  if (!r.root_cause && r.rootCause) r.root_cause = r.rootCause;
  if (!r.root_cause && r.rootCauseAnalysis) r.root_cause = r.rootCauseAnalysis;
  if (!r.action_items && r.actionItems) r.action_items = r.actionItems;
  if (!r.lessons_learned && r.lessonsLearned) r.lessons_learned = r.lessonsLearned;
  if (!r.affected_services && r.affectedServices) r.affected_services = r.affectedServices;
  if (!r.executive_summary && r.executiveSummary) r.executive_summary = r.executiveSummary;
  if (!r.status && r.resolutionStatus) r.status = r.resolutionStatus;

  // snake_case aliases
  if (!r.affected_services) r.affected_services = r.services || r.services_affected;
  if (!r.status) r.status = r.resolution_status;
  if (!r.root_cause && r.root_cause_analysis) r.root_cause = r.root_cause_analysis;

  // executive_summary: object -> string (LLMs sometimes return {incident, impact, resolution})
  if (r.executive_summary && typeof r.executive_summary === 'object') {
    r.executive_summary = Object.values(r.executive_summary).filter(Boolean).join(' ');
  }

  // root_cause: string or object -> {summary, confidence}
  const rc: any = r.root_cause;
  if (typeof rc === 'string') {
    r.root_cause = { summary: rc, confidence: 'probable' };
  } else if (rc && typeof rc === 'object' && !rc.summary) {
    r.root_cause = {
      summary: rc.analysis || rc.description || rc.detail || rc.primary_root_cause || JSON.stringify(rc),
      confidence: rc.confidence || 'probable',
      details: rc.details || rc.contributing_factors || null,
    };
  }

  // Normalize action_items: description/recommendation -> action
  if (r.action_items && Array.isArray(r.action_items)) {
    r.action_items = r.action_items.map((item: any) => ({
      ...item,
      action: item.action || item.description || item.detail || item.recommendation || item.title || '',
    }));
  } else {
    r.action_items = [];
  }

  // Normalize timeline: dict -> array
  if (r.timeline && !Array.isArray(r.timeline)) {
    const tl = r.timeline as any;
    r.timeline = Object.entries(tl).map(([k, v]) => ({
      time: k.replace(/_/g, ' '),
      event: String(v),
    }));
  }

  // Normalize lessons_learned: dict -> array
  if (r.lessons_learned && !Array.isArray(r.lessons_learned)) {
    const ll = r.lessons_learned as any;
    const flat: string[] = [];
    for (const items of Object.values(ll)) {
      if (Array.isArray(items)) flat.push(...items.map(String));
      else if (typeof items === 'string') flat.push(items);
    }
    r.lessons_learned = flat;
  }

  return r;
}

export default function InvestigationReport({ report }: { report: InvestigationReportData }) {
  const [timelineExpanded, setTimelineExpanded] = useState(false);

  const normalized = normalizeReport(report as any);
  const sev = (normalized.severity || 'info').toLowerCase();
  const sevColors = SEVERITY_COLORS[sev] || SEVERITY_COLORS.info;
  const statusColor = STATUS_COLORS[(normalized.status || '').toLowerCase()] || STATUS_COLORS.inconclusive;

  const timeline = Array.isArray(normalized.timeline) ? normalized.timeline : [];
  const showTimelineToggle = timeline.length > 5;
  const visibleTimeline = timelineExpanded ? timeline : timeline.slice(0, 5);

  return (
    <div className={`border-l-4 ${sevColors.border} rounded-r-lg bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 overflow-hidden`}>
      {/* Header */}
      <div className="p-4 pb-3">
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-lg font-bold text-stone-900 dark:text-white leading-tight">
            {normalized.title}
          </h3>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full uppercase ${sevColors.badge}`}>
              {sev}
            </span>
            {normalized.status && (
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColor}`}>
                {normalized.status.replace('_', ' ')}
              </span>
            )}
          </div>
        </div>
        {normalized.affected_services && normalized.affected_services.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            {normalized.affected_services.map((svc) => (
              <span
                key={svc}
                className="text-xs font-mono px-1.5 py-0.5 rounded bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-400"
              >
                {svc}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Executive Summary */}
      {normalized.executive_summary && (
        <div className="px-4 py-3 border-t border-stone-100 dark:border-stone-700">
          <SectionHeader
            icon={<Shield className="w-4 h-4 text-stone-500" />}
            title="Executive Summary"
          />
          <p className="text-sm text-stone-700 dark:text-stone-300 leading-relaxed">
            {normalized.executive_summary}
          </p>
        </div>
      )}

      {/* Impact */}
      {normalized.impact && (normalized.impact.user_facing || normalized.impact.service_impact || normalized.impact.blast_radius) && (
        <div className="px-4 py-3 border-t border-stone-100 dark:border-stone-700">
          <SectionHeader
            icon={<Target className="w-4 h-4 text-stone-500" />}
            title="Impact"
          />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {normalized.impact.user_facing && (
              <div className="bg-stone-50 dark:bg-stone-700/50 rounded-lg p-2.5">
                <div className="text-xs text-stone-500 uppercase tracking-wide mb-1">User-Facing</div>
                <div className="text-sm text-stone-700 dark:text-stone-300">{normalized.impact.user_facing}</div>
              </div>
            )}
            {normalized.impact.service_impact && (
              <div className="bg-stone-50 dark:bg-stone-700/50 rounded-lg p-2.5">
                <div className="text-xs text-stone-500 uppercase tracking-wide mb-1">Service Impact</div>
                <div className="text-sm text-stone-700 dark:text-stone-300">{normalized.impact.service_impact}</div>
              </div>
            )}
            {normalized.impact.blast_radius && (
              <div className="bg-stone-50 dark:bg-stone-700/50 rounded-lg p-2.5">
                <div className="text-xs text-stone-500 uppercase tracking-wide mb-1">Blast Radius</div>
                <div className="text-sm text-stone-700 dark:text-stone-300">{normalized.impact.blast_radius}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Timeline */}
      {timeline.length > 0 && (
        <div className="px-4 py-3 border-t border-stone-100 dark:border-stone-700">
          <SectionHeader
            icon={<Clock className="w-4 h-4 text-stone-500" />}
            title="Timeline"
          />
          <div className="relative ml-2">
            {visibleTimeline.map((entry, i) => (
              <div key={i} className="flex items-start gap-3 pb-2 last:pb-0">
                <div className="flex flex-col items-center">
                  <div className="w-2 h-2 rounded-full bg-stone-400 dark:bg-stone-500 mt-1.5 flex-shrink-0" />
                  {i < visibleTimeline.length - 1 && (
                    <div className="w-px h-full bg-stone-200 dark:bg-stone-700 min-h-[16px]" />
                  )}
                </div>
                <div className="flex items-baseline gap-2 min-w-0">
                  <span className="text-xs font-mono text-stone-500 flex-shrink-0">{entry.time}</span>
                  <span className="text-sm text-stone-700 dark:text-stone-300">{entry.event}</span>
                </div>
              </div>
            ))}
          </div>
          {showTimelineToggle && (
            <button
              onClick={() => setTimelineExpanded(!timelineExpanded)}
              className="flex items-center gap-1 text-xs text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 mt-1 ml-2"
            >
              {timelineExpanded ? (
                <>
                  <ChevronDown className="w-3 h-3" /> Show less
                </>
              ) : (
                <>
                  <ChevronRight className="w-3 h-3" /> Show {timeline.length - 5} more
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* Root Cause */}
      {normalized.root_cause && normalized.root_cause.summary && (
        <div className="px-4 py-3 border-t border-stone-100 dark:border-stone-700">
          <SectionHeader
            icon={<AlertTriangle className="w-4 h-4 text-stone-500" />}
            title="Root Cause"
          />
          {normalized.root_cause.confidence && (
            <span
              className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full mb-2 ${
                CONFIDENCE_COLORS[normalized.root_cause.confidence] || CONFIDENCE_COLORS.hypothesis
              }`}
            >
              {normalized.root_cause.confidence}
            </span>
          )}
          <p className="text-sm text-stone-700 dark:text-stone-300 leading-relaxed">
            {normalized.root_cause.summary}
          </p>
          {normalized.root_cause.details && (
            <p className="text-sm text-stone-500 dark:text-stone-400 mt-1.5 leading-relaxed">
              {normalized.root_cause.details}
            </p>
          )}
        </div>
      )}

      {/* Action Items */}
      {normalized.action_items && normalized.action_items.length > 0 && (
        <div className="px-4 py-3 border-t border-stone-100 dark:border-stone-700">
          <SectionHeader
            icon={<CheckCircle2 className="w-4 h-4 text-stone-500" />}
            title="Action Items"
          />
          <div className="space-y-1.5">
            {normalized.action_items.map((item, i) => (
              <div
                key={i}
                className={`border-l-2 rounded-r px-3 py-1.5 ${
                  PRIORITY_STYLES[item.priority] || 'border-l-stone-300 bg-stone-50 dark:bg-stone-700/50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-stone-500 uppercase flex-shrink-0">
                    {item.priority.replace('_', ' ')}
                  </span>
                  <span className="text-sm text-stone-700 dark:text-stone-300">{item.action}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Lessons Learned */}
      {normalized.lessons_learned && normalized.lessons_learned.length > 0 && (
        <div className="px-4 py-3 border-t border-stone-100 dark:border-stone-700">
          <SectionHeader
            icon={<Lightbulb className="w-4 h-4 text-stone-500" />}
            title="Lessons Learned"
          />
          <ul className="space-y-1">
            {normalized.lessons_learned.map((lesson, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-stone-700 dark:text-stone-300">
                <span className="text-stone-400 mt-0.5">&#8226;</span>
                <span>{lesson}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
