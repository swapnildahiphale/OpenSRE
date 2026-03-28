export type ToolCall = {
    id: string;
    toolName: string;
    toolIcon: string; // e.g., 'newrelic', 'splunk', 'jenkins', 'kubernetes'
    command: string; // The "code" or query run
    args?: Record<string, any>;
    status: 'running' | 'completed' | 'failed';
    result?: any; // structured result data
    duration?: string;
};

export type ChatMessage = {
    id: string;
    type: 'alert' | 'agent_thought' | 'tool_step' | 'user_message' | 'conclusion';
    // Allow known senders but also support arbitrary agent/team names (e.g. "Payment Bot")
    // without breaking production builds.
    sender: 'OpenSRE' | 'PagerDuty' | 'User' | 'System' | (string & {});
    timestamp: string;
    content?: string; // Markdown text
    toolCall?: ToolCall; // If type is tool_step
    metadata?: any; // Extra data for alerts (severity, urgency, etc) or memory linkage
};

export type InvestigationSession = {
    id: string;
    title: string;
    status: 'active' | 'resolved' | 'monitoring';
    messages: ChatMessage[];
    summary?: string;
    confidenceScore?: number;
    policyUsed?: string;
};
