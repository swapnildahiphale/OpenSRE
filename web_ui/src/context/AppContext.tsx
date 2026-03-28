'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { InvestigationSession, ChatMessage } from '@/types/chat';

// Types
export type Integration = {
  id: string;
  name: string;
  category: string;
  status: 'connected' | 'available'; // Global status (Admin Allowlist)
  enabledForTeams: string[]; // Which teams have this enabled
  description?: string;
  iconSlug?: string; 
  config?: Record<string, string>;
  isCustom?: boolean; 
  mcpUrl?: string;    
};

export type Incident = {
  id: string;
  title: string;
  status: 'Resolved' | 'Analyzing' | 'Active' | 'Monitoring';
  severity: 'SEV-1' | 'SEV-2' | 'SEV-3';
  time: string;
  duration?: string;
  aiScore?: number | null;
  aiVerdict?: 'Accurate' | 'Helpful' | 'Inaccurate' | null;
  team: string;
};

export type Team = {
    id: string;
    name: string;
    slackChannel: string;
    slackChannelUrl: string;
}

export type Document = {
    id: string;
    title: string;
    type: 'confluence' | 'google_doc' | 'notion' | 'post_mortem' | 'github_md';
    url: string;
    lastUpdated: string;
    included: boolean;
    source: string;
}

export type ToolPrompt = {
    id: string;
    toolName: string;
    description: string;
    defaultPrompt: string;
    teamPrompt?: string; 
    isOverridden: boolean;
    isPublished: boolean;
    enabled: boolean; // New field for per-team tool toggle
    integrationId?: string; // Link back to integration
}

type AppState = {
  integrations: Integration[];
  incidents: Incident[];
  teams: Team[];
  currentTeam: Team;
  documents: Record<string, Document[]>; 
  toolPrompts: Record<string, ToolPrompt[]>; 
  activeSession: InvestigationSession | null; // The chat session for the demo
  
  // Actions
  toggleIntegration: (id: string, config?: Record<string, string>) => void;
  addCustomIntegration: (integration: Integration) => void; 
  disconnectIntegration: (id: string) => void;
  updateIncidentStatus: (id: string, status: Incident['status']) => void;
  addIncident: (incident: Incident) => void;
  setCurrentTeam: (teamId: string) => void;
  settings: Record<string, boolean>;
  toggleSetting: (key: string) => void;
  
  toggleDocument: (docId: string) => void;
  addDocument: (doc: Document) => void;
  deleteDocument: (docId: string) => void;

  toggleTool: (toolId: string) => void;
  updateToolPrompt: (toolId: string, prompt: string) => void;
  resetToolPrompt: (toolId: string) => void;
  publishToolPrompt: (toolId: string) => void;
  
  addToolPrompt: (tool: ToolPrompt) => void; // New Action

  // Simulation Actions
  startSimulation: () => void;
  advanceSimulation: (message: ChatMessage) => void;
};

const AppContext = createContext<AppState | undefined>(undefined);

