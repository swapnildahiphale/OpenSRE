#!/usr/bin/env python3
"""
Clean up inherited MCPs from existing organization configurations.

This script removes mcp_servers from all node configurations since:
1. MCPs should not be inherited from defaults
2. Customers should add MCPs explicitly via the UI
3. Old preset had hardcoded MCPs (GitHub, AWS EKS, etc.) that appeared as "Inherited"

Usage:
    python -m config_service.scripts.cleanup_inherited_mcps --dry-run
    python -m config_service.scripts.cleanup_inherited_mcps  # actually clean
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config_service.src.db.config_repository import invalidate_config_cache
from config_service.src.db.models import NodeConfiguration

logger = structlog.get_logger(__name__)


def cleanup_inherited_mcps(db_url: str, dry_run: bool = True):
    """Remove mcp_servers from all node configurations."""
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get all node configurations
        configs = session.query(NodeConfiguration).all()

        cleaned_count = 0
        total_mcps_removed = 0

        for config in configs:
            config_json = config.config_json or {}

            # Check for old schema: mcps.default
            old_mcps = config_json.get("mcps", {}).get("default", [])

            # Check for new schema: mcp_servers
            mcp_servers = config_json.get("mcp_servers", {})

            if old_mcps or mcp_servers:
                num_mcps = (
                    len(old_mcps) if isinstance(old_mcps, list) else len(mcp_servers)
                )
                total_mcps_removed += num_mcps

                print(
                    f"\n{'[DRY RUN] ' if dry_run else ''}Cleaning node: {config.node_id} ({config.node_type})"
                )
                print(f"  Removing {num_mcps} MCP(s)")

                if old_mcps:
                    print(
                        f"  Old schema (mcps.default): {[m.get('id') for m in old_mcps if isinstance(m, dict)]}"
                    )
                if mcp_servers:
                    print(f"  New schema (mcp_servers): {list(mcp_servers.keys())}")

                if not dry_run:
                    # Remove both old and new schemas
                    if "mcps" in config_json:
                        del config_json["mcps"]
                    if "mcp_servers" in config_json:
                        del config_json["mcp_servers"]

                    config.config_json = config_json

                    # Invalidate cached effective config
                    invalidate_config_cache(
                        session, config.org_id, config.node_id, cascade=True
                    )

                cleaned_count += 1

        if not dry_run:
            session.commit()
            print("\n✅ Cleanup complete!")
        else:
            print(f"\n{'='*60}")
            print("DRY RUN - No changes made")
            print(f"{'='*60}")

        print("\nSummary:")
        print(f"  Nodes affected: {cleaned_count}")
        print(f"  Total MCPs removed: {total_mcps_removed}")
        print("\nCustomers can now add MCPs via the UI:")
        print("  1. Go to Tools page")
        print("  2. Click 'Add Custom MCP Server'")
        print("  3. Fill in command, args, env vars")
        print("  4. System discovers tools automatically")

    except Exception as e:
        logger.error("cleanup_failed", error=str(e))
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Clean up inherited MCPs")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without applying"
    )
    parser.add_argument(
        "--db-url", help="Database URL (default: from DATABASE_URL env)"
    )
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        print("\nUsage:")
        print(
            "  DATABASE_URL=postgresql://... python -m config_service.scripts.cleanup_inherited_mcps"
        )
        print(
            "  python -m config_service.scripts.cleanup_inherited_mcps --db-url postgresql://..."
        )
        sys.exit(1)

    print("=" * 60)
    print("CLEANUP INHERITED MCPs")
    print("=" * 60)
    print(f"Database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE - will modify database'}")
    print("=" * 60)

    if not args.dry_run:
        confirm = input(
            "\n⚠️  This will remove all MCP servers from configs. Continue? (yes/no): "
        )
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    cleanup_inherited_mcps(db_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
