'use client';

import { useState, useEffect, useCallback } from 'react';
import { useIdentity } from '@/lib/useIdentity';

interface Remediation {
  id: string;
  action_type: string;
  target: string;
  reason: string;
  parameters: Record<string, unknown>;
  urgency: 'low' | 'medium' | 'high' | 'critical';
  rollback_action?: string;
  status: 'pending' | 'approved' | 'rejected' | 'executed' | 'failed';
  proposed_at: string;
  proposed_by?: string;
  reviewed_at?: string;
  reviewed_by?: string;
  review_comment?: string;
  executed_at?: string;
  execution_result?: Record<string, unknown>;
  execution_error?: string;
}

const urgencyColors: Record<string, string> = {
  low: 'bg-stone-100 text-stone-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-orange-100 text-orange-800',
  critical: 'bg-clay-light/15 text-red-800 animate-pulse',
};

const statusColors: Record<string, string> = {
  pending: 'bg-forest-light/15 text-forest-dark',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-stone-100 text-stone-800',
  executed: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-clay-light/15 text-red-800',
};

const actionIcons: Record<string, string> = {
  restart_pod: '🔄',
  restart_deployment: '♻️',
  scale_deployment: '📈',
  rollback_deployment: '⏪',
  delete_pod: '🗑️',
  drain_node: '🚧',
  default: '⚡',
};

