"""Migrate to canonical config format

Revision ID: 20260114_canonical_format
Revises: 20260113_consolidated
Create Date: 2026-01-14

This migration converts all configuration JSON to the canonical format:
1. Convert team_enabled_tool_ids + team_disabled_tool_ids → tools: {tool_id: bool}
2. Merge team_added_mcp_servers into mcp_servers dict
3. Remove top-level mcps section
4. Convert agents.*.tools: {enabled: [], disabled: []} → {tool_id: bool}
5. Convert agents.*.sub_agents: [] → {agent_id: bool}
"""

from typing import Any, Dict, List

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260114_canonical_format"
down_revision = "20260113_consolidated"
branch_labels = None
depends_on = None


def convert_tools_to_dict(tools_config: Any) -> Dict[str, bool]:
    """Convert tools from {enabled: [], disabled: []} format to {tool_id: bool} format."""
    if not tools_config:
        return {}

    if isinstance(tools_config, dict):
        # Check if it's the old format with enabled/disabled keys
        if "enabled" in tools_config or "disabled" in tools_config:
            result = {}
            for tool_id in tools_config.get("enabled", []):
                result[tool_id] = True
            for tool_id in tools_config.get("disabled", []):
                result[tool_id] = False
            return result
        else:
            # Already in dict format, return as-is
            return tools_config

    return {}


def convert_sub_agents_to_dict(sub_agents: Any) -> Dict[str, bool]:
    """Convert sub_agents from [] format to {agent_id: bool} format."""
    if not sub_agents:
        return {}

    if isinstance(sub_agents, list):
        return {agent_id: True for agent_id in sub_agents}
    elif isinstance(sub_agents, dict):
        # Already in dict format
        return sub_agents

    return {}


