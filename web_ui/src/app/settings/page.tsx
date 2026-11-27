'use client';

import { type Message } from '@/lib/i18n/locale';

import { LanguageSelect } from '@/components/LanguageSelect';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useIdentity } from '@/lib/useIdentity';
import { useOnboarding } from '@/lib/useOnboarding';
import { apiFetch } from '@/lib/apiClient';
import { HelpTip } from '@/components/onboarding/HelpTip';
import { QuickStartWizard } from '@/components/onboarding/QuickStartWizard';
import { TelemetryInfoModal } from '@/components/settings/TelemetryInfoModal';
import { ContinueOnboardingButton } from '@/components/onboarding/ContinueOnboardingButton';
import {
  Settings,
  Moon,
  Sun,
  RefreshCcw,
  Bot,
  ChevronRight,
  AlertTriangle,
  Shield,
  KeyRound,
  Activity,
  ExternalLink,
  Radio,
  Bell,
  Plus,
  X,
  Check,
  Zap,
  Clock,
  ToggleLeft,
  ToggleRight,
  Network,
  Loader2,
  Link2,
  BookOpen,
  RotateCcw,
  Route,
  MessageSquare,
  Github,
  Webhook,
  Tag,
  Server,
  Info,
  HelpCircle,
  LogOut
} from 'lucide-react';
import { PageHeader } from '@/components/ui-flow';
import { useLocale } from '@/lib/i18n/LocaleProvider';

// Tab type
type SettingsTab =
  | 'general'
  | 'routing'
  | 'notifications'
  | 'telemetry'
  | 'features'
  | 'advanced'
  | 'about';

// Feature configs
interface IngestorSourceConfig {
  slack: {
    enabled: boolean;
    channels: string[];  // Channel names like "#incidents", "#oncall"
  };
  confluence: {
    enabled: boolean;
    base_url: string;    // e.g., "https://company.atlassian.net"
    space_keys: string[]; // Space keys to include
  };
  gdocs: {
    enabled: boolean;
    folder_ids: string[]; // Optional folder IDs to filter
  };
  agent_traces: {
    enabled: boolean;
  };
}

interface PipelineConfig {
  enabled: boolean;
  schedule: string;
  ingestors: IngestorSourceConfig;
}

interface DependencyDiscoveryConfig {
  enabled: boolean;
  schedule: string;
  sources: {
    new_relic: boolean;
    cloudwatch: boolean;
    prometheus: boolean;
    datadog: boolean;
  };
}

interface CorrelationConfig {
  enabled: boolean;
  temporal_window_seconds: number;
  semantic_threshold: number;
}

// Routing configuration - determines which webhooks route to this team
interface RoutingConfig {
  slack_channel_ids: string[];
  github_repos: string[];
  pagerduty_service_ids: string[];
  incidentio_team_ids: string[];
  incidentio_alert_source_ids: string[];
  coralogix_team_names: string[];
  services: string[];
}

// Admin sub-pages (shown as links in sidebar for admins)
interface AdminLink {
  name: Message;
  href: string;
  icon: any;
  description: string;
}

const adminLinks: AdminLink[] = [
  { name: 'Security Policies', href: '/admin/security-policies', icon: Shield, description: 'Token policies and guardrails' },
  { name: 'SSO', href: '/admin/sso', icon: KeyRound, description: 'Single sign-on configuration' },
  { name: 'Audit Log', href: '/admin/audit', icon: Activity, description: 'View all activity logs' },
];

