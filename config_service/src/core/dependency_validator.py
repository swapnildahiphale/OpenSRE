"""
Dependency validation for configuration changes.

Validates that:
- Tools aren't disabled if agents use them
- Integrations aren't disabled if tools depend on them
- Sub-agents aren't disabled if agents use them
- MCPs aren't disabled if agents use them

This prevents invalid configurations that would cause runtime failures.
"""

from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class DependencyError(Exception):
    """Raised when a dependency constraint is violated."""

    def __init__(self, message: str, dependents: List[str]):
        super().__init__(message)
        self.message = message
        self.dependents = dependents


def validate_integration_dependencies(
    effective_config: Dict[str, Any],
    changed_integration_id: str,
    new_enabled_state: bool,
) -> Optional[DependencyError]:
    """
    Validate that disabling an integration won't break tools.

    Args:
        effective_config: The full effective config after merge
        changed_integration_id: ID of integration being changed
        new_enabled_state: New enabled state (True/False)

    Returns:
        DependencyError if validation fails, None if valid
    """
    if new_enabled_state:
        # Enabling is always safe
        return None

    # Check if any enabled tools depend on this integration
    tools = effective_config.get("tools", {})
    dependent_tools = []

    for tool_id, tool_config in tools.items():
        if not isinstance(tool_config, dict):
            continue

        if not tool_config.get("enabled"):
            continue

        # Check if this tool depends on the integration
        requires = tool_config.get("requires_integration")
        if requires == changed_integration_id:
            dependent_tools.append(tool_id)

    if dependent_tools:
        msg = (
            f"Cannot disable integration '{changed_integration_id}' because "
            f"the following tools depend on it: {', '.join(dependent_tools)}. "
            f"Please disable these tools first."
        )
        return DependencyError(msg, dependent_tools)

    return None


def validate_tool_dependencies(
    effective_config: Dict[str, Any], changed_tool_id: str, new_enabled_state: bool
) -> Optional[DependencyError]:
    """
    Validate that disabling a tool won't break agents.

    Returns:
        DependencyError if validation fails, None if valid
    """
    if new_enabled_state:
        return None

    # Check if any enabled agents use this tool
    agents = effective_config.get("agents", {})
    dependent_agents = []

    for agent_id, agent_config in agents.items():
        if not isinstance(agent_config, dict):
            continue

        if not agent_config.get("enabled"):
            continue

        # Check if this agent uses the tool
        agent_tools = agent_config.get("tools", {})
        if isinstance(agent_tools, dict):
            # Handle special case: {"*": True} means all tools
            if agent_tools.get("*"):
                dependent_agents.append(agent_id)
            elif agent_tools.get(changed_tool_id):
                dependent_agents.append(agent_id)

    if dependent_agents:
        msg = (
            f"Cannot disable tool '{changed_tool_id}' because "
            f"the following agents use it: {', '.join(dependent_agents)}. "
            f"Please remove this tool from these agents first."
        )
        return DependencyError(msg, dependent_agents)

    return None


def validate_subagent_dependencies(
    effective_config: Dict[str, Any], changed_agent_id: str, new_enabled_state: bool
) -> Optional[DependencyError]:
    """
    Validate that disabling an agent won't break other agents that use it as sub-agent.

    Returns:
        DependencyError if validation fails, None if valid
    """
    if new_enabled_state:
        return None

    # Check if any enabled agents use this as a sub-agent
    agents = effective_config.get("agents", {})
    dependent_agents = []

    for agent_id, agent_config in agents.items():
        if not isinstance(agent_config, dict):
            continue

        if not agent_config.get("enabled"):
            continue

        # Check if this agent uses changed_agent_id as sub-agent
        sub_agents = agent_config.get("sub_agents", {})
        if isinstance(sub_agents, dict) and sub_agents.get(changed_agent_id):
            dependent_agents.append(agent_id)

    if dependent_agents:
        msg = (
            f"Cannot disable agent '{changed_agent_id}' because "
            f"the following agents use it as a sub-agent: {', '.join(dependent_agents)}. "
            f"Please remove this sub-agent from these agents first."
        )
        return DependencyError(msg, dependent_agents)

    return None