export const initialIntegrations: Integration[] = [
  { id: 'aws', name: 'Amazon AWS', category: 'Infrastructure', status: 'connected', enabledForTeams: ['global', 'payment', 'user'], description: 'Ingest metrics and logs from CloudWatch.', iconSlug: 'amazonaws' },
  { id: 'splunk', name: 'Splunk', category: 'Telemetry', status: 'connected', enabledForTeams: ['global', 'payment'], description: 'Enterprise log aggregation.', iconSlug: 'splunk' },
  { id: 'pagerduty', name: 'PagerDuty', category: 'Project Management', status: 'connected', enabledForTeams: ['global', 'payment', 'user', 'data'], description: 'On-call alerting and incident tracking.', iconSlug: 'pagerduty' },
  { id: 'slack', name: 'Slack', category: 'Chat', status: 'connected', enabledForTeams: ['global', 'payment', 'user', 'data'], description: 'ChatOps and notifications.', iconSlug: 'slack' },
  { id: 'github', name: 'GitHub', category: 'Code', status: 'connected', enabledForTeams: ['global', 'payment', 'user'], description: 'Source code, PRs, and deployments.', iconSlug: 'github' },
  { id: 'k8s', name: 'Kubernetes', category: 'Infrastructure', status: 'connected', enabledForTeams: ['global', 'payment'], description: 'Cluster health and pod metrics.', iconSlug: 'kubernetes' },
  { id: 'wandb', name: 'Weights & Biases', category: 'ML/AI', status: 'connected', enabledForTeams: ['data'], description: 'Model training and evaluation tracking.', iconSlug: 'weightsandbiases' },
  
  { id: 'grafana', name: 'Grafana', category: 'Telemetry', status: 'connected', enabledForTeams: ['payment'], description: 'Visualizing metrics dashboards.', iconSlug: 'grafana' },
  { id: 'datadog', name: 'Datadog', category: 'Telemetry', status: 'connected', enabledForTeams: [], description: 'Cloud monitoring as a service.', iconSlug: 'datadog' },
  { id: 'prometheus', name: 'Prometheus', category: 'Telemetry', status: 'available', enabledForTeams: [], description: 'Open-source monitoring system.', iconSlug: 'prometheus' },
  { id: 'notion', name: 'Notion', category: 'Project Management', status: 'connected', enabledForTeams: ['user'], description: 'Wiki and project docs.', iconSlug: 'notion' },
  { id: 'elastic', name: 'Elastic', category: 'Telemetry', status: 'connected', enabledForTeams: ['data'], description: 'Search and analytics engine.', iconSlug: 'elastic' },
  { id: 'dynatrace', name: 'Dynatrace', category: 'Telemetry', status: 'available', enabledForTeams: [], iconSlug: 'dynatrace' },
  { id: 'gcp', name: 'Google Cloud', category: 'Infrastructure', status: 'available', enabledForTeams: [], iconSlug: 'googlecloud' },
  { id: 'sentry', name: 'Sentry', category: 'Telemetry', status: 'connected', enabledForTeams: ['payment', 'user'], description: 'Error tracking and performance monitoring.', iconSlug: 'sentry' },
  { id: 'newrelic', name: 'New Relic', category: 'Telemetry', status: 'available', enabledForTeams: [], iconSlug: 'newrelic' },
  { id: 'linear', name: 'Linear', category: 'Project Management', status: 'available', enabledForTeams: [], iconSlug: 'linear' },
  { id: 'servicenow', name: 'ServiceNow', category: 'Project Management', status: 'connected', enabledForTeams: ['global'], description: 'IT Service Management.', iconSlug: 'servicenow' },
  
  { id: 'snowflake', name: 'Snowflake', category: 'Infrastructure', status: 'connected', enabledForTeams: ['data'], description: 'Cloud data platform.', iconSlug: 'snowflake' },
  { id: 'confluence', name: 'Confluence', category: 'Project Management', status: 'connected', enabledForTeams: ['global', 'payment'], description: 'Remote-friendly team workspace.', iconSlug: 'confluence' },
  { id: 'gitlab', name: 'GitLab', category: 'Code', status: 'connected', enabledForTeams: [], description: 'DevOps platform.', iconSlug: 'gitlab' },
  { id: 'azure', name: 'Azure', category: 'Infrastructure', status: 'connected', enabledForTeams: [], description: 'Cloud computing services.', iconSlug: 'microsoftazure' },
  { id: 'jenkins', name: 'Jenkins', category: 'Code', status: 'connected', enabledForTeams: [], description: 'Open source automation server.', iconSlug: 'jenkins' },
  { id: 'jira', name: 'Jira', category: 'Project Management', status: 'connected', enabledForTeams: ['global', 'payment', 'user'], description: 'Issue and project tracking.', iconSlug: 'jira' },
];

const initialIncidents: Incident[] = [
  {
    id: 'INC-2023-001',
    title: 'High Latency in Checkout Service',
    status: 'Analyzing',
    severity: 'SEV-2',
    time: '2m ago',
    duration: '2m',
    aiScore: null,
    aiVerdict: null,
    team: 'Payment Team'
  },
  {
    id: 'INC-2023-002',
    title: 'Database Connection Pool Exhaustion',
    status: 'Resolved',
    severity: 'SEV-1',
    time: '1 day ago',
    duration: '45m',
    aiScore: 88,
    aiVerdict: 'Helpful',
    team: 'User Service Team'
  },
  {
    id: 'INC-2023-003',
    title: 'API Gateway 5xx Spikes',
    status: 'Resolved',
    severity: 'SEV-2',
    time: '2 days ago',
    duration: '15m',
    aiScore: 92,
    aiVerdict: 'Accurate',
    team: 'Global'
  }
];

