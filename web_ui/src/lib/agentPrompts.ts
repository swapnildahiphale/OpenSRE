// Shared helpers for the canonical nested agent-prompt config shape
// (agents.{id}.prompt.system) — used by the team prompt editor and the admin
// org-defaults editor so the read/write shape lives in exactly one place.

export type AgentsMap = Record<string, any>;

export interface AgentListItem {
  agent: string;
  displayName: string;
  description: string;
}

/** True when a stored system prompt counts as "set" (a non-empty string). */
export function isPromptSet(system: unknown): system is string {
  return typeof system === 'string' && system.length > 0;
}

/** Read agents.{id}.prompt.system out of a node/effective config agents map. */
export function readAgentSystem(agents: AgentsMap | undefined, agent: string): unknown {
  return agents?.[agent]?.prompt?.system;
}

/** Build the canonical { agents: { id: { prompt: { system } } } } config patch. */
export function agentPromptPatch(agent: string, system: string | null) {
  return { agents: { [agent]: { prompt: { system } } } };
}

/** Derive the {agent, displayName, description} list from an effective agents map. */
export function buildAgentList(agents: AgentsMap): AgentListItem[] {
  return Object.keys(agents).map((agent) => ({
    agent,
    displayName: agents[agent]?.display_name || agent,
    description: agents[agent]?.description || '',
  }));
}
