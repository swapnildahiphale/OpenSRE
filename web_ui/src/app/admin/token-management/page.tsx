'use client';

import { RequireRole } from '@/components/RequireRole';
import { apiFetch } from '@/lib/apiClient';
import { useIdentity } from '@/lib/useIdentity';
import { useEffect, useState } from 'react';
import {
  KeyRound,
  Copy,
  RefreshCcw,
  ShieldCheck,
  Trash2,
  Search,
  Filter,
  MoreVertical,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle,
  Plus,
  ChevronDown,
} from 'lucide-react';

type TokenStatus = 'active' | 'expiring' | 'unused' | 'revoked';

interface Token {
  token_id: string;
  team_node_id: string;
  team_name?: string;
  issued_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  issued_by: string;
  total_requests?: number;
  status: TokenStatus;
}

interface TokenHealth {
  active: number;
  expiring: number;
  unused: number;
  revoked: number;
}

export default function TokenManagementPage() {
  const { identity } = useIdentity();
  const orgId = identity?.org_id;

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tokens, setTokens] = useState<Token[]>([]);
  const [health, setHealth] = useState<TokenHealth>({ active: 0, expiring: 0, unused: 0, revoked: 0 });
  const [teams, setTeams] = useState<Array<{ node_id: string; name: string }>>([]);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [teamFilter, setTeamFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<TokenStatus | 'all'>('all');

  // Selected tokens for bulk operations
  const [selectedTokens, setSelectedTokens] = useState<Set<string>>(new Set());

  // Modals
  const [issueModalOpen, setIssueModalOpen] = useState(false);
  const [tokenDetailsModalOpen, setTokenDetailsModalOpen] = useState(false);
  const [revokeModalOpen, setRevokeModalOpen] = useState(false);
  const [selectedToken, setSelectedToken] = useState<Token | null>(null);

  // Issue token wizard state
  const [issueStep, setIssueStep] = useState(1);
  const [issueTeamId, setIssueTeamId] = useState('');
  const [issueExpiryDays, setIssueExpiryDays] = useState(90);
  const [issuedTokenSecret, setIssuedTokenSecret] = useState<string | null>(null);
  const [tokenSavedConfirmed, setTokenSavedConfirmed] = useState(false);

  useEffect(() => {
    if (!orgId) return;
    loadTokens();
    loadTeams();
  }, [orgId]);

  const loadTeams = async () => {
    try {
      const res = await fetch(`/api/admin/orgs/${orgId}/nodes`);
      if (!res.ok) {
        console.error('Failed to load teams');
        return;
      }
      const nodes = await res.json();
      const teamNodes = nodes
        .filter((n: any) => n.node_type === 'team')
        .map((n: any) => ({ node_id: n.node_id, name: n.name || n.node_id }));
      setTeams(teamNodes);
    } catch (e) {
      console.error('Failed to load teams:', e);
    }
  };

  const loadTokens = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/orgs/${orgId}/tokens`);

      if (!res.ok) {
        throw new Error(`Failed to load tokens: ${res.statusText}`);
      }

      const data = await res.json();
      const fetchedTokens: Token[] = (data.tokens || []).map((t: any) => ({
        ...t,
        status: t.status as TokenStatus,
      }));

      setTokens(fetchedTokens);

      // Calculate health stats
      const healthStats = {
        active: fetchedTokens.filter((t) => t.status === 'active').length,
        expiring: fetchedTokens.filter((t) => t.status === 'expiring').length,
        unused: fetchedTokens.filter((t) => t.status === 'unused').length,
        revoked: fetchedTokens.filter((t) => t.status === 'revoked').length,
      };
      setHealth(healthStats);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setIsLoading(false);
    }
  };

  const handleIssueToken = async () => {
    // Issue token workflow
    if (issueStep < 3) {
      setIssueStep(issueStep + 1);
      return;
    }

    // Final step - actually issue the token
    setIsLoading(true);
    try {
      const res = await fetch(`/api/admin/orgs/${orgId}/teams/${issueTeamId}/tokens`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          expires_in_days: issueExpiryDays,
        }),
      });

      if (!res.ok) {
        throw new Error(`Failed to issue token: ${res.statusText}`);
      }

      const data = await res.json();
      setIssuedTokenSecret(data.token);

      // Reload tokens
      await loadTokens();
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevokeToken = async (tokenId: string, reason?: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/admin/orgs/${orgId}/tokens/bulk-revoke`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token_ids: [tokenId],
          reason: reason || 'Revoked via admin UI',
        }),
      });

      if (!res.ok) {
        throw new Error(`Failed to revoke token: ${res.statusText}`);
      }

      await loadTokens();
      setRevokeModalOpen(false);
      setSelectedToken(null);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setIsLoading(false);
    }
  };

  const filteredTokens = tokens.filter((token) => {
    // Search filter
    if (searchQuery && !token.token_id.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !(token.team_name?.toLowerCase().includes(searchQuery.toLowerCase()))) {
      return false;
    }

    // Team filter
    if (teamFilter !== 'all' && token.team_node_id !== teamFilter) {
      return false;
    }

    // Status filter
    if (statusFilter !== 'all' && token.status !== statusFilter) {
      return false;
    }

    return true;
  });

  const uniqueTeams = teams.map((t) => t.node_id);

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const formatRelativeTime = (dateString: string | null) => {
    if (!dateString) return 'Never';
    const diff = Date.now() - new Date(dateString).getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  const getStatusBadge = (status: TokenStatus) => {
    switch (status) {
      case 'active':
        return <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-50 dark:bg-green-900/20 px-2 py-0.5 rounded-full"><CheckCircle className="w-3 h-3" /> Active</span>;
      case 'expiring':
        return <span className="inline-flex items-center gap-1 text-xs font-medium text-yellow-700 bg-yellow-50 dark:bg-yellow-900/20 px-2 py-0.5 rounded-full"><Clock className="w-3 h-3" /> Expiring</span>;
      case 'unused':
        return <span className="inline-flex items-center gap-1 text-xs font-medium text-stone-700 bg-stone-50 dark:bg-stone-800/20 px-2 py-0.5 rounded-full"><AlertCircle className="w-3 h-3" /> Unused</span>;
      case 'revoked':
        return <span className="inline-flex items-center gap-1 text-xs font-medium text-clay-dark bg-clay-light/10 dark:bg-clay/20 px-2 py-0.5 rounded-full"><XCircle className="w-3 h-3" /> Revoked</span>;
    }
  };

  return (
    <RequireRole role="admin" fallbackHref="/">
      <div className="p-8 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <KeyRound className="w-7 h-7 text-stone-500" />
            <div>
              <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">Token Management</h1>
              <p className="text-sm text-stone-500">Manage authentication tokens across all teams</p>
            </div>
          </div>

          <button
            onClick={() => {
              setIssueModalOpen(true);
              setIssueStep(1);
              setIssueTeamId('');
              setIssueExpiryDays(90);
              setIssuedTokenSecret(null);
              setTokenSavedConfirmed(false);
            }}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-forest text-white rounded-lg hover:bg-forest-dark"
          >
            <Plus className="w-4 h-4" /> Issue Token
          </button>
        </div>

        {!orgId && (
          <div className="text-sm text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-100 dark:border-yellow-900/40 rounded-lg p-3">
            Loading organization information...
          </div>
        )}

        {error && (
          <div className="text-sm text-clay bg-clay-light/10 dark:bg-clay/20 border border-red-100 dark:border-red-900/40 rounded-lg p-3">
            {error}
          </div>
        )}

        {/* Token Health Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 text-green-600 mb-2">
              <CheckCircle className="w-5 h-5" />
              <span className="text-sm font-medium">Active Tokens</span>
            </div>
            <div className="text-3xl font-bold text-stone-900 dark:text-white">{health.active}</div>
          </div>

          <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 text-yellow-600 mb-2">
              <Clock className="w-5 h-5" />
              <span className="text-sm font-medium">Expiring Soon</span>
            </div>
            <div className="text-3xl font-bold text-stone-900 dark:text-white">{health.expiring}</div>
            <p className="text-xs text-stone-500 mt-1">&lt; 7 days</p>
          </div>

          <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 text-stone-600 mb-2">
              <AlertCircle className="w-5 h-5" />
              <span className="text-sm font-medium">Unused</span>
            </div>
            <div className="text-3xl font-bold text-stone-900 dark:text-white">{health.unused}</div>
            <p className="text-xs text-stone-500 mt-1">Never used</p>
          </div>

          <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 text-clay mb-2">
              <XCircle className="w-5 h-5" />
              <span className="text-sm font-medium">Revoked</span>
            </div>
            <div className="text-3xl font-bold text-stone-900 dark:text-white">{health.revoked}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-4 shadow-sm">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
              <input
                type="text"
                placeholder="Search by token ID or team name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-3 py-2 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-stone-50 dark:bg-stone-900 focus:outline-none focus:ring-2 focus:ring-forest"
              />
            </div>

            <select
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-stone-50 dark:bg-stone-900 focus:outline-none focus:ring-2 focus:ring-forest"
            >
              <option value="all">All Teams</option>
              {teams.map((team) => (
                <option key={team.node_id} value={team.node_id}>{team.name}</option>
              ))}
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as TokenStatus | 'all')}
              className="px-3 py-2 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-stone-50 dark:bg-stone-900 focus:outline-none focus:ring-2 focus:ring-forest"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="expiring">Expiring</option>
              <option value="unused">Unused</option>
              <option value="revoked">Revoked</option>
            </select>

            <button
              onClick={loadTokens}
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700 disabled:opacity-50"
            >
              <RefreshCcw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} /> Refresh
            </button>
          </div>
        </div>

        {/* Bulk Actions */}
        {selectedTokens.size > 0 && (
          <div className="bg-forest-light/10 dark:bg-forest/20 border border-forest-light dark:border-forest/40 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-forest-dark dark:text-forest-light">
                {selectedTokens.size} token{selectedTokens.size > 1 ? 's' : ''} selected
              </span>
              <div className="flex gap-2">
                <button className="px-3 py-1.5 text-sm font-medium text-clay-dark bg-clay-light/15 dark:bg-clay/20 rounded-lg hover:bg-clay-light/20">
                  Revoke Selected
                </button>
                <button className="px-3 py-1.5 text-sm font-medium text-stone-700 bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200">
                  Export to CSV
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Token List Table */}
        <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-stone-50 dark:bg-stone-700 border-b border-stone-200 dark:border-stone-600">
                <tr>
                  <th className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedTokens.size === filteredTokens.length && filteredTokens.length > 0}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedTokens(new Set(filteredTokens.map((t) => t.token_id)));
                        } else {
                          setSelectedTokens(new Set());
                        }
                      }}
                      className="rounded border-stone-300 text-[#3D7B5F] focus:ring-forest"
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase tracking-wider">Token ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase tracking-wider">Team</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase tracking-wider">Issued</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase tracking-wider">Expires</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase tracking-wider">Last Used</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase tracking-wider">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200 dark:divide-stone-700">
                {filteredTokens.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-sm text-stone-500">
                      No tokens found. {statusFilter !== 'all' || teamFilter !== 'all' || searchQuery ? 'Try adjusting your filters.' : 'Issue your first token to get started.'}
                    </td>
                  </tr>
                ) : (
                  filteredTokens.map((token) => (
                    <tr key={token.token_id} className="hover:bg-stone-50 dark:hover:bg-stone-800/50">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selectedTokens.has(token.token_id)}
                          onChange={(e) => {
                            const newSelected = new Set(selectedTokens);
                            if (e.target.checked) {
                              newSelected.add(token.token_id);
                            } else {
                              newSelected.delete(token.token_id);
                            }
                            setSelectedTokens(newSelected);
                          }}
                          className="rounded border-stone-300 text-[#3D7B5F] focus:ring-forest"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => {
                            setSelectedToken(token);
                            setTokenDetailsModalOpen(true);
                          }}
                          className="font-mono text-sm text-[#3D7B5F] hover:text-[#2D5B47] hover:underline"
                        >
                          {token.token_id}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-sm text-stone-900 dark:text-stone-100">{token.team_name || token.team_node_id}</td>
                      <td className="px-4 py-3 text-sm text-stone-500">{formatDate(token.issued_at)}</td>
                      <td className="px-4 py-3 text-sm text-stone-500">{token.expires_at ? formatDate(token.expires_at) : 'Never'}</td>
                      <td className="px-4 py-3 text-sm text-stone-500">{formatRelativeTime(token.last_used_at)}</td>
                      <td className="px-4 py-3">{getStatusBadge(token.status)}</td>
                      <td className="px-4 py-3">
                        <button className="p-1 hover:bg-stone-100 dark:hover:bg-stone-700 rounded">
                          <MoreVertical className="w-4 h-4 text-stone-500" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Issue Token Modal */}
        {issueModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setIssueModalOpen(false)}>
            <div className="bg-white dark:bg-stone-800 rounded-xl shadow-xl max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between p-6 border-b border-stone-200 dark:border-stone-700">
                <h2 className="text-lg font-semibold text-stone-900 dark:text-white">Issue New Token</h2>
                <button onClick={() => setIssueModalOpen(false)} className="text-stone-400 hover:text-stone-600">✕</button>
              </div>

              <div className="p-6 space-y-4">
                {issueStep === 1 && (
                  <>
                    <div className="text-sm text-stone-600 dark:text-stone-400 mb-4">Step 1 of 3: Select Team</div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">Team</label>
                      <select
                        value={issueTeamId}
                        onChange={(e) => setIssueTeamId(e.target.value)}
                        className="w-full px-3 py-2 text-sm rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 focus:outline-none focus:ring-2 focus:ring-forest"
                      >
                        <option value="">Select team...</option>
                        {teams.map((team) => (
                          <option key={team.node_id} value={team.node_id}>{team.name}</option>
                        ))}
                      </select>
                    </div>
                  </>
                )}

                {issueStep === 2 && (
                  <>
                    <div className="text-sm text-stone-600 dark:text-stone-400 mb-4">Step 2 of 3: Set Expiration</div>
                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-3">Token expiration:</label>
                      {[30, 60, 90, 180, 365, null].map((days) => (
                        <label key={days || 'never'} className="flex items-center gap-3 p-3 border border-stone-200 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 cursor-pointer">
                          <input
                            type="radio"
                            checked={issueExpiryDays === days}
                            onChange={() => setIssueExpiryDays(days as number)}
                            className="text-[#3D7B5F] focus:ring-forest"
                          />
                          <span className="text-sm text-stone-900 dark:text-stone-100">
                            {days ? `${days} days${days === 90 ? ' (recommended)' : ''}` : 'Never expire (not recommended)'}
                          </span>
                        </label>
                      ))}
                    </div>
                    {issueExpiryDays && (
                      <p className="text-xs text-stone-500 mt-2">
                        Expires on: {new Date(Date.now() + issueExpiryDays * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                      </p>
                    )}
                  </>
                )}

                {issueStep === 3 && !issuedTokenSecret && (
                  <>
                    <div className="text-sm text-stone-600 dark:text-stone-400 mb-4">Step 3 of 3: Review</div>
                    <div className="bg-stone-50 dark:bg-stone-700 rounded-lg p-4 space-y-2">
                      <div className="text-sm"><span className="font-medium">Team:</span> {teams.find(t => t.node_id === issueTeamId)?.name || issueTeamId}</div>
                      <div className="text-sm"><span className="font-medium">Expires:</span> {issueExpiryDays ? `${issueExpiryDays} days` : 'Never'}</div>
                    </div>
                  </>
                )}

                {issuedTokenSecret && (
                  <>
                    <div className="text-sm text-stone-600 dark:text-stone-400 mb-4">Step 3 of 3: Copy Token</div>
                    <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-900/40 rounded-lg p-4">
                      <div className="flex items-start gap-2 text-yellow-900 dark:text-yellow-100 text-sm mb-3">
                        <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                        <div>
                          <strong>This token will only be shown once!</strong><br />
                          Save it securely.
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <code className="flex-1 bg-white dark:bg-stone-800 border border-yellow-200 dark:border-yellow-900/50 rounded p-3 text-xs font-mono break-all">
                          {issuedTokenSecret}
                        </code>
                        <button
                          onClick={() => navigator.clipboard.writeText(issuedTokenSecret)}
                          className="flex items-center gap-2 px-3 py-2 text-sm font-medium bg-white dark:bg-stone-800 border border-yellow-200 dark:border-yellow-900/50 rounded-lg hover:bg-yellow-50"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <label className="flex items-center gap-2 mt-4">
                      <input
                        type="checkbox"
                        checked={tokenSavedConfirmed}
                        onChange={(e) => setTokenSavedConfirmed(e.target.checked)}
                        className="rounded border-stone-300 text-[#3D7B5F] focus:ring-forest"
                      />
                      <span className="text-sm text-stone-700 dark:text-stone-300">I have saved this token securely</span>
                    </label>
                  </>
                )}
              </div>

              <div className="flex justify-end gap-2 p-6 border-t border-stone-200 dark:border-stone-700">
                {issueStep > 1 && !issuedTokenSecret && (
                  <button
                    onClick={() => setIssueStep(issueStep - 1)}
                    className="px-4 py-2 text-sm font-medium text-stone-700 bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200"
                  >
                    ← Back
                  </button>
                )}
                {!issuedTokenSecret ? (
                  <button
                    onClick={handleIssueToken}
                    disabled={issueStep === 1 && !issueTeamId}
                    className="px-4 py-2 text-sm font-medium text-white bg-forest rounded-lg hover:bg-forest-dark disabled:opacity-50"
                  >
                    {issueStep === 3 ? 'Issue Token' : 'Next →'}
                  </button>
                ) : (
                  <button
                    onClick={() => setIssueModalOpen(false)}
                    disabled={!tokenSavedConfirmed}
                    className="px-4 py-2 text-sm font-medium text-white bg-forest rounded-lg hover:bg-forest-dark disabled:opacity-50"
                  >
                    Done
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Token Details Modal */}
        {tokenDetailsModalOpen && selectedToken && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setTokenDetailsModalOpen(false)}>
            <div className="bg-white dark:bg-stone-800 rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between p-6 border-b border-stone-200 dark:border-stone-700">
                <h2 className="text-lg font-semibold text-stone-900 dark:text-white">Token Details: {selectedToken.token_id}</h2>
                <button onClick={() => setTokenDetailsModalOpen(false)} className="text-stone-400 hover:text-stone-600">✕</button>
              </div>

              <div className="p-6 space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-stone-900 dark:text-white mb-3">📋 Basic Information</h3>
                  <div className="bg-stone-50 dark:bg-stone-700 rounded-lg p-4 space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-stone-600 dark:text-stone-400">Token ID:</span><span className="font-mono">{selectedToken.token_id}</span></div>
                    <div className="flex justify-between"><span className="text-stone-600 dark:text-stone-400">Team:</span><span>{selectedToken.team_name || selectedToken.team_node_id}</span></div>
                    <div className="flex justify-between"><span className="text-stone-600 dark:text-stone-400">Issued By:</span><span>{selectedToken.issued_by}</span></div>
                    <div className="flex justify-between"><span className="text-stone-600 dark:text-stone-400">Issued Date:</span><span>{formatDate(selectedToken.issued_at)}</span></div>
                    <div className="flex justify-between"><span className="text-stone-600 dark:text-stone-400">Expires Date:</span><span>{selectedToken.expires_at ? formatDate(selectedToken.expires_at) : 'Never'}</span></div>
                    <div className="flex justify-between"><span className="text-stone-600 dark:text-stone-400">Status:</span><span>{getStatusBadge(selectedToken.status)}</span></div>
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-stone-900 dark:text-white mb-3">📊 Usage Statistics</h3>
                  <div className="bg-stone-50 dark:bg-stone-700 rounded-lg p-4 space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-stone-600 dark:text-stone-400">Total Requests:</span><span className="font-semibold">{selectedToken.total_requests?.toLocaleString() || 0}</span></div>
                    <div className="flex justify-between"><span className="text-stone-600 dark:text-stone-400">Last Used:</span><span>{formatRelativeTime(selectedToken.last_used_at)}</span></div>
                    <div className="flex justify-between"><span className="text-stone-600 dark:text-stone-400">First Used:</span><span>{formatDate(selectedToken.issued_at)}</span></div>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button className="px-4 py-2 text-sm font-medium text-stone-700 bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200">
                    View Full Audit Log
                  </button>
                  {!selectedToken.revoked_at && (
                    <>
                      <button className="px-4 py-2 text-sm font-medium text-[#3D7B5F] bg-forest-light/15 dark:bg-forest/20 rounded-lg hover:bg-forest-light/20">
                        Extend Expiry
                      </button>
                      <button
                        onClick={() => {
                          setTokenDetailsModalOpen(false);
                          setRevokeModalOpen(true);
                        }}
                        className="px-4 py-2 text-sm font-medium text-clay-dark bg-clay-light/15 dark:bg-clay/20 rounded-lg hover:bg-clay-light/20"
                      >
                        Revoke Token
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </RequireRole>
  );
}
