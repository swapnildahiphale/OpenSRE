'use client';

import { useEffect, useState, useCallback } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { apiFetch } from '@/lib/apiClient';
import { 
  Shield, 
  Save, 
  TestTube, 
  Eye, 
  EyeOff,
  CheckCircle,
  XCircle,
  Loader2,
  Info,
  Chrome,
  Building2,
  Lock
} from 'lucide-react';

interface SSOConfig {
  org_id: string;
  enabled: boolean;
  provider_type: string;
  provider_name: string | null;
  issuer: string | null;
  client_id: string | null;
  has_client_secret: boolean;
  scopes: string | null;
  tenant_id: string | null;
  email_claim: string | null;
  name_claim: string | null;
  groups_claim: string | null;
  admin_group: string | null;
  allowed_domains: string | null;
  updated_at: string | null;
  updated_by: string | null;
}

const PROVIDER_PRESETS: Record<string, { name: string; icon: any; color: string; issuer?: string; scopes?: string }> = {
  google: {
    name: 'Google Workspace',
    icon: Chrome,
    color: 'text-stone-500',
    issuer: 'https://accounts.google.com',
    scopes: 'openid email profile',
  },
  azure: {
    name: 'Microsoft Entra ID',
    icon: Building2,
    color: 'text-stone-500',
    scopes: 'openid email profile',
  },
  okta: {
    name: 'Okta',
    icon: Lock,
    color: 'text-stone-500',
    scopes: 'openid email profile',
  },
  oidc: {
    name: 'Custom OIDC',
    icon: Shield,
    color: 'text-stone-500',
    scopes: 'openid email profile',
  },
};