export default function SettingsPage() {
  const { t } = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { identity, loading: identityLoading } = useIdentity();
  const { resetOnboarding } = useOnboarding();

  // Tab state - synced with URL query param
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');

  // Sync tab state with URL query param (e.g., /settings?tab=routing)
  // Use searchParams.toString() as dependency for reliable updates
  const searchParamsString = searchParams.toString();
  useEffect(() => {
    const validTabs: SettingsTab[] = [
      'general',
      'routing',
      'notifications',
      'telemetry',
      'features',
      'advanced',
      'about',
    ];
    const urlTab = searchParams.get('tab') as SettingsTab | null;
    if (urlTab && validTabs.includes(urlTab)) {
      setActiveTab(urlTab);
    }
  }, [searchParamsString, searchParams]);

  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [showQuickStart, setShowQuickStart] = useState(false);
  const [quickStartInitialStep, setQuickStartInitialStep] = useState(1);

  // Telemetry opt-in/out
  const [telemetryEnabled, setTelemetryEnabled] = useState(true);
  const [telemetryLoading, setTelemetryLoading] = useState(false);
  const [showTelemetryInfo, setShowTelemetryInfo] = useState(false);

  const [aboutVersion, setAboutVersion] = useState<string | null>(null);
  const [aboutGitSha, setAboutGitSha] = useState<string | null>(null);
  const [aboutError, setAboutError] = useState(false);

  useEffect(() => {
    if (activeTab !== 'about') return;
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch('/api/version');
        if (!res.ok) {
          if (!cancelled) setAboutError(true);
          return;
        }
        const data = await res.json();
        if (!cancelled) {
          setAboutVersion(data.version ?? 'dev');
          setAboutGitSha(data.gitSha ?? null);
          setAboutError(false);
        }
      } catch {
        if (!cancelled) setAboutError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeTab]);

  // Output configuration (Delivery & Notifications)
  const [outputConfig, setOutputConfig] = useState<{
    default_destinations: Array<{
      type: string;
      channel_id?: string;
      channel_name?: string;
      repo?: string;
      config?: any;
    }>;
    trigger_overrides: { [key: string]: string };
  }>({ default_destinations: [], trigger_overrides: {} });
  const [outputConfigLoading, setOutputConfigLoading] = useState(false);
  const [showAddDestination, setShowAddDestination] = useState(false);
  const [newDestinationType, setNewDestinationType] = useState('slack');
  const [newDestinationConfig, setNewDestinationConfig] = useState({ channel_name: '', channel_id: '' });

  // Feature configs (AI Pipeline & Dependency Discovery)
  const [pipelineConfig, setPipelineConfig] = useState<PipelineConfig>({
    enabled: false,
    schedule: '0 2 * * *',
    ingestors: {
      slack: { enabled: true, channels: [] },
      confluence: { enabled: false, base_url: '', space_keys: [] },
      gdocs: { enabled: false, folder_ids: [] },
      agent_traces: { enabled: false },
    },
  });
  const [dependencyConfig, setDependencyConfig] = useState<DependencyDiscoveryConfig>({
    enabled: false,
    schedule: '0 */2 * * *',
    sources: {
      new_relic: true,
      cloudwatch: false,
      prometheus: false,
      datadog: false,
    },
  });
  const [correlationConfig, setCorrelationConfig] = useState<CorrelationConfig>({
    enabled: false,
    temporal_window_seconds: 300,
    semantic_threshold: 0.75,
  });
  const [featuresLoading, setFeaturesLoading] = useState(false);
  const [featuresSaving, setFeaturesSaving] = useState(false);
  const [syncingCronJobs, setSyncingCronJobs] = useState(false);

  // Routing configuration state
  const [routingConfig, setRoutingConfig] = useState<RoutingConfig>({
    slack_channel_ids: [],
    github_repos: [],
    pagerduty_service_ids: [],
    incidentio_team_ids: [],
    incidentio_alert_source_ids: [],
    coralogix_team_names: [],
    services: [],
  });
  const [routingLoading, setRoutingLoading] = useState(false);
  const [routingSaving, setRoutingSaving] = useState(false);
  // Track which routing field is being edited (for add input)
  const [editingRoutingField, setEditingRoutingField] = useState<keyof RoutingConfig | null>(null);
  const [newRoutingValue, setNewRoutingValue] = useState('');

  const isAdmin = identity?.role === 'admin';
  const canWrite = identity?.can_write ?? false;

  // Theme toggle
  useEffect(() => {
    const stored = localStorage.getItem('theme') || 'dark';
    setTheme(stored as 'dark' | 'light');
    if (stored === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  // Load telemetry settings on mount
  useEffect(() => {
    const loadTelemetry = async () => {
      try {
        const res = await apiFetch('/api/config/me/org-settings');
        const data = await res.json();
        setTelemetryEnabled(data.telemetry_enabled);
      } catch (e) {
        console.error('Failed to load telemetry settings', e);
      }
    };
    loadTelemetry();
  }, []);

  // Toggle telemetry
  const toggleTelemetry = async () => {
    setTelemetryLoading(true);
    try {
      const newValue = !telemetryEnabled;
      const res = await apiFetch('/api/config/me/org-settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telemetry_enabled: newValue }),
      });
      if (!res.ok) throw new Error('Failed to update');
      setTelemetryEnabled(newValue);
    } catch (e: any) {
      console.error('Failed to update telemetry', e);
      alert(t("Failed to update telemetry preference"));
    } finally {
      setTelemetryLoading(false);
    }
  };

  // Load output config on mount
  useEffect(() => {
    const loadOutputConfig = async () => {
      try {
        const res = await apiFetch('/api/v1/team/output-config');
        const data = await res.json();
        setOutputConfig(data);
      } catch (e) {
        console.error('Failed to load output config', e);
      }
    };
    loadOutputConfig();
  }, []);

  // Save output config
  const saveOutputConfig = async () => {
    setOutputConfigLoading(true);
    try {
      const res = await apiFetch('/api/v1/team/output-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(outputConfig),
      });
      if (!res.ok) throw new Error('Failed to update');
      const data = await res.json();
      setOutputConfig(data);
      alert(t("Output configuration saved successfully!"));
    } catch (e: any) {
      console.error('Failed to save output config', e);
      alert(t("Failed to save output configuration"));
    } finally {
      setOutputConfigLoading(false);
    }
  };

  // Add destination
  const addDestination = () => {
    const newDest: any = { type: newDestinationType };
    if (newDestinationType === 'slack') {
      newDest.channel_id = newDestinationConfig.channel_id;
      newDest.channel_name = newDestinationConfig.channel_name;
    }
    setOutputConfig({
      ...outputConfig,
      default_destinations: [...outputConfig.default_destinations, newDest],
    });
    setShowAddDestination(false);
    setNewDestinationConfig({ channel_name: '', channel_id: '' });
  };

  // Remove destination
  const removeDestination = (index: number) => {
    setOutputConfig({
      ...outputConfig,
      default_destinations: outputConfig.default_destinations.filter((_, i) => i !== index),
    });
  };

  // Sign out handler
  const signOut = async () => {
    try {
      // Call the logout API to clear the httpOnly session cookie
      await fetch('/api/session/logout', { method: 'POST' });
    } catch (e) {
      console.error('Logout API failed', e);
    }
    // Also clear any localStorage tokens
    localStorage.removeItem('opensre_token');
    // Force reload to clear React state and redirect to login
    window.location.href = '/';
  };

  // Load feature configs on mount
  useEffect(() => {
    const loadFeatureConfigs = async () => {
      setFeaturesLoading(true);
      try {
        const res = await apiFetch('/api/config/me');
        if (res.ok) {
          const data = await res.json();
          const config = data.effective_config || data;

          // Extract ai_pipeline config
          if (config.ai_pipeline) {
            const ingestors = config.ai_pipeline.ingestors || {};
            // Handle both old boolean format and new object format
            const parseIngestor = (key: string, defaultEnabled: boolean) => {
              const val = ingestors[key];
              if (typeof val === 'boolean') {
                // Legacy format - convert to new structure
                return { enabled: val, channels: [], base_url: '', space_keys: [], folder_ids: [] };
              }
              return val || { enabled: defaultEnabled };
            };

            setPipelineConfig({
              enabled: config.ai_pipeline.enabled ?? false,
              schedule: config.ai_pipeline.schedule ?? '0 2 * * *',
              ingestors: {
                slack: {
                  enabled: parseIngestor('slack', true).enabled ?? true,
                  channels: ingestors.slack?.channels || [],
                },
                confluence: {
                  enabled: parseIngestor('confluence', false).enabled ?? false,
                  base_url: ingestors.confluence?.base_url || '',
                  space_keys: ingestors.confluence?.space_keys || [],
                },
                gdocs: {
                  enabled: parseIngestor('gdocs', false).enabled ?? false,
                  folder_ids: ingestors.gdocs?.folder_ids || [],
                },
                agent_traces: {
                  enabled: parseIngestor('agent_traces', false).enabled ?? false,
                },
              },
            });
          }

          // Extract dependency_discovery config
          if (config.dependency_discovery) {
            setDependencyConfig({
              enabled: config.dependency_discovery.enabled ?? false,
              schedule: config.dependency_discovery.schedule ?? '0 */2 * * *',
              sources: {
                new_relic: config.dependency_discovery.sources?.new_relic ?? true,
                cloudwatch: config.dependency_discovery.sources?.cloudwatch ?? false,
                prometheus: config.dependency_discovery.sources?.prometheus ?? false,
                datadog: config.dependency_discovery.sources?.datadog ?? false,
              },
            });
          }

          // Extract correlation config
          if (config.correlation) {
            setCorrelationConfig({
              enabled: config.correlation.enabled ?? false,
              temporal_window_seconds: config.correlation.temporal_window_seconds ?? 300,
              semantic_threshold: config.correlation.semantic_threshold ?? 0.75,
            });
          }

          // Extract routing config
          if (config.routing) {
            setRoutingConfig({
              slack_channel_ids: config.routing.slack_channel_ids || [],
              github_repos: config.routing.github_repos || [],
              pagerduty_service_ids: config.routing.pagerduty_service_ids || [],
              incidentio_team_ids: config.routing.incidentio_team_ids || [],
              incidentio_alert_source_ids: config.routing.incidentio_alert_source_ids || [],
              coralogix_team_names: config.routing.coralogix_team_names || [],
              services: config.routing.services || [],
            });
          }
        }
      } catch (e) {
        console.error('Failed to load feature configs', e);
      } finally {
        setFeaturesLoading(false);
        setRoutingLoading(false);
      }
    };
    setRoutingLoading(true);
    loadFeatureConfigs();
  }, []);

  // Save feature configs
  const saveFeatureConfigs = async () => {
    setFeaturesSaving(true);
    try {
      const patch = {
        ai_pipeline: {
          enabled: pipelineConfig.enabled,
          schedule: pipelineConfig.schedule,
          ingestors: pipelineConfig.ingestors,
        },
        dependency_discovery: {
          enabled: dependencyConfig.enabled,
          schedule: dependencyConfig.schedule,
          sources: dependencyConfig.sources,
        },
        correlation: {
          enabled: correlationConfig.enabled,
          temporal_window_seconds: correlationConfig.temporal_window_seconds,
          semantic_threshold: correlationConfig.semantic_threshold,
        },
      };

      const res = await apiFetch('/api/config/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });

      if (!res.ok) throw new Error('Failed to save');
      alert(t("Feature configuration saved! Click \"Apply Changes\" to update scheduled jobs."));
    } catch (e: any) {
      console.error('Failed to save feature configs', e);
      alert(t("Failed to save feature configuration"));
    } finally {
      setFeaturesSaving(false);
    }
  };

  // Save routing config
  const saveRoutingConfig = async () => {
    setRoutingSaving(true);
    try {
      const patch = {
        routing: routingConfig,
      };

      const res = await apiFetch('/api/config/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });

      if (!res.ok) throw new Error('Failed to save');
      alert(t("Routing configuration saved successfully!"));
    } catch (e: any) {
      console.error('Failed to save routing config', e);
      alert(t("Failed to save routing configuration"));
    } finally {
      setRoutingSaving(false);
    }
  };

  // Add a routing identifier value
  const addRoutingValue = (field: keyof RoutingConfig) => {
    const trimmed = newRoutingValue.trim();
    if (!trimmed) return;
    if (routingConfig[field].includes(trimmed)) {
      alert(t("This value already exists"));
      return;
    }
    setRoutingConfig({
      ...routingConfig,
      [field]: [...routingConfig[field], trimmed],
    });
    setNewRoutingValue('');
    setEditingRoutingField(null);
  };

  // Remove a routing identifier value
  const removeRoutingValue = (field: keyof RoutingConfig, value: string) => {
    setRoutingConfig({
      ...routingConfig,
      [field]: routingConfig[field].filter((v) => v !== value),
    });
  };

  // Sync CronJobs with current config
  const syncCronJobs = async () => {
    setSyncingCronJobs(true);
    try {
      // Team endpoint uses token auth - no body needed
      const res = await apiFetch('/api/orchestrator/sync-cronjobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      const data = await res.json();
      if (data.ok) {
        alert(t("Scheduled jobs synced successfully!"));
      } else {
        alert(t('Sync failed: {message}', { message: data.message || t('Unknown error') }));
      }
    } catch (e: any) {
      console.error('Failed to sync cronjobs', e);
      alert(t("Failed to sync scheduled jobs"));
    } finally {
      setSyncingCronJobs(false);
    }
  };

  const tabs: { id: SettingsTab; name: Message; icon: any; adminOnly?: boolean }[] = [
    { id: 'general', name: 'General', icon: Settings },
    { id: 'routing', name: 'Webhook Routing', icon: Route },
    { id: 'notifications', name: 'Delivery & Notifications', icon: Bell },
    { id: 'telemetry', name: 'Telemetry', icon: Radio },
    { id: 'features', name: 'Advanced Features', icon: Zap },
    { id: 'advanced', name: 'Debug Tools', icon: Bot, adminOnly: true },
    { id: 'about', name: 'About', icon: Info },
  ];

  const filteredTabs = tabs.filter(t => !t.adminOnly || isAdmin);

  return (
    <div className="p-4 sm:p-8 max-w-6xl mx-auto">
      <PageHeader
        eyebrow={t("Team console")}
        title={t("Settings")}
        subtitle={
          isAdmin
            ? t('Manage preferences and run ad-hoc agents.')
            : t('Manage your preferences.')
        }
      />

      <div className="flex flex-col gap-6 mt-8 lg:flex-row lg:gap-8">
        {/* Sidebar */}
        <div className="w-full shrink-0 lg:w-64">
          <nav className="space-y-1">
            {filteredTabs.map((tab) => (
            <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-sm font-medium rounded-full transition-colors ${
                  activeTab === tab.id
                    ? 'bg-emerald-100/55 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400'
                    : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <tab.icon className="w-4 h-4 shrink-0" />
                <span className="flex-1 text-left whitespace-nowrap">{t(tab.name)}</span>
                <ChevronRight className={`w-4 h-4 shrink-0 transition-transform ${activeTab === tab.id ? 'rotate-90' : ''}`} />
            </button>
          ))}
          
          {/* Admin Links Section */}
          {isAdmin && (
            <>
              <div className="pt-4 mt-4 border-t border-slate-200 dark:border-slate-700">
                <p className="px-3 text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">{t("Admin")}</p>
              </div>
              {adminLinks.map((link) => (
                <button
                  key={link.href}
                  onClick={() => router.push(link.href)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <link.icon className="w-4 h-4" />
                  {t(link.name)}
                  <ExternalLink className="w-3 h-3 ml-auto text-slate-400" />
                </button>
              ))}
            </>
          )}
          </nav>
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {/* General Tab */}
          {activeTab === 'general' && (
            <div className="space-y-6">
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">{t("Settings")}</h2>

                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div>
                      <label htmlFor="settings-language" className="font-medium text-slate-900 dark:text-white">
                        {t('Language')}
                      </label>
                      <div className="text-sm text-slate-500">{t('Choose the language used by this browser.')}</div>
                    </div>
                    <LanguageSelect id="settings-language" />
                  </div>

                  <div className="flex items-center justify-between py-3">
                    <div>
                      <div className="font-medium text-slate-900 dark:text-white">{t("Theme")}</div>
                      <div className="text-sm text-slate-500">{t("Toggle dark/light mode")}</div>
                    </div>
                    <button
                      onClick={toggleTheme}
                      className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-700 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700"
                    >
                      {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                      {t(theme === 'dark' ? 'Dark' : 'Light')}
                    </button>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">{t("Session")}</h2>
                
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between py-2">
                    <span className="text-slate-500">{t("Signed in as")}</span>
                    <span className="font-mono text-slate-900 dark:text-white">{identity?.auth_kind || t('unknown')}</span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-slate-500">{t("Role")}</span>
                    <span className="font-medium text-slate-900 dark:text-white">{t(identity?.role === 'admin' ? 'Admin' : identity?.role === 'team' ? 'Team' : 'unknown')}</span>
                  </div>
                  {identity?.org_id && (
                    <div className="flex justify-between py-2">
                      <span className="text-slate-500">{t("Organization")}</span>
                      <span className="font-mono text-slate-900 dark:text-white">{identity.org_id}</span>
                    </div>
                  )}
                </div>

                <div className="pt-3 mt-3 border-t border-slate-100 dark:border-slate-700">
                  <button
                    onClick={signOut}
                    className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-rose-600 dark:text-slate-400 dark:hover:text-rose-600 transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    {t("Sign out")}
                  </button>
                </div>
            </div>

              {/* Quick Start Guide */}
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                  <BookOpen className="w-5 h-5" />{' '}{t("Quick Start Guide")}
                </h2>
                <p className="text-sm text-slate-500 mb-4">
                  {t("Learn how OpenSRE works and get started with AI-powered investigations.")}
                </p>
                <button
                  onClick={() => setShowQuickStart(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-emerald-100/50 text-emerald-700 rounded-lg hover:bg-emerald-100/80 transition-colors"
                >
                  <BookOpen className="w-4 h-4" />
                  {t("View Guide")}
                </button>
              </div>
          </div>
          )}

          {/* Webhook Routing Tab */}
          {activeTab === 'routing' && (
            <div className="space-y-6">
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-1">
                      {t("Webhook Routing")}
                      <HelpTip id="webhook-routing" position="right">
                        <strong>{t("Webhook Routing")}</strong>{' '}{t("determines which incoming webhooks are directed to your team. Configure identifiers from your integrations (Slack channels, GitHub repos, PagerDuty services, etc.) so that alerts and events from those sources are routed to your team's agent.")}
                      </HelpTip>
                    </h2>
                    <p className="text-sm text-slate-500 mt-1">
                      {t("Configure which webhooks should route to your team")}
                    </p>
                  </div>
                </div>

                {/* Info Banner */}
                <div className="bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 rounded-lg p-4 mb-6">
                  <div className="flex items-start gap-3">
                    <Info className="w-5 h-5 text-slate-500 dark:text-slate-400 flex-shrink-0 mt-0.5" />
                    <div className="text-sm text-slate-600 dark:text-slate-300">
                      <p className="font-medium mb-1">{t("How routing works:")}</p>
                      <p>{t("When a webhook arrives from Slack, GitHub, PagerDuty, or other integrations, the system checks these identifiers to determine which team should handle the event. Add all the IDs and names that belong to your team.")}</p>
                    </div>
                  </div>
                </div>

                {routingLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
                    <span className="ml-2 text-slate-500">{t("Loading routing configuration...")}</span>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Add Routing Form */}
                    {editingRoutingField ? (
                      <div className="border border-slate-200 dark:border-slate-600 rounded-lg p-4 bg-slate-50 dark:bg-slate-700/50">
                        <div className="flex flex-col sm:flex-row gap-3">
                          <select
                            value={editingRoutingField}
                            onChange={(e) => setEditingRoutingField(e.target.value as keyof RoutingConfig)}
                            className="px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                          >
                            <option value="slack_channel_ids">{t("Slack Channel ID")}</option>
                            <option value="github_repos">{t("GitHub Repository")}</option>
                            <option value="pagerduty_service_ids">{t("PagerDuty Service ID")}</option>
                            <option value="incidentio_team_ids">{t("Incident.io Team ID")}</option>
                            <option value="incidentio_alert_source_ids">{t("Incident.io Alert Source ID")}</option>
                            <option value="coralogix_team_names">{t("Coralogix Team Name")}</option>
                            <option value="services">{t("Service Name")}</option>
                          </select>
                          <input
                            type="text"
                            value={newRoutingValue}
                            onChange={(e) => setNewRoutingValue(e.target.value)}
                            placeholder={
                              editingRoutingField === 'slack_channel_ids' ? 'C0A4967KRBM' :
                              editingRoutingField === 'github_repos' ? 'owner/repo' :
                              editingRoutingField === 'pagerduty_service_ids' ? 'PXXXXXX' :
                              editingRoutingField === 'incidentio_team_ids' ? '01KCSZ7FHG...' :
                              editingRoutingField === 'incidentio_alert_source_ids' ? '01KEGMSPP...' :
                              editingRoutingField === 'coralogix_team_names' ? 'team-name' :
                              'service-name'
                            }
                            className="flex-1 px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                            onKeyDown={(e) => e.key === 'Enter' && addRoutingValue(editingRoutingField)}
                            autoFocus
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => addRoutingValue(editingRoutingField)}
                              className="px-4 py-2 bg-slate-600 text-white text-sm rounded-lg hover:bg-slate-700"
                            >
                              {t("Add")}
                            </button>
                            <button
                              onClick={() => { setEditingRoutingField(null); setNewRoutingValue(''); }}
                              className="px-4 py-2 text-slate-600 dark:text-slate-400 text-sm hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-600"
                            >
                              {t("Cancel")}
                            </button>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => setEditingRoutingField('slack_channel_ids')}
                        className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border border-dashed border-slate-300 dark:border-slate-600 rounded-lg hover:border-slate-400 dark:hover:border-slate-600 transition-colors"
                      >
                        <Plus className="w-4 h-4" />
                        {t("Add Routing Rule")}
                      </button>
                    )}

                    {/* Configured Routes List */}
                    {(() => {
                      const allRoutes: { type: keyof RoutingConfig; label: string; value: string }[] = [];
                      routingConfig.slack_channel_ids.forEach(v => allRoutes.push({ type: 'slack_channel_ids', label: 'Slack', value: v }));
                      routingConfig.github_repos.forEach(v => allRoutes.push({ type: 'github_repos', label: 'GitHub', value: v }));
                      routingConfig.pagerduty_service_ids.forEach(v => allRoutes.push({ type: 'pagerduty_service_ids', label: 'PagerDuty', value: v }));
                      routingConfig.incidentio_team_ids.forEach(v => allRoutes.push({ type: 'incidentio_team_ids', label: 'Incident.io Team', value: v }));
                      routingConfig.incidentio_alert_source_ids.forEach(v => allRoutes.push({ type: 'incidentio_alert_source_ids', label: 'Incident.io Source', value: v }));
                      routingConfig.coralogix_team_names.forEach(v => allRoutes.push({ type: 'coralogix_team_names', label: 'Coralogix', value: v }));
                      routingConfig.services.forEach(v => allRoutes.push({ type: 'services', label: 'Service', value: v }));

                      if (allRoutes.length === 0) {
                        return (
                          <div className="text-sm text-slate-500 py-8 text-center border border-dashed border-slate-200 dark:border-slate-700 rounded-lg">
                            {t("No routing rules configured. Webhooks won't be routed to this team.")}
                          </div>
                        );
                      }

                      return (
                        <div className="border border-slate-200 dark:border-slate-700 rounded-lg divide-y divide-slate-200 dark:divide-slate-700">
                          {allRoutes.map((route, idx) => (
                            <div
                              key={`${route.type}-${route.value}-${idx}`}
                              className="flex items-center justify-between p-3 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                            >
                              <div className="flex items-center gap-3">
                                <span className="px-2 py-0.5 text-xs font-medium bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 rounded">
                                  {route.label}
                                </span>
                                <code className="text-sm text-slate-900 dark:text-slate-100">{route.value}</code>
                              </div>
                              <button
                                onClick={() => removeRoutingValue(route.type, route.value)}
                                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                              >
                                <X className="w-4 h-4" />
                              </button>
                            </div>
                          ))}
                        </div>
                      );
                    })()}

                    {/* Save Button */}
                    <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
                      <button
                        onClick={saveRoutingConfig}
                        disabled={routingSaving || !canWrite}
                        title={!canWrite ? 'You do not have write access' : undefined}
                        className="flex items-center gap-2 px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {routingSaving ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            {t("Saving...")}
                          </>
                        ) : (
                          <>
                            <Check className="w-4 h-4" />
                            {t("Save Routing Configuration")}
                          </>
                        )}
                      </button>
                      {!canWrite && (
                        <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-2">
                          {t("Configuration changes are disabled for your account.")}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Delivery & Notifications Tab */}
          {activeTab === 'notifications' && (
            <div className="space-y-6">
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-1">
                      {t("Output Destinations")}
                      <HelpTip id="output-destinations" position="right">
                        <strong>{t("Output Destinations")}</strong>{' '}{t("control where agent investigation results are posted. You can set default destinations (like a Slack channel) and override behavior based on how the agent was triggered.")}
                      </HelpTip>
                    </h2>
                    <p className="text-sm text-slate-500 mt-1">
                      {t("Configure where agent results are delivered")}
                    </p>
                  </div>
                </div>

                {/* Default Destinations */}
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-medium text-slate-900 dark:text-white mb-3">
                      {t("Default Destinations")}
                    </h3>
                    <p className="text-xs text-slate-500 mb-4">
                      {t("Agent results will be posted to these destinations by default")}
                    </p>

                    {outputConfig.default_destinations.length === 0 ? (
                      <div className="text-sm text-slate-500 py-8 text-center border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-lg">
                        {t("No default destinations configured. Results will only be posted to trigger-specific locations.")}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {outputConfig.default_destinations.map((dest, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-700 rounded-lg"
                          >
                            <div className="flex items-center gap-3">
                              <div className="px-2 py-1 bg-emerald-100/55 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 text-xs font-medium rounded">
                                {dest.type}
                              </div>
                              {dest.type === 'slack' && (
                                <span className="text-sm text-slate-700 dark:text-slate-300">
                                  {dest.channel_name || dest.channel_id || 'Unknown channel'}
                                </span>
                              )}
                              {dest.type === 'github' && (
                                <span className="text-sm text-slate-700 dark:text-slate-300">
                                  {dest.repo || 'Unknown repo'}
                                </span>
                              )}
                            </div>
                            <button
                              onClick={() => removeDestination(idx)}
                              className="text-rose-600 hover:text-rose-700 dark:text-rose-400"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}

                    {!showAddDestination ? (
                      <button
                        onClick={() => setShowAddDestination(true)}
                        className="mt-3 flex items-center gap-2 px-3 py-2 text-sm text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100/50 dark:hover:bg-emerald-900/20 rounded-lg"
                      >
                        <Plus className="w-4 h-4" />
                        {t("Add Destination")}
                      </button>
                    ) : (
                      <div className="mt-3 p-4 bg-slate-50 dark:bg-slate-700 rounded-lg space-y-3">
                        <div>
                          <label className="block text-xs text-slate-600 dark:text-slate-400 mb-1">
                            {t("Destination Type")}
                          </label>
                          <select
                            value={newDestinationType}
                            onChange={(e) => setNewDestinationType(e.target.value)}
                            className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"
                          >
                            <option value="slack">Slack</option>
                            <option value="github">GitHub</option>
                            <option value="pagerduty">PagerDuty</option>
                          </select>
                        </div>

                        {newDestinationType === 'slack' && (
                          <>
                            <div>
                              <label className="block text-xs text-slate-600 dark:text-slate-400 mb-1">
                                {t("Channel Name")}
                              </label>
                              <input
                                type="text"
                                placeholder="#incidents"
                                value={newDestinationConfig.channel_name}
                                onChange={(e) =>
                                  setNewDestinationConfig({ ...newDestinationConfig, channel_name: e.target.value })
                                }
                                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-600 dark:text-slate-400 mb-1">
                                {t("Channel ID")}
                              </label>
                              <input
                                type="text"
                                placeholder="C1234567890"
                                value={newDestinationConfig.channel_id}
                                onChange={(e) =>
                                  setNewDestinationConfig({ ...newDestinationConfig, channel_id: e.target.value })
                                }
                                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"
                              />
                            </div>
                          </>
                        )}

                        <div className="flex gap-2">
                          <button
                            onClick={addDestination}
                            disabled={
                              newDestinationType === 'slack' &&
                              (!newDestinationConfig.channel_id || !newDestinationConfig.channel_name)
                            }
                            className="flex items-center gap-2 px-3 py-2 text-sm bg-emerald-100/50 text-emerald-700 rounded-lg hover:bg-emerald-100/80 disabled:opacity-50"
                          >
                            <Check className="w-4 h-4" />
                            {t("Add")}
                          </button>
                          <button
                            onClick={() => {
                              setShowAddDestination(false);
                              setNewDestinationConfig({ channel_name: '', channel_id: '' });
                            }}
                            className="px-3 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg"
                          >
                            {t("Cancel")}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Trigger Overrides */}
                  <div className="border-t border-slate-200 dark:border-slate-700 pt-4 mt-6">
                    <h3 className="text-sm font-medium text-slate-900 dark:text-white mb-3">
                      {t("Trigger-Specific Rules")}
                    </h3>
                    <p className="text-xs text-slate-500 mb-4">
                      {t("Override behavior for specific trigger sources")}
                    </p>

                    <div className="space-y-3">
                      <div className="flex items-center justify-between py-2">
                        <div>
                          <div className="text-sm font-medium text-slate-900 dark:text-white">
                            {t("When triggered from Slack")}
                          </div>
                          <div className="text-xs text-slate-500">{t("Choose where to post results")}</div>
                        </div>
                        <select
                          value={outputConfig.trigger_overrides.slack || 'reply_in_thread'}
                          onChange={(e) =>
                            setOutputConfig({
                              ...outputConfig,
                              trigger_overrides: { ...outputConfig.trigger_overrides, slack: e.target.value },
                            })
                          }
                          className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"
                        >
                          <option value="reply_in_thread">{t("Reply in thread")}</option>
                          <option value="use_default">{t("Use default destinations")}</option>
                        </select>
                      </div>

                      <div className="flex items-center justify-between py-2">
                        <div>
                          <div className="text-sm font-medium text-slate-900 dark:text-white">
                            {t("When triggered from GitHub")}
                          </div>
                          <div className="text-xs text-slate-500">{t("Choose where to post results")}</div>
                        </div>
                        <select
                          value={outputConfig.trigger_overrides.github || 'comment_on_pr'}
                          onChange={(e) =>
                            setOutputConfig({
                              ...outputConfig,
                              trigger_overrides: { ...outputConfig.trigger_overrides, github: e.target.value },
                            })
                          }
                          className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"
                        >
                          <option value="comment_on_pr">{t("Comment on PR/issue")}</option>
                          <option value="use_default">{t("Use default destinations")}</option>
                        </select>
                      </div>

                      <div className="flex items-center justify-between py-2">
                        <div>
                          <div className="text-sm font-medium text-slate-900 dark:text-white">
                            {t("When triggered from API")}
                          </div>
                          <div className="text-xs text-slate-500">{t("Choose where to post results")}</div>
                        </div>
                        <select
                          value={outputConfig.trigger_overrides.api || 'use_default'}
                          onChange={(e) =>
                            setOutputConfig({
                              ...outputConfig,
                              trigger_overrides: { ...outputConfig.trigger_overrides, api: e.target.value },
                            })
                          }
                          className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"
                        >
                          <option value="use_default">{t("Use default destinations")}</option>
                          <option value="no_output">{t("No output (silent)")}</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Save Button */}
                  <div className="border-t border-slate-200 dark:border-slate-700 pt-4 mt-6">
                    <button
                      onClick={saveOutputConfig}
                      disabled={outputConfigLoading || !canWrite}
                      title={!canWrite ? 'You do not have write access' : undefined}
                      className="px-4 py-2 bg-emerald-100/50 text-emerald-700 rounded-lg hover:bg-emerald-100/80 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {outputConfigLoading ? t('Saving...') : 'Save Configuration'}
                    </button>
                    {!canWrite && (
                      <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-2">
                        {t("Configuration changes are disabled for your account.")}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Telemetry Tab */}
          {activeTab === 'telemetry' && (
            <div className="space-y-6">
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-100/55 dark:bg-emerald-900/20 rounded-lg">
                      <Activity className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                        {t("Telemetry")}
                        <button
                          onClick={() => setShowTelemetryInfo(true)}
                          className="p-0.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                          aria-label={t("Learn more about telemetry")}
                        >
                          <HelpCircle className="w-4 h-4" />
                        </button>
                      </h2>
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        {t("Share anonymous usage metrics to help improve OpenSRE")}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={toggleTelemetry}
                    disabled={telemetryLoading}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      telemetryEnabled ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-700'
                    } ${telemetryLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        telemetryEnabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
                  {telemetryEnabled
                    ? 'Telemetry is enabled. Anonymous metrics are being collected.'
                    : 'Telemetry is disabled. No data is being collected.'}
                </p>
              </div>

              {/* Telemetry Info Modal */}
              {showTelemetryInfo && (
                <TelemetryInfoModal onClose={() => setShowTelemetryInfo(false)} />
              )}
            </div>
          )}

          {/* Features Tab - AI Pipeline & Dependency Discovery */}
          {activeTab === 'features' && (
            <div className="space-y-6">
              {/* AI Pipeline Section */}
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-slate-100 dark:bg-slate-700 rounded-lg">
                      <Zap className="w-5 h-5 text-slate-600 dark:text-slate-400" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-1">
                        {t("AI Pipeline")}
                        <HelpTip id="ai-pipeline" position="right">
                          <strong>{t("AI Pipeline")}</strong>{' '}{t("automatically processes your incident data (Slack discussions, Confluence runbooks, Google Docs) on a schedule and extracts learnings to build your Knowledge Base. This enables agents to reference past incidents and solutions.")}
                        </HelpTip>
                      </h2>
                      <p className="text-sm text-slate-500">
                        {t("Automatically learn from incidents and build knowledge base")}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setPipelineConfig({ ...pipelineConfig, enabled: !pipelineConfig.enabled })}
                    disabled={featuresLoading}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      pipelineConfig.enabled ? 'bg-slate-600' : 'bg-slate-300 dark:bg-slate-700'
                    } ${featuresLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        pipelineConfig.enabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                {pipelineConfig.enabled && (
                  <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700 space-y-4">
                    {/* Schedule */}
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                        <Clock className="w-4 h-4" />
                        {t("Schedule (cron):")}
                      </div>
                      <input
                        type="text"
                        value={pipelineConfig.schedule}
                        onChange={(e) => setPipelineConfig({ ...pipelineConfig, schedule: e.target.value })}
                        placeholder="0 2 * * *"
                        className="flex-1 max-w-xs px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 font-mono"
                      />
                      <span className="text-xs text-slate-500">
                        {t("Default: 2:00 AM daily")}
                      </span>
                    </div>

                    {/* Data Sources / Ingestors */}
                    <div className="space-y-4">
                      <div className="text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t("Data Sources")}
                      </div>

                      {/* Slack Ingestor */}
                      <div className={`p-4 rounded-lg border ${
                        pipelineConfig.ingestors.slack.enabled
                          ? 'border-slate-400 bg-slate-50 dark:bg-slate-700/50'
                          : 'border-slate-200 dark:border-slate-600'
                      }`}>
                        <label className="flex items-center gap-3 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={pipelineConfig.ingestors.slack.enabled}
                            onChange={(e) =>
                              setPipelineConfig({
                                ...pipelineConfig,
                                ingestors: {
                                  ...pipelineConfig.ingestors,
                                  slack: { ...pipelineConfig.ingestors.slack, enabled: e.target.checked },
                                },
                              })
                            }
                            className="sr-only"
                          />
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center ${
                              pipelineConfig.ingestors.slack.enabled
                                ? 'bg-slate-600 border-slate-600'
                                : 'border-slate-300 dark:border-slate-600'
                            }`}
                          >
                            {pipelineConfig.ingestors.slack.enabled && <Check className="w-3 h-3 text-white" />}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-slate-900 dark:text-white">Slack</div>
                            <div className="text-xs text-slate-500">{t("Incident discussions & resolutions")}</div>
                          </div>
                        </label>
                        {pipelineConfig.ingestors.slack.enabled && (
                          <div className="mt-3 pl-7">
                            <label className="block text-xs text-slate-600 dark:text-slate-400 mb-1">
                              {t("Channels to monitor (comma-separated)")}
                            </label>
                            <input
                              type="text"
                              value={pipelineConfig.ingestors.slack.channels.join(', ')}
                              onChange={(e) =>
                                setPipelineConfig({
                                  ...pipelineConfig,
                                  ingestors: {
                                    ...pipelineConfig.ingestors,
                                    slack: {
                                      ...pipelineConfig.ingestors.slack,
                                      channels: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                                    },
                                  },
                                })
                              }
                              placeholder="#incidents, #oncall, #postmortems"
                              className="w-full px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700"
                            />
                            <p className="text-xs text-slate-400 mt-1">{t("Leave empty to monitor all bot-accessible channels")}</p>
                          </div>
                        )}
                      </div>

                      {/* Confluence Ingestor */}
                      <div className={`p-4 rounded-lg border ${
                        pipelineConfig.ingestors.confluence.enabled
                          ? 'border-slate-400 bg-slate-50 dark:bg-slate-700/50'
                          : 'border-slate-200 dark:border-slate-600'
                      }`}>
                        <label className="flex items-center gap-3 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={pipelineConfig.ingestors.confluence.enabled}
                            onChange={(e) =>
                              setPipelineConfig({
                                ...pipelineConfig,
                                ingestors: {
                                  ...pipelineConfig.ingestors,
                                  confluence: { ...pipelineConfig.ingestors.confluence, enabled: e.target.checked },
                                },
                              })
                            }
                            className="sr-only"
                          />
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center ${
                              pipelineConfig.ingestors.confluence.enabled
                                ? 'bg-slate-600 border-slate-600'
                                : 'border-slate-300 dark:border-slate-600'
                            }`}
                          >
                            {pipelineConfig.ingestors.confluence.enabled && <Check className="w-3 h-3 text-white" />}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-slate-900 dark:text-white">Confluence</div>
                            <div className="text-xs text-slate-500">{t("Runbooks & documentation")}</div>
                          </div>
                        </label>
                        {pipelineConfig.ingestors.confluence.enabled && (
                          <div className="mt-3 pl-7 space-y-3">
                            <div>
                              <label className="block text-xs text-slate-600 dark:text-slate-400 mb-1">
                                {t("Confluence Base URL")}
                              </label>
                              <input
                                type="text"
                                value={pipelineConfig.ingestors.confluence.base_url}
                                onChange={(e) =>
                                  setPipelineConfig({
                                    ...pipelineConfig,
                                    ingestors: {
                                      ...pipelineConfig.ingestors,
                                      confluence: { ...pipelineConfig.ingestors.confluence, base_url: e.target.value },
                                    },
                                  })
                                }
                                placeholder="https://company.atlassian.net"
                                className="w-full px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-600 dark:text-slate-400 mb-1">
                                {t("Space Keys (comma-separated)")}
                              </label>
                              <input
                                type="text"
                                value={pipelineConfig.ingestors.confluence.space_keys.join(', ')}
                                onChange={(e) =>
                                  setPipelineConfig({
                                    ...pipelineConfig,
                                    ingestors: {
                                      ...pipelineConfig.ingestors,
                                      confluence: {
                                        ...pipelineConfig.ingestors.confluence,
                                        space_keys: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                                      },
                                    },
                                  })
                                }
                                placeholder="ENG, OPS, RUNBOOKS"
                                className="w-full px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700"
                              />
                              <p className="text-xs text-slate-400 mt-1">{t("Leave empty to include all accessible spaces")}</p>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Google Docs Ingestor */}
                      <div className={`p-4 rounded-lg border ${
                        pipelineConfig.ingestors.gdocs.enabled
                          ? 'border-slate-400 bg-slate-50 dark:bg-slate-700/50'
                          : 'border-slate-200 dark:border-slate-600'
                      }`}>
                        <label className="flex items-center gap-3 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={pipelineConfig.ingestors.gdocs.enabled}
                            onChange={(e) =>
                              setPipelineConfig({
                                ...pipelineConfig,
                                ingestors: {
                                  ...pipelineConfig.ingestors,
                                  gdocs: { ...pipelineConfig.ingestors.gdocs, enabled: e.target.checked },
                                },
                              })
                            }
                            className="sr-only"
                          />
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center ${
                              pipelineConfig.ingestors.gdocs.enabled
                                ? 'bg-slate-600 border-slate-600'
                                : 'border-slate-300 dark:border-slate-600'
                            }`}
                          >
                            {pipelineConfig.ingestors.gdocs.enabled && <Check className="w-3 h-3 text-white" />}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-slate-900 dark:text-white">Google Docs</div>
                            <div className="text-xs text-slate-500">{t("Postmortems & procedures")}</div>
                          </div>
                        </label>
                        {pipelineConfig.ingestors.gdocs.enabled && (
                          <div className="mt-3 pl-7">
                            <label className="block text-xs text-slate-600 dark:text-slate-400 mb-1">
                              {t("Folder IDs (comma-separated, optional)")}
                            </label>
                            <input
                              type="text"
                              value={pipelineConfig.ingestors.gdocs.folder_ids.join(', ')}
                              onChange={(e) =>
                                setPipelineConfig({
                                  ...pipelineConfig,
                                  ingestors: {
                                    ...pipelineConfig.ingestors,
                                    gdocs: {
                                      ...pipelineConfig.ingestors.gdocs,
                                      folder_ids: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                                    },
                                  },
                                })
                              }
                              placeholder="1abc123..., 2def456..."
                              className="w-full px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700"
                            />
                            <p className="text-xs text-slate-400 mt-1">{t("Leave empty to include all shared drive docs")}</p>
                          </div>
                        )}
                      </div>

                      {/* Agent Traces Ingestor */}
                      <div className={`p-4 rounded-lg border ${
                        pipelineConfig.ingestors.agent_traces.enabled
                          ? 'border-slate-400 bg-slate-50 dark:bg-slate-700/50'
                          : 'border-slate-200 dark:border-slate-600'
                      }`}>
                        <label className="flex items-center gap-3 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={pipelineConfig.ingestors.agent_traces.enabled}
                            onChange={(e) =>
                              setPipelineConfig({
                                ...pipelineConfig,
                                ingestors: {
                                  ...pipelineConfig.ingestors,
                                  agent_traces: { enabled: e.target.checked },
                                },
                              })
                            }
                            className="sr-only"
                          />
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center ${
                              pipelineConfig.ingestors.agent_traces.enabled
                                ? 'bg-slate-600 border-slate-600'
                                : 'border-slate-300 dark:border-slate-600'
                            }`}
                          >
                            {pipelineConfig.ingestors.agent_traces.enabled && <Check className="w-3 h-3 text-white" />}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-slate-900 dark:text-white">{t("Agent Traces")}</div>
                            <div className="text-xs text-slate-500">{t("Tool calls, errors & decisions (auto-configured)")}</div>
                          </div>
                        </label>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Dependency Discovery Section */}
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-slate-100 dark:bg-slate-700 rounded-lg">
                      <Network className="w-5 h-5 text-slate-600 dark:text-slate-400" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-1">
                        {t("Service Dependency Discovery")}
                        <HelpTip id="dependency-discovery" position="right">
                          <strong>{t("Dependency Discovery")}</strong>{' '}{t("analyzes your observability data (traces, metrics) to automatically map service relationships. This helps agents understand how services connect and identify cascading failures during incidents.")}
                        </HelpTip>
                      </h2>
                      <p className="text-sm text-slate-500">
                        {t("Automatically discover service dependencies from observability data")}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setDependencyConfig({ ...dependencyConfig, enabled: !dependencyConfig.enabled })}
                    disabled={featuresLoading}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      dependencyConfig.enabled ? 'bg-slate-600' : 'bg-slate-300 dark:bg-slate-700'
                    } ${featuresLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        dependencyConfig.enabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                {dependencyConfig.enabled && (
                  <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700 space-y-4">
                    {/* Schedule */}
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                        <Clock className="w-4 h-4" />
                        {t("Schedule (cron):")}
                      </div>
                      <input
                        type="text"
                        value={dependencyConfig.schedule}
                        onChange={(e) => setDependencyConfig({ ...dependencyConfig, schedule: e.target.value })}
                        placeholder="0 */2 * * *"
                        className="flex-1 max-w-xs px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 font-mono"
                      />
                      <span className="text-xs text-slate-500">
                        {t("Default: Every 2 hours")}
                      </span>
                    </div>

                    {/* Data Sources */}
                    <div>
                      <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                        {t("Discovery Sources")}
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        {[
                          { key: 'new_relic', name: 'New Relic', desc: 'Distributed tracing' },
                          { key: 'datadog', name: 'Datadog', desc: 'APM traces' },
                          { key: 'cloudwatch', name: 'AWS CloudWatch', desc: 'X-Ray traces' },
                          { key: 'prometheus', name: 'Prometheus', desc: 'Service mesh metrics' },
                        ].map((source) => (
                          <label
                            key={source.key}
                            className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                              dependencyConfig.sources[source.key as keyof typeof dependencyConfig.sources]
                                ? 'border-slate-400 bg-slate-50 dark:bg-slate-700/50'
                                : 'border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800'
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={dependencyConfig.sources[source.key as keyof typeof dependencyConfig.sources]}
                              onChange={(e) =>
                                setDependencyConfig({
                                  ...dependencyConfig,
                                  sources: {
                                    ...dependencyConfig.sources,
                                    [source.key]: e.target.checked,
                                  },
                                })
                              }
                              className="sr-only"
                            />
                            <div
                              className={`w-4 h-4 rounded border flex items-center justify-center ${
                                dependencyConfig.sources[source.key as keyof typeof dependencyConfig.sources]
                                  ? 'bg-slate-600 border-slate-600'
                                  : 'border-slate-300 dark:border-slate-600'
                              }`}
                            >
                              {dependencyConfig.sources[source.key as keyof typeof dependencyConfig.sources] && (
                                <Check className="w-3 h-3 text-white" />
                              )}
                            </div>
                            <div>
                              <div className="text-sm font-medium text-slate-900 dark:text-white">
                                {source.name}
                              </div>
                              <div className="text-xs text-slate-500">{source.desc}</div>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Alert Correlation Section */}
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-slate-100 dark:bg-slate-700 rounded-lg">
                      <Link2 className="w-5 h-5 text-slate-600 dark:text-slate-400" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-1">
                        {t("Alert Correlation")}
                        <HelpTip id="alert-correlation" position="right">
                          <strong>{t("Alert Correlation")}</strong>{' '}{t("groups related alerts together to reduce noise. It uses three methods:")}{' '}<em>{t("temporal")}</em>{' '}{t("(alerts within a time window),")}{' '}<em>{t("topology")}</em>{' '}{t("(alerts from related services), and")}{' '}<em>{t("semantic")}</em>{' '}{t("(alerts with similar descriptions).")}
                        </HelpTip>
                      </h2>
                      <p className="text-sm text-slate-500">
                        {t("Automatically correlate related alerts using temporal, topology, and semantic analysis")}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setCorrelationConfig({ ...correlationConfig, enabled: !correlationConfig.enabled })}
                    disabled={featuresLoading}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      correlationConfig.enabled ? 'bg-slate-600' : 'bg-slate-300 dark:bg-slate-700'
                    } ${featuresLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        correlationConfig.enabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                {correlationConfig.enabled && (
                  <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700 space-y-4">
                    {/* Temporal Window */}
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                        <Clock className="w-4 h-4" />
                        {t("Temporal Window:")}
                      </div>
                      <input
                        type="number"
                        value={correlationConfig.temporal_window_seconds}
                        onChange={(e) => setCorrelationConfig({ ...correlationConfig, temporal_window_seconds: parseInt(e.target.value) || 300 })}
                        min={60}
                        max={3600}
                        className="w-24 px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 font-mono"
                      />
                      <span className="text-xs text-slate-500">
                        {t("seconds (default: 300 = 5 min)")}
                      </span>
                    </div>

                    {/* Semantic Threshold */}
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                        <Activity className="w-4 h-4" />
                        {t("Semantic Threshold:")}
                      </div>
                      <input
                        type="number"
                        value={correlationConfig.semantic_threshold}
                        onChange={(e) => setCorrelationConfig({ ...correlationConfig, semantic_threshold: parseFloat(e.target.value) || 0.75 })}
                        min={0}
                        max={1}
                        step={0.05}
                        className="w-24 px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 font-mono"
                      />
                      <span className="text-xs text-slate-500">
                        {t("0.0 - 1.0 (default: 0.75)")}
                      </span>
                    </div>

                    <div className="mt-3 text-xs text-slate-500">
                      {t("When enabled, incoming alerts are correlated with recent alerts based on:")}
                      <ul className="list-disc list-inside mt-2 space-y-1">
                        <li><strong>{t("Temporal:")}</strong>{' '}{t("Alerts within the time window")}</li>
                        <li><strong>{t("Topology:")}</strong>{' '}{t("Related services from dependency graph")}</li>
                        <li><strong>{t("Semantic:")}</strong>{' '}{t("Similar alert descriptions (above threshold)")}</li>
                      </ul>
                    </div>
                  </div>
                )}
              </div>

              {/* Save & Sync Actions */}
              <div className="flex items-center gap-3">
                <button
                  onClick={saveFeatureConfigs}
                  disabled={featuresSaving || !canWrite}
                  title={!canWrite ? 'You do not have write access' : undefined}
                  className="flex items-center gap-2 px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {featuresSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {t("Saving...")}
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      {t("Save Configuration")}
                    </>
                  )}
                </button>
                <button
                  onClick={syncCronJobs}
                  disabled={syncingCronJobs || !canWrite}
                  title={!canWrite ? 'You do not have write access' : undefined}
                  className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {syncingCronJobs ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {t("Syncing...")}
                    </>
                  ) : (
                    <>
                      <RefreshCcw className="w-4 h-4" />
                      {t("Apply Changes")}
                    </>
                  )}
                </button>
                <span className="text-xs text-slate-500">
                  {!canWrite ? t('Configuration changes are disabled for your account.') : t('Save config first, then apply to activate scheduled jobs')}
                </span>
              </div>

              {/* Info Box */}
              <div className="bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 rounded-lg p-4">
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  <span className="font-medium">{t("How it works:")}</span>{' '}{t("When enabled, these features run as scheduled Kubernetes CronJobs. The AI Pipeline processes incident data to build your knowledge base. Dependency Discovery analyzes observability data to map service relationships, helping agents understand your architecture during incidents.")}
                </p>
              </div>
            </div>
          )}

          {/* Advanced Tab */}
          {activeTab === 'advanced' && isAdmin && (
            <div className="space-y-6">
              <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-xl p-4">
                <div className="flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
                  <AlertTriangle className="w-5 h-5" />
                  <span className="font-medium">{t("Debug Tools")}</span>
                </div>
                <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
                  {t("These tools are for debugging and testing. Use with caution.")}
                </p>
              </div>

              {/* Quick Start Guide Section */}
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <BookOpen className="w-5 h-5" />{' '}{t("Quick Start Guide")}
                </h2>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                  {t("Review the onboarding guide or reset it for testing purposes.")}
                </p>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => {
                      setQuickStartInitialStep(1);
                      setShowQuickStart(true);
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-100/50 text-emerald-700 rounded-lg hover:bg-emerald-100/80 transition-colors"
                  >
                    <BookOpen className="w-4 h-4" />
                    {t("View Quick Start Guide")}
                  </button>
                  <button
                    onClick={() => {
                      resetOnboarding();
                      alert(t("Onboarding state reset. Refresh the page to see the welcome modal again."));
                    }}
                    className="flex items-center gap-2 px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                  >
                    <RotateCcw className="w-4 h-4" />
                    {t("Reset Onboarding")}
                  </button>
                </div>
              </div>

          </div>
          )}

          {activeTab === 'about' && (
            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">{t("About")}</h2>
              <div className="space-y-3">
                <div className="text-sm text-slate-500">OpenSRE</div>
                {aboutError ? (
                  <div className="text-sm text-rose-600">{t('Could not load version')}</div>
                ) : (
                  <>
                    <div className="text-2xl font-semibold text-emerald-700 dark:text-emerald-400">
                      {aboutVersion ?? '…'}
                    </div>
                    {aboutGitSha && (
                      <div className="text-sm text-slate-500 font-mono">{aboutGitSha}</div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Continue Onboarding floating button */}
      <ContinueOnboardingButton
        onContinue={(step) => {
          setQuickStartInitialStep(step);
          setShowQuickStart(true);
        }}
      />

      {/* Quick Start Guide Modal */}
      {showQuickStart && (
        <QuickStartWizard
          onClose={() => setShowQuickStart(false)}
          onRunAgent={() => {
            setShowQuickStart(false);
            router.push('/team/agent-runs');
          }}
          onSkip={() => setShowQuickStart(false)}
          initialStep={quickStartInitialStep}
        />
      )}
    </div>
  );
}
