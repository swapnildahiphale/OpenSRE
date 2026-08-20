'use client';

import { useEffect, useState, useCallback } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { PageHeader, Button, Skeleton, TeamPageShell } from '@/components/ui-flow';
import {
  Server,
  Plus,
  Save,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Eye,
  EyeOff,
  X,
  ToggleLeft,
  ToggleRight,
  MinusSquare,
  ChevronDown,
  ChevronRight,
  Settings,
  Trash2,
  BookOpen,
} from 'lucide-react';

interface ConfigField {
  type: string;
  required: boolean;
  display_name: string;
  description?: string;
  placeholder?: string;
  default?: string;
  allowed_values?: string[];
}

interface ToolItem {
  id: string;
  name: string;
  description?: string;
  type: 'tool' | 'mcp_server' | 'integration';
  enabled: boolean;
  config_schema: Record<string, ConfigField>;
  config_values: Record<string, string>;
  config_sources?: Record<string, 'team' | 'inherited'>;  // NEW: Track which values are team-level
  source: 'org' | 'team';
  category?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  tools?: Array<{
    name: string;
    display_name: string;
    description: string;
    category?: string;
  }>;
  enabled_tools?: string[];  // NEW: Tool filtering for MCPs
}

interface ToolMetadata {
  id: string;
  name: string;
  description: string;
  category: string;
  required_integrations: string[];
}

const SKILL_CATEGORY_ORDER = [
  'Core Methodology',
  'Memory',
  'Observability',
  'Infrastructure & Cloud',
  'Databases',
  'Incident Management',
  'Alerting & On-call',
  'Ticketing & Project',
  'Code & Version Control',
  'Docs & Knowledge',
  'Other Integrations',
];

interface IntegrationSchemaResponse {
  id: string;
  name: string;
  description: string;
  category: string;
}