export default function RemediationsPage() {
  const { identity, loading: authLoading } = useIdentity();
  const [remediations, setRemediations] = useState<Remediation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'pending' | 'executed'>('pending');
  const [selectedRemediation, setSelectedRemediation] = useState<Remediation | null>(null);
  const [reviewComment, setReviewComment] = useState('');
  const [reviewing, setReviewing] = useState(false);

  const fetchRemediations = useCallback(async () => {
    if (!identity?.org_id) return;
    
    try {
      const statusParam = filter === 'all' ? '' : `?status=${filter}`;
      const res = await fetch(`/api/admin/orgs/${identity.org_id}/remediations${statusParam}`);
      if (res.ok) {
        const data = await res.json();
        setRemediations(data);
      }
    } catch (error) {
      console.error('Failed to fetch remediations:', error);
    } finally {
      setLoading(false);
    }
  }, [identity?.org_id, filter]);

  useEffect(() => {
    fetchRemediations();
    
    // Poll for updates every 10 seconds (important for real-time approval)
    const interval = setInterval(fetchRemediations, 10000);
    return () => clearInterval(interval);
  }, [fetchRemediations]);

  const handleReview = async (action: 'approve' | 'reject') => {
    if (!selectedRemediation || !identity?.org_id) return;
    
    setReviewing(true);
    try {
      const res = await fetch(
        `/api/admin/orgs/${identity.org_id}/remediations/${selectedRemediation.id}/review`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, comment: reviewComment }),
        }
      );
      
      if (res.ok) {
        setSelectedRemediation(null);
        setReviewComment('');
        fetchRemediations();
      } else {
        alert('Failed to submit review');
      }
    } catch (error) {
      console.error('Review failed:', error);
    } finally {
      setReviewing(false);
    }
  };

  const handleRollback = async (remediation: Remediation) => {
    if (!identity?.org_id) return;
    
    if (!confirm(`Are you sure you want to rollback "${remediation.action_type}" on ${remediation.target}?`)) {
      return;
    }
    
    try {
      const res = await fetch(
        `/api/admin/orgs/${identity.org_id}/remediations/${remediation.id}/rollback`,
        { method: 'POST' }
      );
      
      if (res.ok) {
        fetchRemediations();
      } else {
        alert('Failed to initiate rollback');
      }
    } catch (error) {
      console.error('Rollback failed:', error);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-stone-200 rounded w-1/3"></div>
          <div className="h-64 bg-stone-200 rounded"></div>
        </div>
      </div>
    );
  }

  const pendingCount = remediations.filter(r => r.status === 'pending').length;
  const criticalCount = remediations.filter(r => r.urgency === 'critical' && r.status === 'pending').length;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-stone-900">Remediation Queue</h1>
          <p className="text-stone-600 mt-1">
            Review and approve auto-remediation actions proposed by agents
          </p>
        </div>
        
        {criticalCount > 0 && (
          <div className="bg-red-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 animate-pulse">
            <span className="text-xl">🚨</span>
            <span className="font-semibold">{criticalCount} Critical</span>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-forest-light/10 rounded-lg p-4">
          <div className="text-2xl font-bold text-forest">{pendingCount}</div>
          <div className="text-sm text-forest-dark">Pending Approval</div>
        </div>
        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-2xl font-bold text-green-600">
            {remediations.filter(r => r.status === 'executed').length}
          </div>
          <div className="text-sm text-green-800">Executed</div>
        </div>
        <div className="bg-stone-50 rounded-lg p-4">
          <div className="text-2xl font-bold text-stone-600">
            {remediations.filter(r => r.status === 'rejected').length}
          </div>
          <div className="text-sm text-stone-800">Rejected</div>
        </div>
        <div className="bg-clay-light/10 rounded-lg p-4">
          <div className="text-2xl font-bold text-clay">
            {remediations.filter(r => r.status === 'failed').length}
          </div>
          <div className="text-sm text-red-800">Failed</div>
        </div>
      </div>

      {/* Filter */}
      <div className="mb-6 flex gap-2">
        {(['pending', 'all', 'executed'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              filter === f
                ? 'bg-stone-900 text-white'
                : 'bg-stone-100 text-stone-700 hover:bg-stone-200'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Remediation List */}
      <div className="space-y-4">
        {remediations.length === 0 ? (
          <div className="text-center py-12 bg-stone-50 rounded-lg">
            <div className="text-4xl mb-4">✅</div>
            <div className="text-stone-600">No remediations {filter !== 'all' ? `with status "${filter}"` : ''}</div>
          </div>
        ) : (
          remediations.map((rem) => (
            <div
              key={rem.id}
              className={`bg-white rounded-lg border shadow-sm p-6 ${
                rem.urgency === 'critical' && rem.status === 'pending'
                  ? 'border-red-300 ring-2 ring-red-100'
                  : 'border-stone-200'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl">
                      {actionIcons[rem.action_type] || actionIcons.default}
                    </span>
                    <h3 className="text-lg font-semibold text-stone-900">
                      {rem.action_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </h3>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${urgencyColors[rem.urgency]}`}>
                      {rem.urgency.toUpperCase()}
                    </span>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[rem.status]}`}>
                      {rem.status}
                    </span>
                  </div>
                  
                  <div className="text-stone-600 mb-2">
                    <span className="font-mono bg-stone-100 px-2 py-1 rounded">
                      {rem.target}
                    </span>
                  </div>
                  
                  <p className="text-stone-700 mb-3">{rem.reason}</p>
                  
                  {rem.parameters && Object.keys(rem.parameters).length > 0 && (
                    <div className="text-sm text-stone-500 mb-2">
                      <span className="font-medium">Parameters:</span>{' '}
                      <code className="bg-stone-100 px-2 py-1 rounded">
                        {JSON.stringify(rem.parameters)}
                      </code>
                    </div>
                  )}
                  
                  <div className="text-sm text-stone-500">
                    Proposed {new Date(rem.proposed_at).toLocaleString()}
                    {rem.proposed_by && ` by ${rem.proposed_by}`}
                  </div>
                  
                  {rem.execution_error && (
                    <div className="mt-3 p-3 bg-clay-light/10 rounded text-clay-dark text-sm">
                      <span className="font-medium">Error:</span> {rem.execution_error}
                    </div>
                  )}
                  
                  {rem.execution_result && (
                    <div className="mt-3 p-3 bg-green-50 rounded text-green-700 text-sm">
                      <span className="font-medium">Result:</span>{' '}
                      <code>{JSON.stringify(rem.execution_result)}</code>
                    </div>
                  )}
                </div>
                
                <div className="flex flex-col gap-2 ml-4">
                  {rem.status === 'pending' && (
                    <>
                      <button
                        onClick={() => setSelectedRemediation(rem)}
                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium"
                      >
                        Review
                      </button>
                    </>
                  )}
                  
                  {rem.status === 'executed' && rem.rollback_action && (
                    <button
                      onClick={() => handleRollback(rem)}
                      className="px-4 py-2 bg-forest text-white rounded-lg hover:bg-forest-dark font-medium"
                    >
                      Rollback
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Review Modal */}
      {selectedRemediation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-bold text-stone-900">
                Review Remediation
              </h2>
            </div>
            
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">
                  Action
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-2xl">
                    {actionIcons[selectedRemediation.action_type] || actionIcons.default}
                  </span>
                  <span className="font-semibold">
                    {selectedRemediation.action_type.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">
                  Target
                </label>
                <code className="block bg-stone-100 px-3 py-2 rounded font-mono">
                  {selectedRemediation.target}
                </code>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">
                  Reason
                </label>
                <p className="text-stone-700 bg-stone-50 p-3 rounded">
                  {selectedRemediation.reason}
                </p>
              </div>
              
              {selectedRemediation.rollback_action && (
                <div>
                  <label className="block text-sm font-medium text-stone-700 mb-1">
                    Rollback Plan
                  </label>
                  <p className="text-stone-600 bg-yellow-50 p-3 rounded">
                    {selectedRemediation.rollback_action}
                  </p>
                </div>
              )}
              
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">
                  Comment (optional)
                </label>
                <textarea
                  value={reviewComment}
                  onChange={(e) => setReviewComment(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-forest focus:border-forest"
                  rows={3}
                  placeholder="Add a comment..."
                />
              </div>
            </div>
            
            <div className="p-6 border-t bg-stone-50 flex justify-end gap-3">
              <button
                onClick={() => {
                  setSelectedRemediation(null);
                  setReviewComment('');
                }}
                className="px-4 py-2 text-stone-700 bg-white border rounded-lg hover:bg-stone-50"
                disabled={reviewing}
              >
                Cancel
              </button>
              <button
                onClick={() => handleReview('reject')}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium"
                disabled={reviewing}
              >
                {reviewing ? 'Processing...' : 'Reject'}
              </button>
              <button
                onClick={() => handleReview('approve')}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium"
                disabled={reviewing}
              >
                {reviewing ? 'Processing...' : 'Approve & Execute'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

