'use client';

import { useEffect, useState, useCallback } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { apiFetch } from '@/lib/apiClient';
import { 
  Activity, 
  RefreshCcw,
  Download,
  Search,
  Filter,
  ChevronDown,
  ChevronRight,
  Key,
  Settings,
  Bot,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  User,
  Hash
} from 'lucide-react';

// Types
interface AuditEvent {
  id: string;
  source: 'token' | 'config' | 'agent';
  event_type: string;
  timestamp: string;
  actor: string | null;
  team_node_id: string | null;
  team_name: string | null;
  summary: string;
  details: Record<string, any>;
  correlation_id: string | null;
}

interface AuditResponse {
  events: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

interface TeamOption {
  node_id: string;
  name: string;
}

// Source badge colors
const sourceColors: Record<string, { bg: string; text: string; icon: any }> = {
  token: { bg: 'bg-stone-100 dark:bg-stone-700', text: 'text-stone-700 dark:text-stone-300', icon: Key },
  config: { bg: 'bg-stone-100 dark:bg-stone-700', text: 'text-stone-700 dark:text-stone-300', icon: Settings },
  agent: { bg: 'bg-stone-100 dark:bg-stone-700', text: 'text-stone-700 dark:text-stone-300', icon: Bot },
};

// Event type icons
const eventTypeIcons: Record<string, { icon: any; color: string }> = {
  issued: { icon: CheckCircle, color: 'text-green-500' },
  revoked: { icon: XCircle, color: 'text-clay' },
  expired: { icon: Clock, color: 'text-orange-500' },
  permission_denied: { icon: AlertTriangle, color: 'text-clay' },
  config_updated: { icon: Settings, color: 'text-forest' },
  agent_completed: { icon: CheckCircle, color: 'text-green-500' },
  agent_failed: { icon: XCircle, color: 'text-clay' },
  agent_timeout: { icon: Clock, color: 'text-orange-500' },
  agent_running: { icon: Activity, color: 'text-forest' },
};

export default function AuditPage() {
  const { identity, loading: identityLoading } = useIdentity();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [expandedEvent, setExpandedEvent] = useState<string | null>(null);
  
  // Filters
  const [sources, setSources] = useState<string[]>(['token', 'config', 'agent']);
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [timeRange, setTimeRange] = useState('24h');
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  
  // Team options
  const [teams, setTeams] = useState<TeamOption[]>([]);
  
  const orgId = identity?.org_id || 'org1';
  const isAdmin = identity?.role === 'admin';

  // Load teams for filter dropdown
  useEffect(() => {
    if (!isAdmin) return;
    apiFetch(`/api/admin/orgs/${orgId}/nodes`)
      .then(res => res.json())
      .then(data => {
        const teamNodes = (data || [])
          .filter((n: any) => n.node_type === 'team')
          .map((n: any) => ({ node_id: n.node_id, name: n.name || n.node_id }));
        setTeams(teamNodes);
      })
      .catch(() => {});
  }, [orgId, isAdmin]);

  // Calculate time range
  const getTimeRange = () => {
    const now = new Date();
    let since: Date | null = null;
    switch (timeRange) {
      case '1h': since = new Date(now.getTime() - 60 * 60 * 1000); break;
      case '24h': since = new Date(now.getTime() - 24 * 60 * 60 * 1000); break;
      case '7d': since = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000); break;
      case '30d': since = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000); break;
      default: since = null;
    }
    return since;
  };

  // Load audit events
  const loadEvents = useCallback(async (resetOffset = false) => {
    if (!isAdmin) return;
    setLoading(true);
    
    const params = new URLSearchParams();
    if (sources.length > 0 && sources.length < 3) {
      params.set('sources', sources.join(','));
    }
    if (selectedTeam) params.set('team_node_id', selectedTeam);
    if (searchQuery) params.set('search', searchQuery);
    
    const since = getTimeRange();
    if (since) params.set('since', since.toISOString());
    
    const currentOffset = resetOffset ? 0 : offset;
    params.set('limit', String(limit));
    params.set('offset', String(currentOffset));
    
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/audit?${params}`);
      if (res.ok) {
        const data: AuditResponse = await res.json();
        setEvents(data.events);
        setTotal(data.total);
        if (resetOffset) setOffset(0);
      }
    } catch (e) {
      console.error('Failed to load audit events', e);
    } finally {
      setLoading(false);
    }
  }, [orgId, isAdmin, sources, selectedTeam, searchQuery, timeRange, limit, offset]);

  // Load on filter changes
  useEffect(() => {
    loadEvents(true);
  }, [sources, selectedTeam, searchQuery, timeRange, limit]);

  // Load on pagination
  useEffect(() => {
    if (offset > 0) loadEvents(false);
  }, [offset]);

  // Export CSV
  const exportCSV = async () => {
    const params = new URLSearchParams();
    if (sources.length > 0 && sources.length < 3) {
      params.set('sources', sources.join(','));
    }
    if (selectedTeam) params.set('team_node_id', selectedTeam);
    if (searchQuery) params.set('search', searchQuery);
    const since = getTimeRange();
    if (since) params.set('since', since.toISOString());
    
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/audit/export?${params}`);
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit_export_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }
    } catch (e) {
      console.error('Failed to export', e);
      alert('Failed to export audit log');
    }
  };

  // Toggle source filter
  const toggleSource = (source: string) => {
    if (sources.includes(source)) {
      if (sources.length > 1) {
        setSources(sources.filter(s => s !== source));
      }
    } else {
      setSources([...sources, source]);
    }
  };

  // Format timestamp
  const formatTime = (ts: string) => {
    const d = new Date(ts);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    
    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <p className="text-stone-500">Admin access required</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-stone-900 dark:text-white flex items-center gap-3">
            <Activity className="w-7 h-7 text-stone-500" />
            Unified Audit Log
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            View all activity across tokens, configuration, and agent runs
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadEvents(true)}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700 transition-colors"
          >
            <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={exportCSV}
            className="flex items-center gap-2 px-4 py-2 text-sm bg-stone-700 text-white rounded-lg hover:bg-stone-600 transition-colors"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-4 mb-6 shadow-sm">
        <div className="flex flex-wrap items-center gap-4">
          {/* Source filters */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-stone-400" />
            <span className="text-sm text-stone-500 mr-2">Sources:</span>
            {Object.entries(sourceColors).map(([source, style]) => (
              <button
                key={source}
                onClick={() => toggleSource(source)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full transition-all ${
                  sources.includes(source)
                    ? `${style.bg} ${style.text} ring-2 ring-offset-2 ring-offset-white dark:ring-offset-stone-900 ${style.text.replace('text-', 'ring-')}`
                    : 'bg-stone-100 dark:bg-stone-700 text-stone-500'
                }`}
              >
                <style.icon className="w-3 h-3" />
                {source.charAt(0).toUpperCase() + source.slice(1)}
              </button>
            ))}
          </div>

          {/* Team filter */}
          <select
            value={selectedTeam}
            onChange={(e) => setSelectedTeam(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300"
          >
            <option value="">All Teams</option>
            {teams.map(t => (
              <option key={t.node_id} value={t.node_id}>{t.name}</option>
            ))}
          </select>

          {/* Time range */}
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300"
          >
            <option value="1h">Last hour</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All time</option>
          </select>

          {/* Search */}
          <div className="flex-1 relative min-w-[200px]">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
            <input
              type="text"
              placeholder="Search events..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 placeholder-stone-400"
            />
          </div>
        </div>
      </div>

      {/* Results count */}
      <div className="text-sm text-stone-500 mb-4">
        Showing {events.length} of {total} events
      </div>

      {/* Event list */}
      <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <RefreshCcw className="w-6 h-6 animate-spin mx-auto text-stone-400" />
            <p className="text-stone-500 mt-2">Loading events...</p>
          </div>
        ) : events.length === 0 ? (
          <div className="p-8 text-center">
            <Activity className="w-8 h-8 mx-auto text-stone-300 mb-2" />
            <p className="text-stone-500">No events found</p>
            <p className="text-xs text-stone-400 mt-1">Try adjusting your filters</p>
          </div>
        ) : (
          <div className="divide-y divide-stone-100 dark:divide-stone-700">
            {events.map((event) => {
              const sourceStyle = sourceColors[event.source] || sourceColors.token;
              const eventIcon = eventTypeIcons[event.event_type] || { icon: Activity, color: 'text-stone-400' };
              const isExpanded = expandedEvent === event.id;

              return (
                <div key={event.id} className="hover:bg-stone-50 dark:hover:bg-stone-800/50 transition-colors">
                  <button
                    onClick={() => setExpandedEvent(isExpanded ? null : event.id)}
                    className="w-full flex items-start gap-4 p-4 text-left"
                  >
                    {/* Icon */}
                    <div className={`flex-shrink-0 mt-0.5 ${eventIcon.color}`}>
                      <eventIcon.icon className="w-5 h-5" />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Source badge */}
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${sourceStyle.bg} ${sourceStyle.text}`}>
                          <sourceStyle.icon className="w-3 h-3" />
                          {event.source}
                        </span>
                        
                        {/* Summary */}
                        <span className="font-medium text-stone-900 dark:text-white text-sm">
                          {event.summary}
                        </span>
                      </div>

                      {/* Metadata row */}
                      <div className="flex items-center gap-4 mt-1 text-xs text-stone-500">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatTime(event.timestamp)}
                        </span>
                        {event.actor && (
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {event.actor}
                          </span>
                        )}
                        {event.team_name && (
                          <span className="flex items-center gap-1">
                            <Hash className="w-3 h-3" />
                            {event.team_name}
                          </span>
                        )}
                        {event.correlation_id && (
                          <span className="font-mono text-xs text-stone-400 bg-stone-100 dark:bg-stone-700 px-1.5 py-0.5 rounded">
                            {event.correlation_id.substring(0, 8)}...
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Expand button */}
                    <div className="flex-shrink-0">
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-stone-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-stone-400" />
                      )}
                    </div>
                  </button>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="px-4 pb-4 ml-9">
                      <div className="bg-stone-50 dark:bg-stone-700 rounded-lg p-4">
                        <h4 className="text-xs font-medium text-stone-500 uppercase tracking-wide mb-2">Event Details</h4>
                        <pre className="text-xs text-stone-700 dark:text-stone-300 overflow-x-auto whitespace-pre-wrap">
                          {JSON.stringify(event.details, null, 2)}
                        </pre>
                        {event.correlation_id && (
                          <div className="mt-3 pt-3 border-t border-stone-200 dark:border-stone-600">
                            <span className="text-xs text-stone-500">Correlation ID: </span>
                            <code className="text-xs font-mono text-stone-700 dark:text-stone-300">{event.correlation_id}</code>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {total > limit && (
          <div className="flex items-center justify-between p-4 border-t border-stone-100 dark:border-stone-700 bg-stone-50 dark:bg-stone-700/50">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-4 py-2 text-sm rounded-lg bg-white dark:bg-stone-700 border border-stone-200 dark:border-stone-600 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-stone-100 dark:hover:bg-stone-700"
            >
              Previous
            </button>
            <span className="text-sm text-stone-500">
              Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="px-4 py-2 text-sm rounded-lg bg-white dark:bg-stone-700 border border-stone-200 dark:border-stone-600 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-stone-100 dark:hover:bg-stone-700"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