def validate_mcp_dependencies(
    effective_config: Dict[str, Any], changed_mcp_id: str, new_enabled_state: bool
) -> Optional[DependencyError]:
    """
    Validate that disabling an MCP won't break agents.

    Returns:
        DependencyError if validation fails, None if valid
    """
    if new_enabled_state:
        return None

    # Check if any enabled agents use this MCP
    agents = effective_config.get("agents", {})
    dependent_agents = []

    for agent_id, agent_config in agents.items():
        if not isinstance(agent_config, dict):
            continue

        if not agent_config.get("enabled"):
            continue

        # Check if this agent uses the MCP
        agent_mcps = agent_config.get("mcps", {})
        if isinstance(agent_mcps, dict) and agent_mcps.get(changed_mcp_id):
            dependent_agents.append(agent_id)

    if dependent_agents:
        msg = (
            f"Cannot disable MCP '{changed_mcp_id}' because "
            f"the following agents use it: {', '.join(dependent_agents)}. "
            f"Please remove this MCP from these agents first."
        )
        return DependencyError(msg, dependent_agents)

    return None


def extract_changes(config_patch: Dict[str, Any]) -> Dict[str, List[tuple]]:
    """
    Extract all enable/disable changes from a config patch.

    Returns:
        Dict with keys: 'integrations', 'tools', 'agents', 'mcp_servers'
        Values are lists of (item_id, new_enabled_state) tuples
    """
    changes = {"integrations": [], "tools": [], "agents": [], "mcp_servers": []}

    # Check integration changes
    if "integrations" in config_patch:
        for integration_id, integration_config in config_patch["integrations"].items():
            if isinstance(integration_config, dict) and "enabled" in integration_config:
                new_state = integration_config["enabled"]
                changes["integrations"].append((integration_id, new_state))

    # Check tool changes
    if "tools" in config_patch:
        for tool_id, tool_config in config_patch["tools"].items():
            if isinstance(tool_config, dict) and "enabled" in tool_config:
                new_state = tool_config["enabled"]
                changes["tools"].append((tool_id, new_state))

    # Check agent changes (might affect sub-agent dependencies)
    if "agents" in config_patch:
        for agent_id, agent_config in config_patch["agents"].items():
            if isinstance(agent_config, dict) and "enabled" in agent_config:
                new_state = agent_config["enabled"]
                changes["agents"].append((agent_id, new_state))

    # Check MCP changes
    if "mcp_servers" in config_patch:
        for mcp_id, mcp_config in config_patch["mcp_servers"].items():
            if isinstance(mcp_config, dict) and "enabled" in mcp_config:
                new_state = mcp_config["enabled"]
                changes["mcp_servers"].append((mcp_id, new_state))

    return changes


def validate_mcp_enabled_tools(
    mcp_id: str, mcp_config: Dict[str, Any]
) -> Optional[DependencyError]:
    """
    Validate that enabled_tools only references valid tools from the MCP's tools list.

    Args:
        mcp_id: ID of the MCP being validated
        mcp_config: MCP configuration dict

    Returns:
        DependencyError if validation fails, None if valid
    """
    enabled_tools = mcp_config.get("enabled_tools", ["*"])

    # Wildcard is always valid
    if enabled_tools == ["*"]:
        return None

    available_tools = mcp_config.get("tools", [])

    # If no tools list defined, we can't validate
    if not available_tools:
        return None

    # Extract tool names from available_tools (handle both string and object arrays)
    available_tool_names = []
    for tool in available_tools:
        if isinstance(tool, str):
            available_tool_names.append(tool)
        elif isinstance(tool, dict):
            # Extract name from tool object
            tool_name = tool.get("name") or tool.get("display_name")
            if tool_name:
                available_tool_names.append(tool_name)

    # Check each enabled tool exists in available tools
    invalid_tools = []
    for tool in enabled_tools:
        if tool not in available_tool_names:
            invalid_tools.append(tool)

    if invalid_tools:
        msg = (
            f"MCP '{mcp_id}' has invalid tools in enabled_tools: {', '.join(invalid_tools)}. "
            f"Valid tools are: {', '.join(available_tool_names)}"
        )
        return DependencyError(msg, invalid_tools)

    return None