const initialTeams: Team[] = [
    { id: 'global', name: 'Global', slackChannel: '#sre-global', slackChannelUrl: '#' },
    { id: 'payment', name: 'Payment Team', slackChannel: '#team-payments', slackChannelUrl: '#' },
    { id: 'user', name: 'User Service Team', slackChannel: '#team-users', slackChannelUrl: '#' },
    { id: 'data', name: 'Data Platform', slackChannel: '#data-platform', slackChannelUrl: '#' },
];

// Mock Documents
const initialDocs: Record<string, Document[]> = {
    'payment': [
        { id: 'd1', title: 'Payment Gateway v2 Migration Guide', type: 'confluence', url: '#', lastUpdated: '2d ago', included: true, source: 'Confluence' },
        { id: 'd2', title: 'PCI Compliance Checklist 2024', type: 'google_doc', url: '#', lastUpdated: '1w ago', included: true, source: 'G-Drive' },
        { id: 'd3', title: 'Post-Mortem: Black Friday Outage', type: 'post_mortem', url: '#', lastUpdated: '1mo ago', included: false, source: 'Notion' },
    ],
    'user': [
        { id: 'd4', title: 'Auth0 Implementation Details', type: 'notion', url: '#', lastUpdated: '3d ago', included: true, source: 'Notion' },
    ],
    'data': [
         { id: 'd6', title: 'Snowflake Query Optimization Guide', type: 'notion', url: '#', lastUpdated: '5d ago', included: true, source: 'Notion' },
         { id: 'd7', title: 'Airflow DAG Best Practices', type: 'confluence', url: '#', lastUpdated: '2w ago', included: true, source: 'Confluence' },
    ],
    'global': [
        { id: 'd5', title: 'Incident Response Playbook', type: 'confluence', url: '#', lastUpdated: '1d ago', included: true, source: 'Confluence' },
    ]
};

// Mock Tool Prompts
const initialToolPrompts: Record<string, ToolPrompt[]> = {
    'payment': [
        { 
            id: 't1', 
            toolName: 'Restart ECS Service', 
            description: 'Restarts a service container in ECS.', 
            defaultPrompt: 'Analyze the service health metrics first. If CPU > 90% or Memory > 85% for > 5 mins, and no active deployments are visible, proceed with restart.',
            teamPrompt: 'For Payment Service, ALWAYS check pending transaction queue depth. If > 0, DO NOT RESTART without human approval.',
            isOverridden: true,
            isPublished: false,
            enabled: true,
            integrationId: 'aws'
        },
        { 
            id: 't2', 
            toolName: 'Query Snowflake', 
            description: 'Runs read-only SQL queries.', 
            defaultPrompt: 'Construct valid SQL to query business metrics. Limit results to 100 rows.',
            teamPrompt: '',
            isOverridden: false,
            isPublished: false,
            enabled: true,
            integrationId: 'snowflake'
        },
        {
            id: 't3',
            toolName: 'Splunk Log Search',
            description: 'Search logs in Splunk.',
            defaultPrompt: 'Generate SPL queries to find errors related to the service. Filter by `error` or `exception`.',
            teamPrompt: '',
            isOverridden: false,
            isPublished: false,
            enabled: true,
            integrationId: 'splunk'
        }
    ],
    'data': [
         { 
            id: 't5', 
            toolName: 'Restart Airflow DAG', 
            description: 'Restarts a failed Airflow DAG.', 
            defaultPrompt: 'Check for dependent upstream tasks before restarting. If retry count > 3, escalate.',
            teamPrompt: '',
            isOverridden: false,
            isPublished: false,
            enabled: true,
            integrationId: 'airflow'
        },
        { 
            id: 't6', 
            toolName: 'Query Snowflake (Data Admin)', 
            description: 'Runs SQL queries with admin privileges.', 
            defaultPrompt: 'Ensure query complexity does not exceed warehouse limits. Use `Medium` warehouse by default.',
            teamPrompt: 'For Data Platform, always check query cost estimates before execution.',
            isOverridden: true,
            isPublished: false,
            enabled: true,
            integrationId: 'snowflake'
        },
    ],
    'global': [
        {
            id: 't4',
            toolName: 'Jira Create Ticket',
            description: 'Creates a new Jira issue.',
            defaultPrompt: 'Create a ticket with clear Summary and Description. Set Priority based on incident severity.',
            teamPrompt: '',
            isOverridden: false,
            isPublished: true,
            enabled: true,
            integrationId: 'jira'
        }
    ]
};

