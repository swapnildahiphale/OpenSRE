#!/usr/bin/env python3
"""
Data Migration: node_configs → node_configurations

Migrates existing configuration data from the old schema (node_configs table)
to the new hierarchical configuration schema (node_configurations table).

Usage:
    # Dry run (preview changes without committing)
    python3 scripts/migrate_node_configs_to_new_schema.py --dry-run

    # Execute migration
    python3 scripts/migrate_node_configs_to_new_schema.py

    # Rollback (delete all migrated data)
    python3 scripts/migrate_node_configs_to_new_schema.py --rollback
"""

import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import structlog

# Add src to path
sys.path.insert(0, "/app" if __import__("os").path.exists("/app/src") else ".")

from src.db.config_models import NodeConfiguration
from src.db.models import NodeConfig, OrgNode
from src.db.session import get_session_maker

logger = structlog.get_logger(__name__)


def get_node_type(org_id: str, node_id: str, session) -> str:
    """Infer node type from OrgNode table."""
    org_node = session.query(OrgNode).filter_by(org_id=org_id, node_id=node_id).first()
    if org_node:
        return (
            org_node.node_type.value
            if hasattr(org_node.node_type, "value")
            else str(org_node.node_type)
        )

    # Fallback: infer from node_id
    if node_id == org_id:
        return "org"
    else:
        # Default to 'team' for all non-org nodes
        return "team"


def migrate_node_configs(dry_run: bool = True) -> Dict[str, Any]:
    """
    Migrate all node_configs to node_configurations.

    Args:
        dry_run: If True, preview changes without committing

    Returns:
        Dict with migration statistics
    """
    session_maker = get_session_maker()
    session = session_maker()

    stats = {
        "total_old_configs": 0,
        "already_migrated": 0,
        "migrated": 0,
        "skipped": 0,
        "errors": [],
    }

    try:
        # Get all configs from old schema
        old_configs = session.query(NodeConfig).all()
        stats["total_old_configs"] = len(old_configs)

        logger.info(
            "migration_started",
            total_configs=stats["total_old_configs"],
            dry_run=dry_run,
        )

        for old_config in old_configs:
            org_id = old_config.org_id
            node_id = old_config.node_id

            # Check if already migrated
            existing = (
                session.query(NodeConfiguration)
                .filter_by(org_id=org_id, node_id=node_id)
                .first()
            )

            if existing:
                logger.debug("already_migrated", org_id=org_id, node_id=node_id)
                stats["already_migrated"] += 1
                continue

            # Get node type
            node_type = get_node_type(org_id, node_id, session)

            # Create new configuration
            new_config = NodeConfiguration(
                id=f"cfg-{uuid.uuid4().hex[:12]}",
                org_id=org_id,
                node_id=node_id,
                node_type=node_type,
                config_json=old_config.config_json or {},
                version=old_config.version or 1,
                created_at=old_config.updated_at
                or datetime.now(timezone.utc),  # Best guess
                updated_at=old_config.updated_at or datetime.now(timezone.utc),
                updated_by=old_config.updated_by,
                # Leave effective_config_json=None, will be computed on first read
                effective_config_json=None,
                effective_config_computed_at=None,
            )

            if dry_run:
                logger.info(
                    "would_migrate",
                    org_id=org_id,
                    node_id=node_id,
                    node_type=node_type,
                    config_size=len(str(old_config.config_json)),
                )
            else:
                session.add(new_config)
                logger.info(
                    "migrated", org_id=org_id, node_id=node_id, node_type=node_type
                )

            stats["migrated"] += 1

        if not dry_run:
            session.commit()
            logger.info("migration_committed", **stats)
        else:
            logger.info("migration_preview_complete", **stats)

        return stats

    except Exception as e:
        session.rollback()
        logger.error("migration_failed", error=str(e))
        stats["errors"].append(str(e))
        raise
    finally:
        session.close()


def rollback_migration() -> Dict[str, Any]:
    """
    Rollback migration by deleting all data from node_configurations.

    WARNING: This will delete ALL data in node_configurations table!
    """
    session_maker = get_session_maker()
    session = session_maker()

    stats = {"deleted": 0}

    try:
        # Count before delete
        count = session.query(NodeConfiguration).count()

        logger.warning("rollback_started", total_configs=count, action="DELETE_ALL")

        # Delete all
        deleted = session.query(NodeConfiguration).delete()
        session.commit()

        stats["deleted"] = deleted
        logger.info("rollback_complete", deleted=deleted)

        return stats

    except Exception as e:
        session.rollback()
        logger.error("rollback_failed", error=str(e))
        raise
    finally:
        session.close()


def verify_migration() -> Dict[str, Any]:
    """Verify migration by comparing counts and spot-checking data."""
    session_maker = get_session_maker()
    session = session_maker()

    try:
        old_count = session.query(NodeConfig).count()
        new_count = session.query(NodeConfiguration).count()

        logger.info(
            "verification",
            old_schema_count=old_count,
            new_schema_count=new_count,
            match=old_count == new_count,
        )

        # Spot check: compare a few configs
        old_sample = session.query(NodeConfig).limit(5).all()
        for old in old_sample:
            new = (
                session.query(NodeConfiguration)
                .filter_by(org_id=old.org_id, node_id=old.node_id)
                .first()
            )

            if not new:
                logger.error(
                    "verification_failed_missing",
                    org_id=old.org_id,
                    node_id=old.node_id,
                )
            elif new.config_json != old.config_json:
                logger.error(
                    "verification_failed_mismatch",
                    org_id=old.org_id,
                    node_id=old.node_id,
                )
            else:
                logger.debug(
                    "verification_passed", org_id=old.org_id, node_id=old.node_id
                )

        return {
            "old_count": old_count,
            "new_count": new_count,
            "match": old_count == new_count,
        }

    finally:
        session.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate node_configs to node_configurations"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without committing"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (DELETE ALL from node_configurations)",
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify migration by comparing counts"
    )

    args = parser.parse_args()

    if args.rollback:
        response = input(
            "WARNING: This will DELETE ALL data from node_configurations. Type 'yes' to confirm: "
        )
        if response.lower() != "yes":
            print("Rollback cancelled.")
            return

        stats = rollback_migration()
        print(f"\n✓ Rollback complete: {stats['deleted']} configs deleted")

    elif args.verify:
        stats = verify_migration()
        print("\n✓ Verification complete:")
        print(f"  Old schema: {stats['old_count']} configs")
        print(f"  New schema: {stats['new_count']} configs")
        print(f"  Match: {stats['match']}")

    else:
        stats = migrate_node_configs(dry_run=args.dry_run)

        print(f"\n{'DRY RUN - ' if args.dry_run else ''}Migration complete:")
        print(f"  Total old configs: {stats['total_old_configs']}")
        print(f"  Already migrated: {stats['already_migrated']}")
        print(f"  Migrated: {stats['migrated']}")
        print(f"  Skipped: {stats['skipped']}")

        if stats["errors"]:
            print(f"\n❌ Errors ({len(stats['errors'])}):")
            for error in stats["errors"]:
                print(f"  - {error}")
        elif not args.dry_run:
            print("\n✓ Migration successful! Run with --verify to validate.")
        else:
            print("\n✓ Dry run complete. Run without --dry-run to execute.")


if __name__ == "__main__":
    main()