def validate_agent_mcps(
    agent_id: str, agent_config: Dict[str, Any], effective_config: Dict[str, Any]
) -> Optional[DependencyError]:
    """
    Validate that agent's mcps only references valid MCP IDs.

    Args:
        agent_id: ID of the agent being validated
        agent_config: Agent configuration dict
        effective_config: Full effective config

    Returns:
        DependencyError if validation fails, None if valid
    """
    agent_mcps = agent_config.get("mcps", {})

    if not agent_mcps:
        return None

    mcp_servers = effective_config.get("mcp_servers", {})

    # Check each referenced MCP exists
    invalid_mcps = []
    for mcp_id in agent_mcps.keys():
        if mcp_id not in mcp_servers:
            invalid_mcps.append(mcp_id)

    if invalid_mcps:
        msg = (
            f"Agent '{agent_id}' references non-existent MCPs: {', '.join(invalid_mcps)}. "
            f"Available MCPs are: {', '.join(mcp_servers.keys())}"
        )
        return DependencyError(msg, invalid_mcps)

    return None


def validate_entrance_agent(
    effective_config: Dict[str, Any],
) -> Optional[DependencyError]:
    """
    Validate that the entrance_agent field references a valid, enabled agent.

    Args:
        effective_config: Full effective config after applying changes

    Returns:
        DependencyError if validation fails, None if valid
    """
    entrance_agent = effective_config.get("entrance_agent")

    if not entrance_agent:
        # If no entrance_agent specified, it's valid (will default to planner in orchestrator)
        return None

    agents = effective_config.get("agents", {})

    # Check if the entrance agent exists
    if entrance_agent not in agents:
        available_agents = list(agents.keys())
        msg = (
            f"Entrance agent '{entrance_agent}' does not exist. "
            f"Available agents are: {', '.join(available_agents)}"
        )
        return DependencyError(msg, [entrance_agent])

    # Check if the entrance agent is enabled
    agent_config = agents.get(entrance_agent, {})
    if not agent_config.get("enabled", False):
        msg = (
            f"Entrance agent '{entrance_agent}' must be enabled. "
            f"Please enable the agent before setting it as the entrance agent."
        )
        return DependencyError(msg, [entrance_agent])

    return None


def validate_config_change(
    effective_config: Dict[str, Any], config_patch: Dict[str, Any]
) -> List[DependencyError]:
    """
    Validate all dependency constraints for a config change.

    Args:
        effective_config: The effective config after applying patch
        config_patch: The changes being made

    Returns:
        List of DependencyErrors (empty if valid)
    """
    errors = []

    # Extract all changes from patch
    changes = extract_changes(config_patch)

    # Validate integration changes
    for integration_id, new_state in changes["integrations"]:
        err = validate_integration_dependencies(
            effective_config, integration_id, new_state
        )
        if err:
            errors.append(err)

    # Validate tool changes
    for tool_id, new_state in changes["tools"]:
        err = validate_tool_dependencies(effective_config, tool_id, new_state)
        if err:
            errors.append(err)

    # Validate agent changes (might affect sub-agent dependencies)
    for agent_id, new_state in changes["agents"]:
        err = validate_subagent_dependencies(effective_config, agent_id, new_state)
        if err:
            errors.append(err)

    # Validate MCP changes
    for mcp_id, new_state in changes["mcp_servers"]:
        err = validate_mcp_dependencies(effective_config, mcp_id, new_state)
        if err:
            errors.append(err)

    # NEW: Validate MCP enabled_tools
    if "mcp_servers" in config_patch:
        for mcp_id, mcp_config in config_patch["mcp_servers"].items():
            if isinstance(mcp_config, dict) and "enabled_tools" in mcp_config:
                # Get the full MCP config from effective config
                full_mcp_config = effective_config.get("mcp_servers", {}).get(
                    mcp_id, {}
                )
                err = validate_mcp_enabled_tools(mcp_id, full_mcp_config)
                if err:
                    errors.append(err)

    # NEW: Validate agent mcps references
    if "agents" in config_patch:
        for agent_id, agent_config in config_patch["agents"].items():
            if isinstance(agent_config, dict) and "mcps" in agent_config:
                # Get the full agent config from effective config
                full_agent_config = effective_config.get("agents", {}).get(agent_id, {})
                err = validate_agent_mcps(agent_id, full_agent_config, effective_config)
                if err:
                    errors.append(err)

    # Validate entrance_agent field (always validate if present, or if agents changed)
    if "entrance_agent" in config_patch or "agents" in config_patch:
        err = validate_entrance_agent(effective_config)
        if err:
            errors.append(err)

    return errors
