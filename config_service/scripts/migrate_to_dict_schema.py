"""
⚠️ OBSOLETE - This script is no longer used ⚠️

This migration is now handled by Alembic migration: 20260114_canonical_format.py
The database migration runs automatically on deploy.

Use: python3 -m alembic upgrade head

---

Original description:
Migration script to convert old list-based configs to new dict-based schema.

This script:
1. Converts agents.*.tools from {enabled: [...], disabled: [...]} to {tool_id: bool}
2. Converts agents.*.sub_agents from list to dict
3. Adds agents.*.mcps field (empty dict by default)
4. Converts mcp_servers from list to dict keyed by ID
5. Merges team_added_mcp_servers into mcp_servers
6. Applies team_enabled_tool_ids and team_disabled_tool_ids to appropriate sections
7. Removes deprecated fields
"""

import argparse
import copy
import json
import sys
from typing import Any, Dict

import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config_service.src.db.config_models import NodeConfiguration

logger = structlog.get_logger(__name__)


def migrate_agent_tools(agent_config: Dict[str, Any]) -> None:
    """
    Convert agent tools from {enabled: [...], disabled: [...]} to {tool_id: bool}.

    Modifies agent_config in place.
    """
    if "tools" not in agent_config:
        return

    tools_config = agent_config["tools"]

    # Old format: {"enabled": [...], "disabled": [...]}
    if isinstance(tools_config, dict) and (
        "enabled" in tools_config or "disabled" in tools_config
    ):
        new_tools = {}

        # Add enabled tools
        for tool_id in tools_config.get("enabled", []):
            if tool_id == "*":
                # Special case: all tools enabled
                new_tools["*"] = True
            else:
                new_tools[tool_id] = True

        # Add disabled tools (explicit False)
        for tool_id in tools_config.get("disabled", []):
            new_tools[tool_id] = False

        agent_config["tools"] = new_tools
        logger.debug("migrated_agent_tools", new_tools=new_tools)


def migrate_agent_sub_agents(agent_config: Dict[str, Any]) -> None:
    """
    Convert agent sub_agents from list to dict.

    Modifies agent_config in place.
    """
    if "sub_agents" not in agent_config:
        return

    sub_agents = agent_config["sub_agents"]

    # Old format: ["agent1", "agent2", ...]
    if isinstance(sub_agents, list):
        new_sub_agents = {}
        for sub_agent_id in sub_agents:
            new_sub_agents[sub_agent_id] = True

        agent_config["sub_agents"] = new_sub_agents
        logger.debug("migrated_agent_sub_agents", new_sub_agents=new_sub_agents)


def migrate_mcp_servers(config: Dict[str, Any]) -> None:
    """
    Convert mcp_servers from list to dict keyed by ID.

    Modifies config in place.
    """
    if "mcp_servers" not in config:
        return

    mcp_list = config["mcp_servers"]

    # Old format: [{id: "x", name: "...", ...}, ...]
    if isinstance(mcp_list, list):
        new_mcps = {}
        for mcp in mcp_list:
            if "id" in mcp:
                mcp_id = mcp.pop("id")  # Remove id from object, use as key
                new_mcps[mcp_id] = mcp
            else:
                # No ID field - generate one from name
                mcp_id = mcp.get("name", "unknown").lower().replace(" ", "-")
                logger.warning("mcp_missing_id", mcp=mcp, generated_id=mcp_id)
                new_mcps[mcp_id] = mcp

        config["mcp_servers"] = new_mcps
        logger.debug("migrated_mcp_servers", count=len(new_mcps))