// Initial Chat Session Data
const initialSession: InvestigationSession = {
    id: 'INC-2023-001',
    title: 'High Latency in Checkout Service',
    status: 'active',
    messages: [
        {
            id: 'msg-1',
            type: 'alert',
            sender: 'PagerDuty',
            timestamp: '10:15 PM',
            content: '[CRITICAL] Transaction Authorization Latency Spike\n\nService: payment-gateway-api\nCluster: c1-useast1-prod-04\nUrgency: Critical\nImpact: Auth Latency p99 > 5s',
            metadata: {
                service: 'payment-gateway-api',
                cluster: 'c1-useast1-prod-04',
                severity: 'Critical',
                link: '#'
            }
        }
    ]
};

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [integrations, setIntegrations] = useState<Integration[]>(initialIntegrations);
  const [incidents, setIncidents] = useState<Incident[]>(initialIncidents);
  const [teams] = useState<Team[]>(initialTeams);
  const [currentTeam, setCurrentTeamState] = useState<Team>(initialTeams[1]); // Default to Payment Team
  
  const [documents, setDocuments] = useState(initialDocs);
  const [toolPrompts, setToolPrompts] = useState(initialToolPrompts);
  const [activeSession, setActiveSession] = useState<InvestigationSession | null>(initialSession);

  const [settings, setSettings] = useState<Record<string, boolean>>({
    humanApproval: true,
    piiRedaction: true,
  });

  const toggleIntegration = (id: string, config?: Record<string, string>) => {
    setIntegrations(prev => prev.map(int => {
      if (int.id === id) {
        // If we are "connecting", we add the current team to enabledForTeams
        const isEnabledForTeam = int.enabledForTeams.includes(currentTeam.id);
        
        let newTeams = int.enabledForTeams;
        if (config || !isEnabledForTeam) {
            // Enabling
            if (!isEnabledForTeam) newTeams = [...newTeams, currentTeam.id];
            
            // Mock: Inject tools if enabling
            if (!isEnabledForTeam) {
                injectToolsForIntegration(id, currentTeam.id);
            }

            return { ...int, status: 'connected', enabledForTeams: newTeams, config: config || int.config };
        } else {
            // Disabling
            // Don't remove tools for now to keep demo simple, or we could filter them out
            return { ...int, enabledForTeams: newTeams.filter(t => t !== currentTeam.id) };
        }
      }
      return int;
    }));
  };

  const injectToolsForIntegration = (integrationId: string, teamId: string) => {
      // Mock injection of tools
      let newTools: ToolPrompt[] = [];
      
      if (integrationId === 'jira') {
          newTools.push({
              id: `jira-${Date.now()}`,
              toolName: 'Jira Search Issues',
              description: 'Search for existing tickets.',
              defaultPrompt: 'Use JQL to find duplicates before creating new tickets.',
              isOverridden: false,
              isPublished: false,
              enabled: true,
              integrationId: 'jira'
          });
      } else if (integrationId === 'pagerduty') {
          newTools.push({
              id: `pd-${Date.now()}`,
              toolName: 'PagerDuty Acknowledge',
              description: 'Acknowledge an incident.',
              defaultPrompt: 'Acknowledge immediately upon receipt if valid.',
              isOverridden: false,
              isPublished: false,
              enabled: true,
              integrationId: 'pagerduty'
          });
      }

      if (newTools.length > 0) {
          setToolPrompts(prev => ({
              ...prev,
              [teamId]: [...(prev[teamId] || []), ...newTools]
          }));
      }
  };

  const addCustomIntegration = (integration: Integration) => {
    setIntegrations(prev => [...prev, { ...integration, enabledForTeams: [currentTeam.id] }]);
  };

  const disconnectIntegration = (id: string) => {
      // For this demo, "Disconnect" in the UI usually means "Disable for my team"
      toggleIntegration(id);
  };

  const updateIncidentStatus = (id: string, status: Incident['status']) => {
    setIncidents(prev => prev.map(inc => inc.id === id ? { ...inc, status } : inc));
  };

  const addIncident = (incident: Incident) => {
      setIncidents(prev => [incident, ...prev]);
  };

  const toggleSetting = (key: string) => {
      setSettings(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const setCurrentTeam = (teamId: string) => {
      const team = teams.find(t => t.id === teamId);
      if (team) setCurrentTeamState(team);
  };

  // Doc Actions
  const toggleDocument = (docId: string) => {
      setDocuments(prev => {
          const teamDocs = prev[currentTeam.id] || [];
          return {
              ...prev,
              [currentTeam.id]: teamDocs.map(d => d.id === docId ? { ...d, included: !d.included } : d)
          };
      });
  };

  const addDocument = (doc: Document) => {
       setDocuments(prev => ({
            ...prev,
            [currentTeam.id]: [doc, ...(prev[currentTeam.id] || [])]
       }));
  };

  const deleteDocument = (docId: string) => {
       setDocuments(prev => ({
            ...prev,
            [currentTeam.id]: (prev[currentTeam.id] || []).filter(d => d.id !== docId)
       }));
  };

  // Tool Actions
  const toggleTool = (toolId: string) => {
      setToolPrompts(prev => ({
          ...prev,
          [currentTeam.id]: (prev[currentTeam.id] || []).map(t => 
              t.id === toolId ? { ...t, enabled: !t.enabled } : t
          )
      }));
  };

  const updateToolPrompt = (toolId: string, prompt: string) => {
      setToolPrompts(prev => ({
          ...prev,
          [currentTeam.id]: (prev[currentTeam.id] || []).map(t => 
              t.id === toolId ? { ...t, teamPrompt: prompt, isOverridden: true } : t
          )
      }));
  };

  const resetToolPrompt = (toolId: string) => {
      setToolPrompts(prev => ({
          ...prev,
          [currentTeam.id]: (prev[currentTeam.id] || []).map(t => 
              t.id === toolId ? { ...t, teamPrompt: '', isOverridden: false } : t
          )
      }));
  };

  const publishToolPrompt = (toolId: string) => {
      setToolPrompts(prev => ({
          ...prev,
          [currentTeam.id]: (prev[currentTeam.id] || []).map(t => 
              t.id === toolId ? { ...t, isPublished: true } : t
          )
      }));
  };

  const addToolPrompt = (tool: ToolPrompt) => {
      setToolPrompts(prev => ({
          ...prev,
          [currentTeam.id]: [tool, ...(prev[currentTeam.id] || [])]
      }));
  };

  // Simulation Actions
  const startSimulation = () => {
      setActiveSession(initialSession);
  };

  const advanceSimulation = (message: ChatMessage) => {
      setActiveSession(prev => {
          if (!prev) return null;
          // Prevent duplicates
          if (prev.messages.find(m => m.id === message.id)) return prev;
          return {
              ...prev,
              messages: [...prev.messages, message]
          };
      });
  };


  return (
    <AppContext.Provider value={{
      integrations,
      incidents,
      teams,
      currentTeam,
      documents,
      toolPrompts,
      activeSession,
      toggleIntegration,
      addCustomIntegration,
      disconnectIntegration,
      updateIncidentStatus,
      addIncident,
      setCurrentTeam,
      settings,
      toggleSetting,
      toggleDocument,
      addDocument,
      deleteDocument,
      toggleTool,
      updateToolPrompt,
      resetToolPrompt,
      publishToolPrompt,
      addToolPrompt, // Exported
      startSimulation,
      advanceSimulation
    }}>
      {children}
    </AppContext.Provider>
  );
}

export const useApp = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