export default function SSOSettingsPage() {
  const { identity, loading: identityLoading } = useIdentity();
  const [config, setConfig] = useState<SSOConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  
  // Form state
  const [enabled, setEnabled] = useState(false);
  const [providerType, setProviderType] = useState('oidc');
  const [providerName, setProviderName] = useState('');
  const [issuer, setIssuer] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [scopes, setScopes] = useState('openid email profile');
  const [tenantId, setTenantId] = useState('');
  const [adminGroup, setAdminGroup] = useState('');
  const [allowedDomains, setAllowedDomains] = useState('');

  const orgId = identity?.org_id || 'org1';
  const isAdmin = identity?.role === 'admin';

  const loadConfig = useCallback(async () => {
    if (!isAdmin) return;
    setLoading(true);
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/sso-config`);
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
        // Populate form
        setEnabled(data.enabled || false);
        setProviderType(data.provider_type || 'oidc');
        setProviderName(data.provider_name || '');
        setIssuer(data.issuer || '');
        setClientId(data.client_id || '');
        setScopes(data.scopes || 'openid email profile');
        setTenantId(data.tenant_id || '');
        setAdminGroup(data.admin_group || '');
        setAllowedDomains(data.allowed_domains || '');
      }
    } catch (e) {
      console.error('Failed to load SSO config', e);
    } finally {
      setLoading(false);
    }
  }, [orgId, isAdmin]);

  useEffect(() => {
    if (isAdmin) {
      loadConfig();
    }
  }, [isAdmin, loadConfig]);

  const handleProviderChange = (type: string) => {
    setProviderType(type);
    const preset = PROVIDER_PRESETS[type];
    if (preset) {
      setProviderName(preset.name);
      if (preset.issuer) setIssuer(preset.issuer);
      if (preset.scopes) setScopes(preset.scopes);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setTestResult(null);
    try {
      const body: any = {
        enabled,
        provider_type: providerType,
        provider_name: providerName || PROVIDER_PRESETS[providerType]?.name,
        issuer,
        client_id: clientId,
        scopes,
        admin_group: adminGroup || null,
        allowed_domains: allowedDomains || null,
      };
      
      if (providerType === 'azure') {
        body.tenant_id = tenantId;
      }
      
      // Only send secret if changed
      if (clientSecret) {
        body.client_secret = clientSecret;
      }

      const res = await apiFetch(`/api/admin/orgs/${orgId}/sso-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        const data = await res.json();
        setConfig(data);
        setClientSecret(''); // Clear secret after save
        setTestResult({ success: true, message: 'SSO configuration saved!' });
      } else {
        const err = await res.json();
        setTestResult({ success: false, message: err.detail || 'Failed to save' });
      }
    } catch (e: any) {
      setTestResult({ success: false, message: e?.message || 'Failed to save' });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/sso-config/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issuer }),
      });

      const data = await res.json();
      setTestResult({
        success: data.success,
        message: data.message,
      });
    } catch (e: any) {
      setTestResult({ success: false, message: e?.message || 'Test failed' });
    } finally {
      setTesting(false);
    }
  };

  if (identityLoading || loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-stone-400" />
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
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-white flex items-center gap-3">
          <Shield className="w-7 h-7 text-stone-500" />
          Single Sign-On
        </h1>
        <p className="text-sm text-stone-500 mt-2">
          Configure SSO to allow your organization to sign in with your identity provider.
        </p>
      </div>

      {/* Enable Toggle */}
      <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-stone-900 dark:text-white">Enable SSO</h2>
            <p className="text-sm text-stone-500 mt-1">
              When enabled, users can sign in with your identity provider.
            </p>
          </div>
          <button
            onClick={() => setEnabled(!enabled)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              enabled ? 'bg-[#3D7B5F]' : 'bg-stone-300 dark:bg-stone-600'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                enabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Provider Selection */}
      <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-stone-900 dark:text-white mb-4">Identity Provider</h2>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {Object.entries(PROVIDER_PRESETS).map(([key, preset]) => {
            const Icon = preset.icon;
            const isSelected = providerType === key;
            return (
              <button
                key={key}
                onClick={() => handleProviderChange(key)}
                className={`p-4 rounded-xl border-2 transition-all ${
                  isSelected
                    ? 'border-forest bg-forest-light/10 dark:bg-forest/20'
                    : 'border-stone-200 dark:border-stone-600 hover:border-stone-300 dark:hover:border-stone-600'
                }`}
              >
                <Icon className={`w-6 h-6 mx-auto mb-2 ${preset.color}`} />
                <div className="text-xs font-medium text-center text-stone-900 dark:text-white">
                  {preset.name}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Configuration Form */}
      <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-6 mb-6 space-y-4">
        <h2 className="text-lg font-semibold text-stone-900 dark:text-white mb-4">Configuration</h2>

        {/* Azure-specific: Tenant ID */}
        {providerType === 'azure' && (
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
              Tenant ID <span className="text-clay">*</span>
            </label>
            <input
              type="text"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              placeholder="your-tenant-id or common"
              className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white"
            />
            <p className="text-xs text-stone-500 mt-1">
              Find this in Azure Portal → Entra ID → Overview
            </p>
          </div>
        )}

        {/* Generic OIDC: Issuer URL */}
        {(providerType === 'oidc' || providerType === 'okta') && (
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
              Issuer URL <span className="text-clay">*</span>
            </label>
            <input
              type="url"
              value={issuer}
              onChange={(e) => setIssuer(e.target.value)}
              placeholder="https://your-idp.com"
              className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white"
            />
            <p className="text-xs text-stone-500 mt-1">
              The OIDC issuer URL (must have /.well-known/openid-configuration)
            </p>
          </div>
        )}

        {/* Client ID */}
        <div>
          <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
            Client ID <span className="text-clay">*</span>
          </label>
          <input
            type="text"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Your OAuth client ID"
            className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white"
          />
        </div>

        {/* Client Secret */}
        <div>
          <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
            Client Secret <span className="text-clay">*</span>
          </label>
          <div className="relative">
            <input
              type={showSecret ? 'text' : 'password'}
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder={config?.has_client_secret ? '••••••••••••••••' : 'Your OAuth client secret'}
              className="w-full px-3 py-2 pr-10 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white"
            />
            <button
              type="button"
              onClick={() => setShowSecret(!showSecret)}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600"
            >
              {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {config?.has_client_secret && (
            <p className="text-xs text-stone-500 mt-1">
              Leave empty to keep existing secret, or enter new value to update
            </p>
          )}
        </div>

        {/* Admin Group */}
        <div>
          <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
            Admin Group (optional)
          </label>
          <input
            type="text"
            value={adminGroup}
            onChange={(e) => setAdminGroup(e.target.value)}
            placeholder="e.g., opensre-admins"
            className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white"
          />
          <p className="text-xs text-stone-500 mt-1">
            Users in this group will get admin role
          </p>
        </div>

        {/* Allowed Domains */}
        <div>
          <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
            Allowed Email Domains (optional)
          </label>
          <input
            type="text"
            value={allowedDomains}
            onChange={(e) => setAllowedDomains(e.target.value)}
            placeholder="e.g., company.com,subsidiary.com"
            className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 text-stone-900 dark:text-white"
          />
          <p className="text-xs text-stone-500 mt-1">
            Comma-separated list of allowed email domains
          </p>
        </div>
      </div>

      {/* Test Result */}
      {testResult && (
        <div className={`mb-6 p-4 rounded-xl flex items-start gap-3 ${
          testResult.success
            ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
            : 'bg-clay-light/10 dark:bg-clay/20 border border-red-200 dark:border-red-800'
        }`}>
          {testResult.success ? (
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
          ) : (
            <XCircle className="w-5 h-5 text-clay flex-shrink-0 mt-0.5" />
          )}
          <span className={`text-sm ${testResult.success ? 'text-green-700 dark:text-green-400' : 'text-clay-dark dark:text-clay-light'}`}>
            {testResult.message}
          </span>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button
          onClick={handleTest}
          disabled={testing || !issuer}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700 disabled:opacity-50"
        >
          <TestTube className={`w-4 h-4 ${testing ? 'animate-pulse' : ''}`} />
          {testing ? 'Testing...' : 'Test Connection'}
        </button>

        <button
          onClick={handleSave}
          disabled={saving || !clientId}
          className="flex items-center gap-2 px-6 py-2 bg-forest text-white rounded-lg hover:bg-forest-dark disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {saving ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>

      {/* Info */}
      <div className="mt-8 p-4 bg-stone-50 dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-stone-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm text-stone-800 dark:text-stone-200 font-medium">
              After enabling SSO
            </p>
            <p className="text-sm text-stone-600 dark:text-stone-300 mt-1">
              Your organization members will see a "Sign in with {PROVIDER_PRESETS[providerType]?.name}" button on the login page.
              Token-based login will still work for service accounts and API access.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