def merge_team_added_mcps(config: Dict[str, Any]) -> None:
    """
    Merge team_added_mcp_servers into mcp_servers dict.

    Modifies config in place and removes team_added_mcp_servers field.
    """
    if "team_added_mcp_servers" not in config:
        return

    team_mcps = config.pop("team_added_mcp_servers")

    if isinstance(team_mcps, list):
        # Ensure mcp_servers is a dict
        if "mcp_servers" not in config:
            config["mcp_servers"] = {}

        for mcp in team_mcps:
            if "id" in mcp:
                mcp_id = mcp.pop("id")
                config["mcp_servers"][mcp_id] = mcp
            else:
                mcp_id = mcp.get("name", "unknown").lower().replace(" ", "-")
                logger.warning("team_mcp_missing_id", mcp=mcp, generated_id=mcp_id)
                config["mcp_servers"][mcp_id] = mcp

        logger.debug("merged_team_added_mcps", count=len(team_mcps))


def apply_team_enabled_tool_ids(config: Dict[str, Any]) -> None:
    """
    Apply team_enabled_tool_ids to tools, integrations, and mcp_servers.

    Modifies config in place and removes team_enabled_tool_ids field.
    """
    if "team_enabled_tool_ids" not in config:
        return

    enabled_ids = config.pop("team_enabled_tool_ids")

    for tool_id in enabled_ids:
        # Check which category and set enabled
        if "tools" in config and tool_id in config["tools"]:
            if isinstance(config["tools"][tool_id], dict):
                config["tools"][tool_id]["enabled"] = True
        elif "integrations" in config and tool_id in config["integrations"]:
            if isinstance(config["integrations"][tool_id], dict):
                config["integrations"][tool_id]["enabled"] = True
        elif "mcp_servers" in config and tool_id in config["mcp_servers"]:
            if isinstance(config["mcp_servers"][tool_id], dict):
                config["mcp_servers"][tool_id]["enabled"] = True

    logger.debug("applied_team_enabled_tool_ids", count=len(enabled_ids))


def apply_team_disabled_tool_ids(config: Dict[str, Any]) -> None:
    """
    Apply team_disabled_tool_ids to tools, integrations, and mcp_servers.

    Modifies config in place and removes team_disabled_tool_ids field.
    """
    if "team_disabled_tool_ids" not in config:
        return

    disabled_ids = config.pop("team_disabled_tool_ids")

    for tool_id in disabled_ids:
        # Check which category and set disabled
        if "tools" in config and tool_id in config["tools"]:
            if isinstance(config["tools"][tool_id], dict):
                config["tools"][tool_id]["enabled"] = False
        elif "integrations" in config and tool_id in config["integrations"]:
            if isinstance(config["integrations"][tool_id], dict):
                config["integrations"][tool_id]["enabled"] = False
        elif "mcp_servers" in config and tool_id in config["mcp_servers"]:
            if isinstance(config["mcp_servers"][tool_id], dict):
                config["mcp_servers"][tool_id]["enabled"] = False

    logger.debug("applied_team_disabled_tool_ids", count=len(disabled_ids))


def add_mcps_field_to_agents(config: Dict[str, Any]) -> None:
    """
    Add empty mcps field to all agents.

    Modifies config in place.
    """
    if "agents" not in config:
        return

    for agent_id, agent_config in config["agents"].items():
        if isinstance(agent_config, dict) and "mcps" not in agent_config:
            agent_config["mcps"] = {}

    logger.debug("added_mcps_field_to_agents")


