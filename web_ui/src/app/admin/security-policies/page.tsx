'use client';

import { useEffect, useState, useCallback } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { apiFetch } from '@/lib/apiClient';
import { 
  Shield, 
  Key, 
  Save,
  AlertTriangle,
  RefreshCcw
} from 'lucide-react';

export default function SecurityPoliciesPage() {
  const { identity, loading: identityLoading } = useIdentity();
  const [policies, setPolicies] = useState<any>(null);
  const [policiesLoading, setPoliciesLoading] = useState(false);
  const [policiesSaving, setPoliciesSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const orgId = identity?.org_id || 'org1';
  const isAdmin = identity?.role === 'admin';

  // Load security policies
  const loadPolicies = useCallback(async () => {
    if (!isAdmin) return;
    setPoliciesLoading(true);
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/security-policies`);
      if (res.ok) {
        setPolicies(await res.json());
      }
    } catch (e) {
      console.error('Failed to load policies', e);
    } finally {
      setPoliciesLoading(false);
    }
  }, [orgId, isAdmin]);

  // Save security policies
  const savePolicies = async () => {
    if (!policies) return;
    setPoliciesSaving(true);
    setSaveSuccess(false);
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/security-policies`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(policies),
      });
      if (res.ok) {
        setPolicies(await res.json());
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (e) {
      alert('Failed to save policies');
    } finally {
      setPoliciesSaving(false);
    }
  };

  useEffect(() => {
    if (isAdmin) {
      loadPolicies();
    }
  }, [isAdmin, loadPolicies]);

  if (identityLoading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="animate-pulse text-stone-500">Loading...</div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="p-8">
        <div className="bg-clay-light/10 dark:bg-clay/20 border border-red-200 dark:border-red-800 rounded-xl p-6 text-center">
          <p className="text-clay dark:text-clay-light">Admin access required</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">Security Policies</h1>
          <p className="text-sm text-stone-500 mt-1">
            Organization-wide security settings that cannot be overridden by teams.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {saveSuccess && (
            <span className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1">
              <Shield className="w-4 h-4" /> Saved
            </span>
          )}
          <button
            onClick={loadPolicies}
            disabled={policiesLoading}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700"
          >
            <RefreshCcw className={`w-4 h-4 ${policiesLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={savePolicies}
            disabled={policiesSaving || !policies}
            className="flex items-center gap-2 px-4 py-2 bg-forest text-white rounded-lg hover:bg-forest-dark disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {policiesSaving ? 'Saving...' : 'Save Policies'}
          </button>
        </div>
      </div>

      {policiesLoading ? (
        <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-12 text-center">
          <div className="animate-pulse text-stone-500">Loading policies...</div>
        </div>
      ) : policies ? (
        <div className="space-y-6">
          {/* Token Policies */}
          <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-6 shadow-sm">
            <h3 className="font-semibold text-stone-900 dark:text-white mb-4 flex items-center gap-2">
              <Key className="w-5 h-5 text-stone-500" /> Token Policies
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">
                  Token Expiry (days)
                </label>
                <input
                  type="number"
                  value={policies.token_expiry_days || ''}
                  onChange={(e) => setPolicies({ ...policies, token_expiry_days: e.target.value ? parseInt(e.target.value) : null })}
                  placeholder="Never"
                  className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white"
                />
                <p className="text-xs text-stone-500 mt-1">Leave empty for no expiration</p>
              </div>
              <div>
                <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">
                  Warn Before (days)
                </label>
                <input
                  type="number"
                  value={policies.token_warn_before_days || ''}
                  onChange={(e) => setPolicies({ ...policies, token_warn_before_days: e.target.value ? parseInt(e.target.value) : null })}
                  placeholder="7"
                  className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white"
                />
                <p className="text-xs text-stone-500 mt-1">Days before expiry to warn</p>
              </div>
              <div>
                <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">
                  Revoke Inactive (days)
                </label>
                <input
                  type="number"
                  value={policies.token_revoke_inactive_days || ''}
                  onChange={(e) => setPolicies({ ...policies, token_revoke_inactive_days: e.target.value ? parseInt(e.target.value) : null })}
                  placeholder="Never"
                  className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white"
                />
                <p className="text-xs text-stone-500 mt-1">Auto-revoke after inactivity</p>
              </div>
            </div>
          </div>

          {/* Guardrails */}
          <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-6 shadow-sm">
            <h3 className="font-semibold text-stone-900 dark:text-white mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-stone-500" /> Configuration Guardrails
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">
                  Locked Settings (teams cannot change)
                </label>
                <textarea
                  value={JSON.stringify(policies.locked_settings || [], null, 2)}
                  onChange={(e) => {
                    try {
                      setPolicies({ ...policies, locked_settings: JSON.parse(e.target.value) });
                    } catch {}
                  }}
                  rows={3}
                  placeholder='["model", "enabled_tools.aws"]'
                  className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 font-mono text-sm text-stone-900 dark:text-white"
                />
                <p className="text-xs text-stone-500 mt-1">JSON array of config paths that teams cannot override</p>
              </div>
              <div>
                <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">
                  Max Values (upper limits)
                </label>
                <textarea
                  value={JSON.stringify(policies.max_values || {}, null, 2)}
                  onChange={(e) => {
                    try {
                      setPolicies({ ...policies, max_values: JSON.parse(e.target.value) });
                    } catch {}
                  }}
                  rows={3}
                  placeholder='{"max_turns": 200, "timeout_seconds": 300}'
                  className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 font-mono text-sm text-stone-900 dark:text-white"
                />
                <p className="text-xs text-stone-500 mt-1">JSON object with maximum allowed values</p>
              </div>
            </div>
          </div>

          {/* Change Policies */}
          <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-6 shadow-sm">
            <h3 className="font-semibold text-stone-900 dark:text-white mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-stone-500" /> Change Policies
            </h3>
            <div className="space-y-4">
              <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors">
                <input
                  type="checkbox"
                  checked={policies.require_approval_for_prompts || false}
                  onChange={(e) => setPolicies({ ...policies, require_approval_for_prompts: e.target.checked })}
                  className="w-4 h-4 rounded border-stone-300 text-[#3D7B5F] focus:ring-forest"
                />
                <div>
                  <span className="text-sm font-medium text-stone-900 dark:text-white">Require approval for prompt changes</span>
                  <p className="text-xs text-stone-500">Custom agent prompts must be approved before taking effect</p>
                </div>
              </label>
              <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors">
                <input
                  type="checkbox"
                  checked={policies.require_approval_for_tools || false}
                  onChange={(e) => setPolicies({ ...policies, require_approval_for_tools: e.target.checked })}
                  className="w-4 h-4 rounded border-stone-300 text-[#3D7B5F] focus:ring-forest"
                />
                <div>
                  <span className="text-sm font-medium text-stone-900 dark:text-white">Require approval for tool enablement</span>
                  <p className="text-xs text-stone-500">New tool activations must be approved by an admin</p>
                </div>
              </label>
              <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors">
                <input
                  type="checkbox"
                  checked={policies.log_all_changes !== false}
                  onChange={(e) => setPolicies({ ...policies, log_all_changes: e.target.checked })}
                  className="w-4 h-4 rounded border-stone-300 text-[#3D7B5F] focus:ring-forest"
                />
                <div>
                  <span className="text-sm font-medium text-stone-900 dark:text-white">Log all configuration changes</span>
                  <p className="text-xs text-stone-500">Record all changes to the unified audit log</p>
                </div>
              </label>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-12 text-center">
          <p className="text-stone-500">Failed to load policies. Please try again.</p>
          <button
            onClick={loadPolicies}
            className="mt-4 px-4 py-2 bg-forest text-white rounded-lg hover:bg-forest-dark"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}