export default function TeamToolsPage() {
  const { identity } = useIdentity();
  const [items, setItems] = useState<ToolItem[]>([]);
  const [toolMetadata, setToolMetadata] = useState<ToolMetadata[]>([]);
  const [integrationSchemas, setIntegrationSchemas] = useState<IntegrationSchemaResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingItem, setEditingItem] = useState<ToolItem | null>(null);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set([]));
  const [showAddCustomModal, setShowAddCustomModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [newServerForm, setNewServerForm] = useState({
    name: '',
    description: '',
    command: '',
    args: '',
    env: '',
  });
  const [previewingTools, setPreviewingTools] = useState(false);
  const [previewedTools, setPreviewedTools] = useState<{
    success: boolean;
    tool_count: number;
    tools: Array<{
      name: string;
      display_name: string;
      description: string;
      category: string;
    }>;
    warnings: string[];
    error?: string;
  } | null>(null);

  // Skills catalog state
  const [skillsCatalog, setSkillsCatalog] = useState<Array<{
    id: string;
    name: string;
    description: string;
    category: string;
    required_integrations: string[];
    enabled: boolean;
  }>>([]);

  // Team-level skills config (wildcard-minus-disabled model)
  const [teamSkillsConfig, setTeamSkillsConfig] = useState<{ enabled?: string[]; disabled?: string[] } | null>(null);

  // NEW: Tool filtering modal state
  const [filteringMcp, setFilteringMcp] = useState<ToolItem | null>(null);
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set());

  const teamId = identity?.team_node_id;

  const loadItems = useCallback(async () => {
    if (!teamId) return;
    setLoading(true);

    try {
      // Fetch config and raw config (to detect team vs org)
      const [configRes, rawConfigRes] = await Promise.all([
        fetch('/api/team/config'),
        fetch('/api/config/me/raw'),
      ]);

      if (!configRes.ok) {
        throw new Error('Failed to load configuration');
      }

      const data = await configRes.json();
      const rawConfigData = rawConfigRes.ok ? await rawConfigRes.json() : null;

      // Extract configuration
      const integrations = data.integrations || {};
      const mcpServersDict = data.mcp_servers || {};
      // Canonical format: tools is a dict {tool_id: boolean}
      const toolsDict = (data.tools || {}) as Record<string, boolean>;

      // Populate team skills config for the wildcard-minus-disabled toggle model
      setTeamSkillsConfig(data.skills || null);

      // Detect team-level MCP servers (exist in raw team config)
      const teamMcpIds = new Set<string>();
      if (rawConfigData?.configs && rawConfigData?.lineage) {
        // Find team node ID from lineage (last item is current team)
        const teamNodeId = rawConfigData.lineage[rawConfigData.lineage.length - 1];
        const teamConfig = rawConfigData.configs[teamNodeId];

        if (teamConfig?.mcp_servers) {
          Object.keys(teamConfig.mcp_servers).forEach(id => teamMcpIds.add(id));
        }
      }

      // Convert integrations object to array
      // Use schema descriptions (generic) instead of config descriptions (org-specific)
      const integrationItems = Object.entries(integrations).map(([id, config]: [string, any]) => {
        // Merge org-level and team-level config schemas
        const orgSchema = config.config_schema || {};
        const teamSchema = config.team_config_schema || {};
        const mergedSchema = { ...orgSchema, ...teamSchema };

        // Backend now provides config_values and config_sources directly
        // Fallback to extracting from flat structure for backwards compatibility
        let extractedValues: Record<string, string> = config.config_values || {};
        if (Object.keys(extractedValues).length === 0) {
          // Fallback: extract from flat structure
          for (const fieldName of Object.keys(mergedSchema)) {
            if (config[fieldName] !== undefined) {
              extractedValues[fieldName] = config[fieldName];
            }
          }
        }

        // Get config_sources from backend (indicates team vs inherited for each field)
        const configSources: Record<string, 'team' | 'inherited'> = config.config_sources || {};

        return {
          id,
          name: config.name || id,
          description: '', // Will be populated from schema in next step
          type: 'integration' as const,
          enabled: true,  // Integrations are always "available", tools use them
          config_schema: mergedSchema,
          config_values: extractedValues,
          config_sources: configSources,
          source: 'org' as const,
        };
      });

      // Convert mcp_servers dict to array and extract individual tools
      const mcpServerItems: ToolItem[] = [];

      Object.entries(mcpServersDict).forEach(([id, config]: [string, any]) => {
        const isTeamLevel = teamMcpIds.has(id);

        // Add MCP server card
        mcpServerItems.push({
          id,
          name: config.name || id,
          description: config.description || 'Custom MCP server',
          type: 'mcp_server' as const,
          enabled: config.enabled !== false,
          config_schema: {},
          config_values: config,
          source: isTeamLevel ? 'team' : 'org',
          tools: config.tools || [], // Include tools for display in card
          enabled_tools: config.enabled_tools || ['*'], // Include tool filter settings
        });
      });

      // Combine all items and apply enabled/disabled logic
      const allItems = [...integrationItems, ...mcpServerItems].map((item: ToolItem) => {
        // Integrations are always "available"
        if (item.type === 'integration') {
          return item;
        }

        // For tools/MCPs: check enabled/disabled status in canonical format
        // If tool is explicitly set in toolsDict, use that value
        // Otherwise, use the default enabled state
        const isEnabled = item.id in toolsDict ? toolsDict[item.id] : (item.enabled !== false);
        return { ...item, enabled: isEnabled };
      });

      setItems(allItems);

      // Load tool metadata (integration dependencies)
      try {
        const metadataRes = await fetch('/api/v1/tools/metadata');
        if (metadataRes.ok) {
          const metadataData = await metadataRes.json();
          setToolMetadata(metadataData.tools || []);
        }
      } catch (e) {
        console.error('Failed to load tool metadata:', e);
      }

      // Load integration schemas (for descriptions)
      try {
        const schemasRes = await fetch('/api/v1/integrations/schemas');
        if (schemasRes.ok) {
          const schemasData = await schemasRes.json();
          setIntegrationSchemas(schemasData.integrations || []);
        }
      } catch (e) {
        console.error('Failed to load integration schemas:', e);
      }

      // Load skills catalog from dedicated endpoint
      try {
        const skillsRes = await fetch('/api/team/skills');
        if (skillsRes.ok) {
          const skillsData = await skillsRes.json();
          setSkillsCatalog(skillsData.skills || []);
        }
      } catch (e) {
        console.error('Failed to load skills catalog:', e);
      }
    } catch (e) {
      console.error('Failed to load tools/MCPs:', e);
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  // Update integration descriptions from schemas (use generic descriptions, not org-specific ones)
  useEffect(() => {
    if (integrationSchemas.length > 0 && items.length > 0) {
      const schemaLookup = new Map(integrationSchemas.map(s => [s.id, s]));
      const updatedItems = items.map(item => {
        if (item.type === 'integration') {
          const schema = schemaLookup.get(item.id);
          if (schema) {
            return { ...item, description: schema.description };
          }
        }
        return item;
      });
      setItems(updatedItems);
    }
  }, [integrationSchemas]);

  // Auto-expand sections with search matches
  useEffect(() => {
    if (searchQuery) {
      const sectionsWithMatches = new Set<string>();

      // Check integrations for matches
      const integrationItems = items.filter(i => {
        const hasRequiredConfig = Object.values(i.config_schema || {}).some(f => f.required);
        return hasRequiredConfig;
      });

      integrationItems.forEach(item => {
        if (item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            item.description?.toLowerCase().includes(searchQuery.toLowerCase())) {
          sectionsWithMatches.add('integration');
        }
      });

      // Check custom servers for matches
      const serverItems = items.filter(i => i.type === 'mcp_server');
      serverItems.forEach(item => {
        if (item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            item.description?.toLowerCase().includes(searchQuery.toLowerCase())) {
          sectionsWithMatches.add('mcp');
        }
      });

      // Check skills for matches — expand matching skill categories
      skillsCatalog.forEach(skill => {
        if (skill.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            skill.description?.toLowerCase().includes(searchQuery.toLowerCase())) {
          sectionsWithMatches.add('skills');
          sectionsWithMatches.add(`skill-cat-${skill.category}`);
        }
      });

      // Auto-expand sections with matches
      setExpandedCategories(sectionsWithMatches);
    } else {
      // When search is cleared, collapse all sections
      setExpandedCategories(new Set());
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery]);

  const getMissingRequiredFields = (item: ToolItem): string[] => {
    const missing: string[] = [];
    if (!item.config_schema) return missing;
    
    for (const [fieldName, fieldSchema] of Object.entries(item.config_schema)) {
      if (fieldSchema.required) {
        const value = item.config_values?.[fieldName];
        if (!value || value === '') {
          missing.push(fieldSchema.display_name || fieldName);
        }
      }
    }
    return missing;
  };

  const saveConfig = async () => {
    if (!editingItem) return;
    setSaving(true);
    setMessage(null);

    try {
      // Send integration config as flat structure (DB stores it flat)
      // editValues is already {api_key: "value", region: "value"}, send it directly
      const res = await fetch('/api/team/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          integrations: {
            [editingItem.id]: editValues,  // Send flat, no config_values wrapper
          },
        }),
      });

      if (res.ok) {
        setMessage({ type: 'success', text: 'Configuration saved!' });
        setEditingItem(null);
        await loadItems();
      } else {
        setMessage({ type: 'error', text: 'Failed to save configuration' });
      }
    } catch {
      setMessage({ type: 'error', text: 'Failed to save configuration' });
    } finally {
      setSaving(false);
    }
  };

  const toggleEnabled = async (item: ToolItem) => {
    // Integrations cannot be toggled (they're always available)
    if (item.type === 'integration') {
      return;
    }

    setSaving(true);
    try {
      // Get current lists
      const res = await fetch('/api/team/config');
      if (!res.ok) return;

      const data = await res.json();
      // Canonical format: tools is a dict {tool_id: boolean}
      const currentTools = (data.tools || {}) as Record<string, boolean>;

      // Toggle the tool in the dict
      const newTools = {
        ...currentTools,
        [item.id]: !item.enabled,
      };

      const patchRes = await fetch('/api/team/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tools: newTools,
        }),
      });

      if (patchRes.ok) {
        // Update local state immediately
        setItems(prev => prev.map(i =>
          i.id === item.id ? { ...i, enabled: !i.enabled } : i
        ));
      }
    } catch (e) {
      console.error('Failed to toggle:', e);
    } finally {
      setSaving(false);
    }
  };

  const toggleSkill = async (skillId: string, currentlyEnabled: boolean) => {
    // Read current team skills config from the loaded config, default to wildcard.
    const current = (teamSkillsConfig?.disabled ?? []) as string[];
    const disabled = currentlyEnabled
      ? Array.from(new Set([...current, skillId]))
      : current.filter((s) => s !== skillId);
    const res = await fetch('/api/team/config', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skills: { enabled: ['*'], disabled } }),
    });
    if (res.ok) {
      // Update the local state to reflect the new disabled list
      setTeamSkillsConfig({ enabled: ['*'], disabled });
      // Refetch the catalog so enabled flags reflect the new config.
      const sr = await fetch('/api/team/skills');
      if (sr.ok) setSkillsCatalog((await sr.json()).skills || []);
    }
  };

  const toggleCategory = async (
    _category: string,
    skillsInCat: Array<{ id: string }>,
    enableAll: boolean,
  ) => {
    const catIds = skillsInCat.map((s) => s.id);
    const current = (teamSkillsConfig?.disabled ?? []) as string[];
    const disabled = enableAll
      ? current.filter((s) => !catIds.includes(s))
      : Array.from(new Set([...current, ...catIds]));
    const res = await fetch('/api/team/config', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skills: { enabled: ['*'], disabled } }),
    });
    if (res.ok) {
      setTeamSkillsConfig({ enabled: ['*'], disabled });
      const sr = await fetch('/api/team/skills');
      if (sr.ok) setSkillsCatalog((await sr.json()).skills || []);
    }
  };

  const previewMCPServer = async () => {
    if (!newServerForm.command) {
      setMessage({ type: 'error', text: 'Command is required to preview' });
      return;
    }

    setPreviewingTools(true);
    setMessage(null);
    setPreviewedTools(null);

    try {
      // Parse args and env
      const argsArray = newServerForm.args
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0);

      const envObject: Record<string, string> = {};
      if (newServerForm.env) {
        newServerForm.env.split('\n').forEach(line => {
          const trimmed = line.trim();
          if (trimmed && trimmed.includes('=')) {
            const [key, ...valueParts] = trimmed.split('=');
            envObject[key.trim()] = valueParts.join('=').trim();
          }
        });
      }

      const res = await fetch('/api/team/mcp-servers/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newServerForm.name || 'Preview',
          description: newServerForm.description,
          command: newServerForm.command,
          args: argsArray,
          env_vars: envObject,
        }),
      });

      const data = await res.json();

      if (data.success) {
        setPreviewedTools(data);
        setMessage({ type: 'success', text: `Discovered ${data.tool_count} tools!` });
      } else {
        // Use error_details for better context, fallback to error
        const errorMsg = data.error_details || data.error || 'Failed to preview MCP server';
        setMessage({ type: 'error', text: errorMsg });
      }
    } catch (e) {
      console.error('Failed to preview MCP:', e);
      setMessage({ type: 'error', text: 'Failed to connect to MCP server' });
    } finally {
      setPreviewingTools(false);
    }
  };

  const saveCustomServer = async () => {
    if (!newServerForm.name || !newServerForm.command) {
      setMessage({ type: 'error', text: 'Name and command are required' });
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      // Auto-run preview if not already done
      let toolsToSave = previewedTools?.success ? previewedTools.tools : undefined;

      if (!toolsToSave) {
        setMessage({ type: 'info', text: 'Discovering tools...' });

        // Parse args and env for preview
        const argsArray = newServerForm.args
          .split('\n')
          .map(line => line.trim())
          .filter(line => line.length > 0);

        const envObject: Record<string, string> = {};
        if (newServerForm.env) {
          newServerForm.env.split('\n').forEach(line => {
            const trimmed = line.trim();
            if (trimmed && trimmed.includes('=')) {
              const [key, ...valueParts] = trimmed.split('=');
              envObject[key.trim()] = valueParts.join('=').trim();
            }
          });
        }

        // Run preview
        const previewRes = await fetch('/api/team/mcp-servers/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: newServerForm.name || 'Preview',
            description: newServerForm.description,
            command: newServerForm.command,
            args: argsArray,
            env_vars: envObject,
          }),
        });

        const previewData = await previewRes.json();

        if (previewData.success) {
          toolsToSave = previewData.tools;
          setMessage({ type: 'success', text: `Discovered ${previewData.tool_count} tools!` });
        } else {
          // Use error_details for better context, fallback to error
          const errorMsg = previewData.error_details || previewData.error || 'Failed to discover tools';
          setMessage({ type: 'error', text: errorMsg });
          setSaving(false);
          return;
        }
      }

      // Parse args and env again for server creation
      const argsArray = newServerForm.args
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0);

      const envObject: Record<string, string> = {};
      if (newServerForm.env) {
        newServerForm.env.split('\n').forEach(line => {
          const trimmed = line.trim();
          if (trimmed && trimmed.includes('=')) {
            const [key, ...valueParts] = trimmed.split('=');
            envObject[key.trim()] = valueParts.join('=').trim();
          }
        });
      }

      // Create new server object
      const newServer: ToolItem = {
        id: `custom_${newServerForm.name.toLowerCase().replace(/\s+/g, '_')}`,
        name: newServerForm.name,
        description: newServerForm.description || 'Custom MCP server',
        type: 'mcp_server',
        enabled: true,
        config_schema: {},
        config_values: {},
        source: 'team',
        command: newServerForm.command,
        args: argsArray.length > 0 ? argsArray : undefined,
        env: Object.keys(envObject).length > 0 ? envObject : undefined,
        tools: toolsToSave,
      };

      // Get current config
      const res = await fetch('/api/team/config');
      if (!res.ok) {
        setMessage({ type: 'error', text: 'Failed to load current config' });
        return;
      }

      const data = await res.json();
      const mcpServers = data.mcp_servers || {};

      // Add new server to mcp_servers dict (keyed by MCP ID)
      const updatedMcpServers = {
        ...mcpServers,
        [newServer.id]: newServer,
      };

      // Save to config
      const patchRes = await fetch('/api/team/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mcp_servers: updatedMcpServers,
        }),
      });

      if (patchRes.ok) {
        setMessage({ type: 'success', text: 'Custom server added successfully!' });
        setShowAddCustomModal(false);
        setNewServerForm({
          name: '',
          description: '',
          command: '',
          args: '',
          env: '',
        });
        await loadItems();
      } else {
        setMessage({ type: 'error', text: 'Failed to save custom server' });
      }
    } catch (e) {
      console.error('Failed to save custom server:', e);
      setMessage({ type: 'error', text: 'Failed to save custom server' });
    } finally {
      setSaving(false);
    }
  };

  const deleteMCPServer = async (item: ToolItem) => {
    if (!confirm(`Are you sure you want to delete "${item.name}"? This will also remove all tools from this MCP server from your agents.`)) {
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      // Get current config
      const res = await fetch('/api/team/config');
      if (!res.ok) {
        setMessage({ type: 'error', text: 'Failed to load current config' });
        return;
      }

      const data = await res.json();
      const mcpServers = data.mcp_servers || {};

      // Find the MCP server being deleted
      const mcpToDelete = mcpServers[item.id];

      // Get list of tool names from this MCP server
      const mcpToolNames = new Set<string>();
      if (mcpToDelete && mcpToDelete.tools) {
        mcpToDelete.tools.forEach((tool: any) => {
          mcpToolNames.add(tool.name);
        });
      }

      // Remove the server from mcp_servers dict
      const updatedMcpServers = { ...mcpServers };
      delete updatedMcpServers[item.id];

      // Clean up agent tool assignments
      const agents = data.agents || {};
      const updatedAgents: Record<string, any> = {};
      let toolsRemoved = 0;

      Object.entries(agents).forEach(([agentId, agentConfig]: [string, any]) => {
        const updatedAgent = { ...agentConfig };
        let modified = false;

        // Remove MCP tools from enable_extra_tools
        if (updatedAgent.enable_extra_tools && Array.isArray(updatedAgent.enable_extra_tools)) {
          const filtered = updatedAgent.enable_extra_tools.filter((toolName: string) => !mcpToolNames.has(toolName));
          if (filtered.length !== updatedAgent.enable_extra_tools.length) {
            updatedAgent.enable_extra_tools = filtered;
            toolsRemoved += updatedAgent.enable_extra_tools.length - filtered.length;
            modified = true;
          }
        }

        // Remove from mcp_tools if present (per-agent MCP tool filtering)
        if (updatedAgent.mcp_tools && Array.isArray(updatedAgent.mcp_tools)) {
          const filtered = updatedAgent.mcp_tools.filter((toolName: string) => !mcpToolNames.has(toolName));
          if (filtered.length !== updatedAgent.mcp_tools.length) {
            updatedAgent.mcp_tools = filtered;
            modified = true;
          }
        }

        updatedAgents[agentId] = modified ? updatedAgent : agentConfig;
      });

      // Save to config
      const patchRes = await fetch('/api/team/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mcp_servers: updatedMcpServers,
          agents: updatedAgents,
        }),
      });

      if (patchRes.ok) {
        const msg = toolsRemoved > 0
          ? `MCP server deleted and ${toolsRemoved} tool(s) removed from agents`
          : 'MCP server deleted successfully!';
        setMessage({ type: 'success', text: msg });
        await loadItems();
      } else {
        setMessage({ type: 'error', text: 'Failed to delete MCP server' });
      }
    } catch (e) {
      console.error('Failed to delete MCP server:', e);
      setMessage({ type: 'error', text: 'Failed to delete MCP server' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <TeamPageShell
        variant="fixedHeader"
        header={<Skeleton className="h-16 w-64 rounded-xl" />}
      >
        <Skeleton className="h-48 w-full rounded-xl" />
      </TeamPageShell>
    );
  }

  // Build integration schema lookup (for descriptions)
  const integrationSchemaById = new Map(integrationSchemas.map(s => [s.id, s]));

  // Separate integrations (configurable items like Grafana, Kubernetes) from tools
  const integrations: ToolItem[] = [];
  const customServers: ToolItem[] = [];

  for (const item of items) {
    // Items with config_schema and required fields are "integrations"
    const hasRequiredConfig = Object.values(item.config_schema || {}).some(f => f.required);
    const integrationSchema = integrationSchemaById.get(item.id);

    // Skip orphaned items (no description, not a real integration, not an MCP)
    if (!item.description && !hasRequiredConfig && item.type !== 'mcp_server') {
      console.warn(`Skipping orphaned item with no description: ${item.id}`);
      continue;
    }

    if (item.type === 'mcp_server') {
      customServers.push({ ...item, category: 'mcp' });
    } else if (hasRequiredConfig) {
      // Configurable integration (Grafana, Kubernetes, Datadog, etc.)
      integrations.push({
        ...item,
        description: integrationSchema?.description || item.description,
        type: 'integration',
        category: 'integration'
      });
    }
  }

  // Separate enabled/disabled for custom servers
  const enabledServers = customServers.filter(i => i.enabled);
  const disabledServers = customServers.filter(i => !i.enabled);

  // Group skills by category in fixed display order
  const skillsByCategory: Record<string, typeof skillsCatalog> = {};
  skillsCatalog.forEach(skill => {
    const cat = skill.category || 'Other Integrations';
    if (!skillsByCategory[cat]) skillsByCategory[cat] = [];
    skillsByCategory[cat].push(skill);
  });
  const orderedSkillCategories = SKILL_CATEGORY_ORDER.filter(cat => skillsByCategory[cat]?.length > 0);

  const renderCard = (item: ToolItem) => {
    const missingFields = getMissingRequiredFields(item);
    const hasMissing = missingFields.length > 0;

    // Get tools that depend on this integration
    const dependentTools = item.type === 'integration'
      ? toolMetadata.filter(tool => tool.required_integrations.includes(item.id))
      : [];

    return (
      <div
        key={item.id}
        className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-medium text-slate-900 dark:text-white">{item.name}</h3>
              {item.source === 'org' && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-500">
                  Inherited
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-1 line-clamp-2">{item.description}</p>

            {/* Show dependent tools for integrations */}
            {dependentTools.length > 0 && (
              <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-700">
                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide mb-1">
                  Powers {dependentTools.length} tool{dependentTools.length !== 1 ? 's' : ''}:
                </p>
                <div className="flex flex-wrap gap-1">
                  {dependentTools.map(tool => (
                    <span
                      key={tool.id}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400"
                      title={tool.description}
                    >
                      {tool.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Show tools provided by MCP servers */}
            {item.type === 'mcp_server' && item.tools && Array.isArray(item.tools) && item.tools.length > 0 && (
              <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-700">
                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide mb-1">
                  Provides {item.tools.length} tool{item.tools.length !== 1 ? 's' : ''}:
                </p>
                <div className="flex flex-wrap gap-1">
                  {item.tools.map((tool: any, idx: number) => {
                    // Handle both string arrays and object arrays
                    const toolName = typeof tool === 'string' ? tool : (tool.display_name || tool.name);
                    const toolDesc = typeof tool === 'string' ? tool : (tool.description || tool.name);
                    return (
                      <span
                        key={idx}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100/50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400"
                        title={toolDesc}
                      >
                        {toolName}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Enable/Disable Toggle - Only for tools and MCPs, NOT for integrations */}
            {item.type !== 'integration' && (
              <button
                onClick={() => toggleEnabled(item)}
                disabled={saving}
                className={`p-1 rounded transition-colors ${
                  item.enabled
                    ? 'text-green-600 hover:text-green-700'
                    : 'text-slate-400 hover:text-slate-500'
                }`}
                title={item.enabled ? 'Disable' : 'Enable'}
              >
                {item.enabled ? (
                  <ToggleRight className="w-6 h-6" />
                ) : (
                  <ToggleLeft className="w-6 h-6" />
                )}
              </button>
            )}

            {/* Filter Tools button - only for MCP servers with tools */}
            {item.type === 'mcp_server' && item.tools && item.tools.length > 0 && (
              <button
                onClick={() => {
                  // Debug: Log the item data
                  console.log('🔍 Debug - Opening filter for MCP:', item.id);
                  console.log('🔍 Debug - Full item object:', item);
                  console.log('🔍 Debug - item.tools:', item.tools);
                  console.log('🔍 Debug - item.enabled_tools:', item.enabled_tools);
                  console.log('🔍 Debug - enabled_tools type:', typeof item.enabled_tools);
                  console.log('🔍 Debug - enabled_tools is array?', Array.isArray(item.enabled_tools));

                  setFilteringMcp(item);
                  // Initialize selected tools
                  const enabled = item.enabled_tools || ['*'];
                  console.log('🔍 Debug - Computed enabled:', enabled);
                  console.log('🔍 Debug - enabled.includes("*")?', enabled.includes('*'));

                  if (enabled.includes('*')) {
                    // All tools enabled - handle both string and object arrays
                    const toolNames = item.tools?.map(t =>
                      typeof t === 'string' ? t : (t.name || t.display_name)
                    ) || [];
                    console.log('🔍 Debug - All tools selected, extracted toolNames:', toolNames);
                    setSelectedTools(new Set(toolNames));
                  } else {
                    console.log('🔍 Debug - Using specific enabled tools:', enabled);
                    setSelectedTools(new Set(enabled));
                  }
                }}
                className="p-1 rounded text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                title="Filter Tools"
              >
                <Settings className="w-4 h-4" />
              </button>
            )}

            {/* Configure button */}
            {item.config_schema && Object.keys(item.config_schema).length > 0 && (
              <button
                onClick={() => {
                  setEditingItem(item);
                  setEditValues(item.config_values || {});
                }}
                className={`text-xs px-2 py-1 rounded ${
                  hasMissing && item.enabled
                    ? 'bg-rose-50 dark:bg-rose-900/20 text-rose-700 dark:text-rose-400'
                    : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400'
                } hover:opacity-80`}
              >
                Configure
              </button>
            )}

            {/* Delete button - only for team-added MCP servers */}
            {item.type === 'mcp_server' && item.source === 'team' && (
              <button
                onClick={() => deleteMCPServer(item)}
                disabled={saving}
                className="p-1 rounded text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-900/20 disabled:opacity-50 disabled:cursor-not-allowed"
                title="Delete MCP Server"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <>
    <TeamPageShell
      variant="fixedHeader"
      header={
        <>
          <PageHeader
            eyebrow="Team console"
            title="Tools"
            subtitle="Integrations, MCP servers, and skills available to your AI agents"
            actions={
              <Button variant="primary" onClick={() => setShowAddCustomModal(true)}>
                <Plus className="w-4 h-4" />
                Add Custom
              </Button>
            }
          />

          {message && (
            <div className={`p-3 rounded-xl flex items-center gap-2 text-sm ${
              message.type === 'success'
                ? 'bg-green-50 text-green-700 border border-green-200'
                : message.type === 'info'
                ? 'bg-emerald-100/50 text-emerald-700 border border-emerald-200/60'
                : 'bg-rose-50 text-rose-700 border border-rose-200'
            }`}>
              {message.type === 'success' ? <CheckCircle className="w-4 h-4" /> : message.type === 'info' ? <AlertTriangle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              {message.text}
            </div>
          )}
        </>
      }
    >
      <div className="space-y-6">
        {/* Summary Strip */}
        <div className="flex flex-wrap gap-3">
          <span className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-xs font-medium bg-emerald-100/55 text-emerald-700">
            <Server className="w-3.5 h-3.5" />
            {customServers.length} MCP Servers
          </span>
          <span className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-xs font-medium bg-white border border-slate-200/70 text-slate-600">
            <BookOpen className="w-3.5 h-3.5" />
            {skillsCatalog.length} Skills
          </span>
        </div>

        {/* Search Bar */}
        <div className="mb-6">
          <input
            type="text"
            placeholder="Search integrations, tools, and skills..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2 bg-white border border-slate-200/70 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40 focus:border-emerald-500/50"
          />
        </div>

        {/* Integrations Section */}
        {integrations.length > 0 && (() => {
          const filteredIntegrations = integrations.filter(item =>
            item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            item.description?.toLowerCase().includes(searchQuery.toLowerCase())
          );
          return (
            <section className="border border-slate-200 dark:border-slate-700 border-l-4 border-l-slate-400 dark:border-l-slate-500 rounded-lg overflow-hidden">
              <button
                onClick={() => {
                  const next = new Set(expandedCategories);
                  next.has('integration') ? next.delete('integration') : next.add('integration');
                  setExpandedCategories(next);
                }}
                className="w-full flex items-center gap-3 px-4 py-3 bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                {expandedCategories.has('integration') ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <Settings className="w-4 h-4 text-slate-500" />
                <div className="flex-1 text-left">
                  <span className="font-medium text-slate-900 dark:text-white">Integrations</span>
                  <span className="text-xs text-slate-500 ml-2">
                    {searchQuery ? `${filteredIntegrations.length} of ${integrations.length}` : `${integrations.length} connected`}
                  </span>
                  <p className="text-xs text-slate-400 dark:text-slate-500">API connections to external services (Datadog, Grafana, PagerDuty, etc.)</p>
                </div>
              </button>
              {expandedCategories.has('integration') && (
                <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {filteredIntegrations.map(renderCard)}
                </div>
              )}
            </section>
          );
        })()}

        {/* Custom Servers Section */}
        {(enabledServers.length > 0 || disabledServers.length > 0) && (() => {
          const filteredServers = [...enabledServers, ...disabledServers].filter(item =>
            item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            item.description?.toLowerCase().includes(searchQuery.toLowerCase())
          );
          const filteredEnabled = filteredServers.filter(m => m.enabled).length;
          const filteredDisabled = filteredServers.filter(m => !m.enabled).length;
          return (
            <section className="border border-slate-200 dark:border-slate-700 border-l-4 border-l-emerald-500 rounded-lg overflow-hidden">
                <button
                  onClick={() => {
                    const next = new Set(expandedCategories);
                    next.has('mcp') ? next.delete('mcp') : next.add('mcp');
                    setExpandedCategories(next);
                  }}
                  className="w-full flex items-center gap-3 px-4 py-3 bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  {expandedCategories.has('mcp') ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  <Server className="w-4 h-4 text-emerald-600" />
                  <div className="flex-1 text-left">
                    <span className="font-medium text-slate-900 dark:text-white">MCP Servers</span>
                    <span className="text-xs text-slate-500 ml-2">
                      {searchQuery ? `${filteredEnabled} enabled, ${filteredDisabled} disabled` : `${enabledServers.length} enabled, ${disabledServers.length} disabled`}
                    </span>
                    <p className="text-xs text-slate-400 dark:text-slate-500">Custom tool providers via Model Context Protocol</p>
                  </div>
                </button>
                {expandedCategories.has('mcp') && (
                  <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filteredServers.map(renderCard)}
                  </div>
                )}
              </section>
          );
        })()}

        {/* Skills Section — categorized tree */}
        {skillsCatalog.length > 0 && (() => {
          const enabledSkillCount = skillsCatalog.filter(s => s.enabled).length;
          const filteredSkillsByCategory: Record<string, typeof skillsCatalog> = {};
          skillsCatalog.forEach(skill => {
            if (
              !searchQuery ||
              skill.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
              skill.description?.toLowerCase().includes(searchQuery.toLowerCase())
            ) {
              const cat = skill.category || 'Other Integrations';
              if (!filteredSkillsByCategory[cat]) filteredSkillsByCategory[cat] = [];
              filteredSkillsByCategory[cat].push(skill);
            }
          });
          const filteredCount = Object.values(filteredSkillsByCategory).reduce((n, arr) => n + arr.length, 0);
          return (
            <section className="border border-slate-200 dark:border-slate-700 border-l-4 border-l-slate-400 rounded-lg overflow-hidden">
              {/* Top-level Skills header */}
              <button
                onClick={() => {
                  const next = new Set(expandedCategories);
                  next.has('skills') ? next.delete('skills') : next.add('skills');
                  setExpandedCategories(next);
                }}
                className="w-full flex items-center gap-3 px-4 py-3 bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                {expandedCategories.has('skills') ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <BookOpen className="w-4 h-4 text-slate-500" />
                <div className="flex-1 text-left">
                  <span className="font-medium text-slate-900 dark:text-white">Skills</span>
                  <span className="text-xs text-slate-500 ml-2">
                    {searchQuery
                      ? `${filteredCount} of ${skillsCatalog.length}`
                      : `${enabledSkillCount} enabled / ${skillsCatalog.length}`}
                  </span>
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    Knowledge loaded into agent context on-demand (methodologies, runbooks, query syntax)
                  </p>
                </div>
              </button>

              {expandedCategories.has('skills') && (
                <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                  {orderedSkillCategories.map(category => {
                    const catSkills = filteredSkillsByCategory[category];
                    if (!catSkills || catSkills.length === 0) return null;
                    const allSkillsInCat = skillsByCategory[category] || [];
                    const catEnabledCount = catSkills.filter(s => s.enabled).length;
                    const catTotal = catSkills.length;
                    const allEnabled = catEnabledCount === catTotal;
                    const noneEnabled = catEnabledCount === 0;
                    // tri-state: all / none / partial
                    const catKey = `skill-cat-${category}`;
                    const isCatExpanded = expandedCategories.has(catKey);

                    return (
                      <div key={category}>
                        {/* Category row */}
                        <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-50/60 dark:bg-slate-800/40">
                          <button
                            onClick={() => {
                              const next = new Set(expandedCategories);
                              next.has(catKey) ? next.delete(catKey) : next.add(catKey);
                              setExpandedCategories(next);
                            }}
                            className="flex items-center gap-2 flex-1 text-left min-w-0"
                          >
                            {isCatExpanded ? <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />}
                            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                              {category}
                            </span>
                            <span className="text-[10px] text-slate-400 ml-1">
                              {catEnabledCount} / {catTotal}
                            </span>
                          </button>
                          {/* Category toggle: tri-state */}
                          <button
                            onClick={() => toggleCategory(category, allSkillsInCat, !allEnabled)}
                            className={`p-1 rounded transition-colors flex-shrink-0 ${
                              allEnabled
                                ? 'text-green-600 hover:text-green-700'
                                : noneEnabled
                                ? 'text-slate-400 hover:text-slate-500'
                                : 'text-amber-500 hover:text-amber-600'
                            }`}
                            title={allEnabled ? 'Disable all in category' : noneEnabled ? 'Enable all in category' : 'Some enabled — enable all in category'}
                          >
                            {allEnabled ? (
                              <ToggleRight className="w-6 h-6" />
                            ) : noneEnabled ? (
                              <ToggleLeft className="w-6 h-6" />
                            ) : (
                              <MinusSquare className="w-6 h-6" />
                            )}
                          </button>
                        </div>

                        {/* Skill rows */}
                        {isCatExpanded && (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4">
                            {catSkills.map(skill => (
                              <div
                                key={skill.id}
                                className="flex items-start gap-3 p-3 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700"
                              >
                                <BookOpen className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
                                <div className="min-w-0 flex-1">
                                  <div className="font-medium text-sm text-slate-900 dark:text-white">{skill.name}</div>
                                  <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{skill.description}</div>
                                  {skill.required_integrations?.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-1.5">
                                      {skill.required_integrations.map((int: string) => (
                                        <span key={int} className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800/50 text-slate-600 dark:text-slate-400">
                                          {int}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                                <button
                                  onClick={() => toggleSkill(skill.id, skill.enabled)}
                                  className={`p-1 rounded transition-colors flex-shrink-0 ${
                                    skill.enabled
                                      ? 'text-green-600 hover:text-green-700'
                                      : 'text-slate-400 hover:text-slate-500'
                                  }`}
                                  title={skill.enabled ? 'Disable' : 'Enable'}
                                >
                                  {skill.enabled ? (
                                    <ToggleRight className="w-6 h-6" />
                                  ) : (
                                    <ToggleLeft className="w-6 h-6" />
                                  )}
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })()}

        {items.length === 0 && skillsCatalog.length === 0 && (
          <div className="text-center py-12">
            <Server className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500">No tools configured yet.</p>
          </div>
        )}
      </div>
    </TeamPageShell>

      {/* Configuration Modal */}
      {editingItem && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
              <div>
                <h2 className="font-semibold text-slate-900 dark:text-white">{editingItem.name}</h2>
                <p className="text-xs text-slate-500">{editingItem.description}</p>
              </div>
              <button
                onClick={() => setEditingItem(null)}
                className="p-1 text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-4 max-h-[60vh] overflow-auto">
              {Object.entries(editingItem.config_schema || {}).map(([fieldName, field]) => {
                // Check if this field is set at team level (can be cleared to inherit)
                const isTeamLevel = editingItem.config_sources?.[fieldName] === 'team';
                const hasValue = editValues[fieldName] !== undefined && editValues[fieldName] !== '';

                return (
                  <div key={fieldName}>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {field.display_name || fieldName}
                        {field.required && <span className="text-rose-600 ml-1">*</span>}
                      </label>
                      {/* Show source indicator and clear button for team-level values */}
                      {hasValue && (
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                            isTeamLevel
                              ? 'bg-emerald-100/60 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400'
                              : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
                          }`}>
                            {isTeamLevel ? 'team' : 'inherited'}
                          </span>
                          {isTeamLevel && (
                            <button
                              type="button"
                              onClick={async () => {
                                // Clear this field by sending __INHERIT__ sentinel
                                setSaving(true);
                                try {
                                  const patchRes = await fetch('/api/team/config', {
                                    method: 'PATCH',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                      integrations: {
                                        [editingItem.id]: {
                                          [fieldName]: '__INHERIT__'
                                        }
                                      }
                                    }),
                                  });
                                  if (!patchRes.ok) throw new Error('Failed to clear field');

                                  setMessage({ type: 'success', text: `Cleared ${fieldName} - will now inherit from org` });
                                  // Remove from local state and reload
                                  const newValues = { ...editValues };
                                  delete newValues[fieldName];
                                  setEditValues(newValues);
                                  loadItems();
                                } catch (error: any) {
                                  setMessage({ type: 'error', text: error.message });
                                } finally {
                                  setSaving(false);
                                }
                              }}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100/60 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100/80 dark:hover:bg-emerald-500/40"
                              title="Clear this value to inherit from organization settings"
                            >
                              Clear (inherit)
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {field.allowed_values ? (
                      <select
                        value={editValues[fieldName] || field.default || ''}
                        onChange={(e) => setEditValues({ ...editValues, [fieldName]: e.target.value })}
                        className="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
                      >
                        {field.allowed_values.map(v => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    ) : (
                      <div className="relative">
                        <input
                          type={field.type === 'secret' && !showSecrets[fieldName] ? 'password' : 'text'}
                          value={editValues[fieldName] || ''}
                          onChange={(e) => setEditValues({ ...editValues, [fieldName]: e.target.value })}
                          placeholder={field.placeholder || field.default || ''}
                          className="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
                        />
                        {field.type === 'secret' && (
                          <button
                            type="button"
                            onClick={() => setShowSecrets({ ...showSecrets, [fieldName]: !showSecrets[fieldName] })}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400"
                          >
                            {showSecrets[fieldName] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        )}
                      </div>
                    )}

                    {field.description && (
                      <p className="text-xs text-slate-500 mt-1">{field.description}</p>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="p-4 border-t border-slate-200 dark:border-slate-700 flex justify-end gap-3">
              <button
                onClick={() => setEditingItem(null)}
                className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900"
              >
                Cancel
              </button>
              <button
                onClick={saveConfig}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-emerald-100/50 text-emerald-700 rounded-lg hover:bg-emerald-100/80 disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tool Filtering Modal */}
      {filteringMcp && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-full max-w-2xl">
            <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
              <div>
                <h2 className="font-semibold text-slate-900 dark:text-white">Filter Tools - {filteringMcp.name}</h2>
                <p className="text-xs text-slate-500">Select which tools from this MCP server should be available</p>
              </div>
              <button
                onClick={() => setFilteringMcp(null)}
                className="p-1 text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-4 max-h-[60vh] overflow-auto">
              {/* Select All / Deselect All */}
              <div className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-700 rounded-lg">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  {selectedTools.size === (filteringMcp.tools?.length || 0)
                    ? `All ${filteringMcp.tools?.length || 0} tools selected`
                    : `${selectedTools.size} of ${filteringMcp.tools?.length || 0} tools selected`
                  }
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      // Handle both string and object arrays
                      const toolNames = filteringMcp.tools?.map(t =>
                        typeof t === 'string' ? t : (t.name || t.display_name)
                      ) || [];
                      setSelectedTools(new Set(toolNames));
                    }}
                    className="text-xs px-2 py-1 rounded bg-emerald-100/60 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 hover:opacity-80"
                  >
                    Select All
                  </button>
                  <button
                    onClick={() => {
                      setSelectedTools(new Set());
                    }}
                    className="text-xs px-2 py-1 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:opacity-80"
                  >
                    Deselect All
                  </button>
                </div>
              </div>

              {/* Tool List */}
              <div className="space-y-2">
                {filteringMcp.tools?.map((tool: any, idx: number) => {
                  // Handle both string arrays and object arrays
                  const toolName = typeof tool === 'string' ? tool : (tool.name || tool.display_name);
                  const toolDisplayName = typeof tool === 'string' ? tool : (tool.display_name || tool.name);
                  const toolDesc = typeof tool === 'string' ? undefined : tool.description;
                  const toolCategory = typeof tool === 'string' ? undefined : tool.category;

                  return (
                    <label
                      key={toolName || idx}
                      className="flex items-start gap-3 p-3 rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedTools.has(toolName)}
                        onChange={(e) => {
                          const next = new Set(selectedTools);
                          if (e.target.checked) {
                            next.add(toolName);
                          } else {
                            next.delete(toolName);
                          }
                          setSelectedTools(next);
                        }}
                        className="mt-1 w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-slate-900 dark:text-white">
                          {toolDisplayName}
                        </div>
                        {toolDesc && (
                          <div className="text-xs text-slate-500 mt-0.5">
                            {toolDesc}
                          </div>
                        )}
                        {toolCategory && (
                          <div className="mt-1">
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100/50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400">
                              {toolCategory}
                            </span>
                          </div>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="p-4 border-t border-slate-200 dark:border-slate-700 flex justify-end gap-2">
              <button
                onClick={() => setFilteringMcp(null)}
                className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  if (!filteringMcp) return;

                  setSaving(true);
                  try {
                    // Calculate enabled_tools
                    const enabledTools = selectedTools.size === filteringMcp.tools?.length
                      ? ['*']  // All tools selected = wildcard
                      : Array.from(selectedTools);

                    // Debug: Log what we're sending
                    console.log('🔍 Debug - selectedTools Set:', selectedTools);
                    console.log('🔍 Debug - enabledTools array:', enabledTools);
                    console.log('🔍 Debug - enabledTools types:', enabledTools.map(t => typeof t));

                    // IMPORTANT: Only send the specific MCP and field being updated
                    // Don't send the entire mcp_servers dict to avoid overwriting inherited configs
                    const patchRes = await fetch('/api/team/config', {
                      method: 'PATCH',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        mcp_servers: {
                          [filteringMcp.id]: {
                            enabled_tools: enabledTools
                          }
                        }
                      }),
                    });

                    if (!patchRes.ok) {
                      const errorText = await patchRes.text();
                      let errorMsg = 'Failed to update tools filter';
                      try {
                        const errorData = JSON.parse(errorText);
                        errorMsg = errorData.detail || errorData.error || errorMsg;
                      } catch {
                        errorMsg = errorText || errorMsg;
                      }
                      throw new Error(errorMsg);
                    }

                    setMessage({ type: 'success', text: `Tool filter updated for ${filteringMcp.name}` });
                    setFilteringMcp(null);
                    loadItems();
                  } catch (error: any) {
                    console.error('Tool filter save error:', error);
                    setMessage({ type: 'error', text: error.message });
                  } finally {
                    setSaving(false);
                  }
                }}
                disabled={saving}
                className="px-4 py-2 bg-emerald-100/50 text-emerald-700 rounded-lg hover:bg-emerald-100/80 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                {saving ? 'Saving...' : 'Save Filter'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Custom Server Modal */}
      {showAddCustomModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-full max-w-2xl">
            <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
              <div>
                <h2 className="font-semibold text-slate-900 dark:text-white">Add Custom MCP Server</h2>
                <p className="text-xs text-slate-500">Add a custom Model Context Protocol server for your agents</p>
              </div>
              <button
                onClick={() => {
                  setShowAddCustomModal(false);
                  setNewServerForm({
                    name: '',
                    description: '',
                    command: '',
                    args: '',
                    env: '',
                  });
                  setPreviewedTools(null);
                  setMessage(null);
                }}
                className="p-1 text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-4 max-h-[70vh] overflow-auto">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Name <span className="text-rose-600">*</span>
                </label>
                <input
                  type="text"
                  value={newServerForm.name}
                  onChange={(e) => setNewServerForm({ ...newServerForm, name: e.target.value })}
                  placeholder="e.g., Slack MCP"
                  className="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
                />
                <p className="text-xs text-slate-500 mt-1">A friendly name for this MCP server</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Description
                </label>
                <input
                  type="text"
                  value={newServerForm.description}
                  onChange={(e) => setNewServerForm({ ...newServerForm, description: e.target.value })}
                  placeholder="e.g., Provides Slack channel and message management tools"
                  className="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
                />
                <p className="text-xs text-slate-500 mt-1">Brief description of what this MCP provides</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Command <span className="text-rose-600">*</span>
                </label>
                <input
                  type="text"
                  value={newServerForm.command}
                  onChange={(e) => setNewServerForm({ ...newServerForm, command: e.target.value })}
                  placeholder="e.g., npx or python or /path/to/executable"
                  className="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm font-mono"
                />
                <p className="text-xs text-slate-500 mt-1">The executable command to start the MCP server</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Arguments
                </label>
                <textarea
                  value={newServerForm.args}
                  onChange={(e) => setNewServerForm({ ...newServerForm, args: e.target.value })}
                  placeholder="One argument per line, e.g.:&#10;-m&#10;mcp_server_slack"
                  rows={4}
                  className="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm font-mono"
                />
                <p className="text-xs text-slate-500 mt-1">Command arguments (one per line)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Environment Variables
                </label>
                <textarea
                  value={newServerForm.env}
                  onChange={(e) => setNewServerForm({ ...newServerForm, env: e.target.value })}
                  placeholder="One variable per line in KEY=VALUE format, e.g.:&#10;SLACK_TOKEN=xoxb-your-token&#10;SLACK_TEAM_ID=T1234567"
                  rows={5}
                  className="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm font-mono"
                />
                <p className="text-xs text-slate-500 mt-1">Environment variables in KEY=VALUE format (one per line)</p>
              </div>

              <div className="bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 rounded-lg p-3">
                <p className="text-xs text-slate-700 dark:text-slate-300">
                  <strong>Tip:</strong> MCP servers are executables that communicate via stdio. Common patterns:
                </p>
                <ul className="text-xs text-slate-600 dark:text-slate-400 mt-2 space-y-1 ml-4 list-disc">
                  <li><code className="bg-slate-100 dark:bg-slate-700 px-1 py-0.5 rounded">npx -y @modelcontextprotocol/server-name</code></li>
                  <li><code className="bg-slate-100 dark:bg-slate-700 px-1 py-0.5 rounded">python -m mcp_server_module</code></li>
                  <li><code className="bg-slate-100 dark:bg-slate-700 px-1 py-0.5 rounded">node /path/to/server.js</code></li>
                </ul>
              </div>

              {/* Preview Tools Section */}
              {previewedTools && previewedTools.success && (
                <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
                  <div className="bg-slate-50 dark:bg-slate-700/50 px-3 py-2 border-b border-slate-200 dark:border-slate-700">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium text-slate-900 dark:text-white">
                        Discovered Tools ({previewedTools.tool_count})
                      </h3>
                      {previewedTools.warnings.length > 0 && (
                        <div className="flex items-center gap-1 text-xs text-yellow-600 dark:text-yellow-400">
                          <AlertTriangle className="w-3 h-3" />
                          {previewedTools.warnings.length} warning{previewedTools.warnings.length !== 1 ? 's' : ''}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Warnings */}
                  {previewedTools.warnings.length > 0 && (
                    <div className="bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800 px-3 py-2">
                      {previewedTools.warnings.map((warning, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-xs text-yellow-800 dark:text-yellow-300">
                          <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                          <span>{warning}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Tools List */}
                  <div className="max-h-60 overflow-auto p-3 space-y-2">
                    {previewedTools.tools.length === 0 ? (
                      <p className="text-xs text-slate-500 text-center py-4">No tools discovered</p>
                    ) : (
                      (() => {
                        // Group tools by category
                        const toolsByCategory = previewedTools.tools.reduce((acc, tool) => {
                          const cat = tool.category || 'Other';
                          if (!acc[cat]) acc[cat] = [];
                          acc[cat].push(tool);
                          return acc;
                        }, {} as Record<string, typeof previewedTools.tools>);

                        return Object.entries(toolsByCategory).map(([category, tools]) => (
                          <div key={category} className="space-y-1">
                            <h4 className="text-xs font-medium text-slate-600 dark:text-slate-400 uppercase tracking-wide">
                              {category} ({tools.length})
                            </h4>
                            {tools.map((tool, idx) => (
                              <div
                                key={idx}
                                className="bg-slate-50 dark:bg-slate-700/50 rounded px-2 py-1.5 border border-slate-200 dark:border-slate-600"
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <div className="flex-1 min-w-0">
                                    <p className="text-xs font-mono text-slate-900 dark:text-white truncate">
                                      {tool.display_name}
                                    </p>
                                    {tool.description && (
                                      <p className="text-xs text-slate-500 line-clamp-1 mt-0.5">
                                        {tool.description}
                                      </p>
                                    )}
                                  </div>
                                  <CheckCircle className="w-3 h-3 text-green-500 flex-shrink-0 mt-0.5" />
                                </div>
                              </div>
                            ))}
                          </div>
                        ));
                      })()
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-slate-200 dark:border-slate-700 flex justify-between gap-3">
              <button
                onClick={previewMCPServer}
                disabled={previewingTools || !newServerForm.command}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Eye className="w-4 h-4" />
                {previewingTools ? 'Previewing...' : 'Preview Tools'}
              </button>
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setShowAddCustomModal(false);
                    setNewServerForm({
                      name: '',
                      description: '',
                      command: '',
                      args: '',
                      env: '',
                    });
                    setPreviewedTools(null);
                    setMessage(null);
                  }}
                  className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900"
                >
                  Cancel
                </button>
                <button
                  onClick={saveCustomServer}
                  disabled={saving || !newServerForm.name || !newServerForm.command}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-emerald-100/50 text-emerald-700 rounded-lg hover:bg-emerald-100/80 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Plus className="w-4 h-4" />
                  {saving ? 'Adding...' : 'Add MCP Server'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