def migrate_config(old_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate old config schema to new schema.

    Returns:
        New config dict with migrated schema
    """
    new_config = copy.deepcopy(old_config)

    # 1. Migrate agents
    if "agents" in new_config:
        for agent_id, agent_config in new_config["agents"].items():
            if isinstance(agent_config, dict):
                migrate_agent_tools(agent_config)
                migrate_agent_sub_agents(agent_config)

    # 2. Add mcps field to agents
    add_mcps_field_to_agents(new_config)

    # 3. Migrate mcp_servers from list to dict
    migrate_mcp_servers(new_config)

    # 4. Merge team_added_mcp_servers into mcp_servers
    merge_team_added_mcps(new_config)

    # 5. Apply team_enabled_tool_ids
    apply_team_enabled_tool_ids(new_config)

    # 6. Apply team_disabled_tool_ids
    apply_team_disabled_tool_ids(new_config)

    return new_config


def migrate_all_configs(session, org_id: str = None, dry_run: bool = True):
    """
    Migrate all configs in database to new schema.

    Args:
        session: Database session
        org_id: Optional org ID to filter (migrate only one org)
        dry_run: If True, preview changes without saving
    """
    query = session.query(NodeConfiguration)
    if org_id:
        query = query.filter(NodeConfiguration.org_id == org_id)

    configs = query.all()

    migrated_count = 0
    skipped_count = 0

    for config in configs:
        old_config = config.config_json

        # Skip if config is empty
        if not old_config:
            logger.info(
                "skipping_empty_config", org_id=config.org_id, node_id=config.node_id
            )
            skipped_count += 1
            continue

        # Check if already migrated (heuristic: if mcp_servers is dict, likely migrated)
        if "mcp_servers" in old_config and isinstance(old_config["mcp_servers"], dict):
            # Check if agents have new schema
            if "agents" in old_config:
                first_agent = next(iter(old_config["agents"].values()), {})
                if isinstance(
                    first_agent.get("tools"), dict
                ) and "enabled" not in first_agent.get("tools", {}):
                    logger.info(
                        "skipping_already_migrated",
                        org_id=config.org_id,
                        node_id=config.node_id,
                    )
                    skipped_count += 1
                    continue

        # Perform migration
        new_config = migrate_config(old_config)

        if dry_run:
            print(f"\n{'='*80}")
            print(f"Would migrate: {config.org_id}/{config.node_id}")
            print(f"{'='*80}")
            print("\nOLD CONFIG:")
            print(json.dumps(old_config, indent=2))
            print("\nNEW CONFIG:")
            print(json.dumps(new_config, indent=2))
            print(f"\n{'='*80}\n")
        else:
            config.config_json = new_config
            config.version += 1
            # Invalidate cached effective config
            config.effective_config_json = None
            config.effective_config_computed_at = None
            session.add(config)
            logger.info(
                "migrated_config",
                org_id=config.org_id,
                node_id=config.node_id,
                new_version=config.version,
            )

        migrated_count += 1

    if not dry_run:
        session.commit()
        logger.info(
            "migration_complete",
            total_configs=len(configs),
            migrated=migrated_count,
            skipped=skipped_count,
        )
    else:
        logger.info(
            "dry_run_complete",
            total_configs=len(configs),
            would_migrate=migrated_count,
            would_skip=skipped_count,
        )

    return migrated_count, skipped_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate config database from list-based to dict-based schema"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without actually migrating",
    )
    parser.add_argument(
        "--org-id", type=str, help="Only migrate configs for this org ID"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        help="Database URL (defaults to DATABASE_URL env var)",
    )

    args = parser.parse_args()

    # Get database URL
    import os

    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: DATABASE_URL environment variable not set and --database-url not provided"
        )
        sys.exit(1)

    # Create session
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        print(f"\n{'='*80}")
        print("Config Schema Migration")
        print(f"{'='*80}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'LIVE MIGRATION'}")
        if args.org_id:
            print(f"Org Filter: {args.org_id}")
        print(f"{'='*80}\n")

        if not args.dry_run:
            confirm = input("This will modify the database. Are you sure? (yes/no): ")
            if confirm.lower() != "yes":
                print("Migration cancelled.")
                sys.exit(0)

        migrated, skipped = migrate_all_configs(
            session, org_id=args.org_id, dry_run=args.dry_run
        )

        print(f"\n{'='*80}")
        print("Migration Summary")
        print(f"{'='*80}")
        print(f"Migrated: {migrated}")
        print(f"Skipped: {skipped}")
        print(f"{'='*80}\n")

    except Exception as e:
        logger.error("migration_failed", error=str(e))
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