def merge_team_tools_into_agents(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert team_enabled_tool_ids and team_disabled_tool_ids into team-level tools dict.

    In canonical format, there is a top-level 'tools' dict that serves as a team-wide filter.
    """
    team_enabled = config.pop("team_enabled_tool_ids", [])
    team_disabled = config.pop("team_disabled_tool_ids", [])

    if team_enabled or team_disabled:
        # Create team-level tools dict
        if "tools" not in config:
            config["tools"] = {}

        # Add enabled tools
        for tool_id in team_enabled:
            config["tools"][tool_id] = True

        # Add disabled tools
        for tool_id in team_disabled:
            config["tools"][tool_id] = False

    return config


def merge_mcp_servers(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge team_added_mcp_servers into mcp_servers dict.

    OLD:
      mcp_servers: [{id: "fs-1", ...}]
      team_added_mcp_servers: [{id: "fs-2", ...}]

    NEW:
      mcp_servers: {"fs-1": {...}, "fs-2": {...}}
    """
    team_added = config.pop("team_added_mcp_servers", [])
    mcp_servers = config.get("mcp_servers", [])

    # Convert to dict format if it's a list
    if isinstance(mcp_servers, list):
        mcp_dict = {}
        for server in mcp_servers:
            if isinstance(server, dict) and "id" in server:
                server_id = server.pop("id")
                mcp_dict[server_id] = server
        config["mcp_servers"] = mcp_dict
    elif not isinstance(mcp_servers, dict):
        config["mcp_servers"] = {}

    # Merge team_added_mcp_servers
    if isinstance(team_added, list):
        for server in team_added:
            if isinstance(server, dict) and "id" in server:
                server_id = server.pop("id")
                config["mcp_servers"][server_id] = server

    return config


def convert_config_to_canonical(config: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a single config object to canonical format."""
    if not config:
        return config

    # 1. Remove top-level mcps section (not used by agent runtime)
    config.pop("mcps", None)

    # 2. Convert team-level tool arrays to team-level tools dict
    config = merge_team_tools_into_agents(config)

    # 3. Merge MCP servers
    config = merge_mcp_servers(config)

    # 4. Convert agents section
    if "agents" in config and isinstance(config["agents"], dict):
        for agent_id, agent_config in config["agents"].items():
            if not isinstance(agent_config, dict):
                continue

            # Convert tools format
            if "tools" in agent_config:
                agent_config["tools"] = convert_tools_to_dict(agent_config["tools"])

            # Convert sub_agents format
            if "sub_agents" in agent_config:
                agent_config["sub_agents"] = convert_sub_agents_to_dict(
                    agent_config["sub_agents"]
                )

    return config


def revert_tools_to_array(tools_dict: Dict[str, bool]) -> Dict[str, List[str]]:
    """Revert tools from {tool_id: bool} format to {enabled: [], disabled: []} format."""
    if not tools_dict or not isinstance(tools_dict, dict):
        return {"enabled": [], "disabled": []}

    enabled = [tool_id for tool_id, enabled in tools_dict.items() if enabled]
    disabled = [tool_id for tool_id, enabled in tools_dict.items() if not enabled]

    return {"enabled": enabled, "disabled": disabled}


def revert_sub_agents_to_array(sub_agents_dict: Dict[str, bool]) -> List[str]:
    """Revert sub_agents from {agent_id: bool} format to [] format."""
    if not sub_agents_dict or not isinstance(sub_agents_dict, dict):
        return []

    return [agent_id for agent_id, enabled in sub_agents_dict.items() if enabled]


def revert_config_from_canonical(config: Dict[str, Any]) -> Dict[str, Any]:
    """Revert a config object from canonical format to old format."""
    if not config:
        return config

    # 1. Convert team-level tools dict back to arrays
    if "tools" in config and isinstance(config["tools"], dict):
        tools_dict = config.pop("tools")
        enabled = [tool_id for tool_id, val in tools_dict.items() if val]
        disabled = [tool_id for tool_id, val in tools_dict.items() if not val]

        if enabled:
            config["team_enabled_tool_ids"] = enabled
        if disabled:
            config["team_disabled_tool_ids"] = disabled

    # 2. Split MCP servers back to two arrays
    if "mcp_servers" in config and isinstance(config["mcp_servers"], dict):
        mcp_dict = config["mcp_servers"]
        # Convert dict back to list (can't distinguish which were "team_added" so put all in mcp_servers)
        mcp_list = []
        for server_id, server_config in mcp_dict.items():
            server = server_config.copy()
            server["id"] = server_id
            mcp_list.append(server)
        config["mcp_servers"] = mcp_list

    # 3. Convert agents section back
    if "agents" in config and isinstance(config["agents"], dict):
        for agent_id, agent_config in config["agents"].items():
            if not isinstance(agent_config, dict):
                continue

            # Revert tools format
            if "tools" in agent_config and isinstance(agent_config["tools"], dict):
                agent_config["tools"] = revert_tools_to_array(agent_config["tools"])

            # Revert sub_agents format
            if "sub_agents" in agent_config and isinstance(
                agent_config["sub_agents"], dict
            ):
                agent_config["sub_agents"] = revert_sub_agents_to_array(
                    agent_config["sub_agents"]
                )

    return config


def upgrade() -> None:
    """Convert all configs to canonical format."""
    connection = op.get_bind()

    # Get all node_configurations
    result = connection.execute(
        sa.text("SELECT id, org_id, node_id, config_json FROM node_configurations")
    )

    rows = result.fetchall()
    print("\n=== Canonical Format Migration ===")
    print(f"Found {len(rows)} configurations to migrate\n")

    updated_count = 0
    for row in rows:
        config_id = row[0]
        org_id = row[1]
        node_id = row[2]
        config_json = row[3]

        if not config_json:
            continue

        # Convert to canonical format
        original_config = dict(config_json)
        canonical_config = convert_config_to_canonical(dict(config_json))

        # Only update if something changed
        if canonical_config != original_config:
            connection.execute(
                sa.text(
                    "UPDATE node_configurations SET config_json = :config_json, "
                    "updated_at = NOW() WHERE id = :id"
                ),
                {"config_json": canonical_config, "id": config_id},
            )
            updated_count += 1
            print(f"✓ Migrated: {org_id} / {node_id}")

    print("\n=== Migration Complete ===")
    print(f"Updated {updated_count} out of {len(rows)} configurations\n")


def downgrade() -> None:
    """Revert all configs from canonical format to old format."""
    connection = op.get_bind()

    # Get all node_configurations
    result = connection.execute(
        sa.text("SELECT id, org_id, node_id, config_json FROM node_configurations")
    )

    rows = result.fetchall()
    print("\n=== Reverting Canonical Format Migration ===")
    print(f"Found {len(rows)} configurations to revert\n")

    reverted_count = 0
    for row in rows:
        config_id = row[0]
        org_id = row[1]
        node_id = row[2]
        config_json = row[3]

        if not config_json:
            continue

        # Revert from canonical format
        reverted_config = revert_config_from_canonical(dict(config_json))

        connection.execute(
            sa.text(
                "UPDATE node_configurations SET config_json = :config_json, "
                "updated_at = NOW() WHERE id = :id"
            ),
            {"config_json": reverted_config, "id": config_id},
        )
        reverted_count += 1
        print(f"✓ Reverted: {org_id} / {node_id}")

    print("\n=== Revert Complete ===")
    print(f"Reverted {reverted_count} out of {len(rows)} configurations\n")
