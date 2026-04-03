#!/usr/bin/env python3
"""
Add Azure MCP Server to team configuration.

This script updates a team's node_configurations to include Azure MCP Server
with the proper credentials and configuration.

Usage:
    python scripts/add_azure_mcp.py \
        --org-id demo-org \
        --team-id team-sre \
        --tenant-id "xxx-xxx-xxx" \
        --client-id "yyy-yyy-yyy" \
        --client-secret "zzz-zzz-zzz" \
        --subscription-id "www-www-www"

    # Or use environment variables:
    export AZURE_TENANT_ID="xxx"
    export AZURE_CLIENT_ID="yyy"
    export AZURE_CLIENT_SECRET="zzz"
    export AZURE_SUBSCRIPTION_ID="www"

    python scripts/add_azure_mcp.py --org-id demo-org --team-id team-sre

Prerequisites:
    - Database connection configured via DATABASE_URL environment variable
    - Team must already exist in node_configurations table
"""

import argparse
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables from .env if present
load_dotenv()

# Database connection from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Error: DATABASE_URL environment variable not set")
    print(
        "   Example: export DATABASE_URL='postgresql://user:pass@localhost/opensre_config'"
    )
    sys.exit(1)


def add_azure_mcp_to_team(
    org_id: str,
    team_id: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    subscription_id: str,
    enabled: bool = True,
) -> bool:
    """
    Add Azure MCP configuration to a team's node_configurations.

    Args:
        org_id: Organization ID
        team_id: Team node ID
        tenant_id: Azure AD tenant ID
        client_id: Service Principal client ID
        client_secret: Service Principal secret
        subscription_id: Azure subscription ID
        enabled: Whether to enable the MCP server (default: True)

    Returns:
        True if successful, False otherwise
    """
    azure_mcp_config = {
        "name": "Azure MCP Server (Microsoft Official)",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@azure/mcp@latest", "server", "start"],
        "env": {
            "AZURE_TENANT_ID": "${azure_tenant_id}",
            "AZURE_CLIENT_ID": "${azure_client_id}",
            "AZURE_CLIENT_SECRET": "${azure_client_secret}",
            "AZURE_SUBSCRIPTION_ID": "${azure_subscription_id}",
        },
        "enabled": enabled,
        "config_schema": {
            "azure_tenant_id": {
                "type": "string",
                "required": True,
                "display_name": "Azure Tenant ID",
                "description": "Azure AD tenant ID",
            },
            "azure_client_id": {
                "type": "string",
                "required": True,
                "display_name": "Azure Client ID",
                "description": "Service Principal application (client) ID",
            },
            "azure_client_secret": {
                "type": "secret",
                "required": True,
                "display_name": "Azure Client Secret",
                "description": "Service Principal secret value",
            },
            "azure_subscription_id": {
                "type": "string",
                "required": True,
                "display_name": "Azure Subscription ID",
                "description": "Azure subscription ID",
            },
        },
        "config_values": {
            "azure_tenant_id": tenant_id,
            "azure_client_id": client_id,
            "azure_client_secret": client_secret,
            "azure_subscription_id": subscription_id,
        },
    }

    try:
        engine = create_engine(DATABASE_URL)

        # Check if team exists
        check_query = text("""
            SELECT id, org_id, node_id, config_json
            FROM node_configurations
            WHERE org_id = :org_id AND node_id = :team_id
        """)

        with engine.connect() as conn:
            result = conn.execute(check_query, {"org_id": org_id, "team_id": team_id})
            row = result.fetchone()

            if not row:
                print(f"❌ Team not found: org_id={org_id}, team_id={team_id}")
                print("   Please check the org_id and team_id are correct")
                return False

            # Check if Azure MCP already exists
            existing_config = row.config_json or {}
            mcp_servers = existing_config.get("mcp_servers", {})

            if isinstance(mcp_servers, dict) and "azure-mcp" in mcp_servers:
                print(f"⚠️  Warning: Azure MCP already configured for team {team_id}")
                response = input("   Overwrite existing configuration? (y/N): ")
                if response.lower() != "y":
                    print("   Aborted.")
                    return False

        # Update configuration
        update_query = text("""
            UPDATE node_configurations
            SET
              config_json = jsonb_set(
                COALESCE(config_json, '{}'::jsonb),
                '{mcp_servers,azure-mcp}',
                :azure_mcp_config::jsonb,
                true
              ),
              updated_at = NOW(),
              version = version + 1,
              updated_by = :updated_by
            WHERE org_id = :org_id
              AND node_id = :team_id
            RETURNING id, org_id, node_id, version
        """)

        with engine.begin() as conn:
            result = conn.execute(
                update_query,
                {
                    "org_id": org_id,
                    "team_id": team_id,
                    "azure_mcp_config": json.dumps(azure_mcp_config),
                    "updated_by": "add_azure_mcp_script",
                },
            )

            row = result.fetchone()
            if row:
                print(f"✅ Successfully added Azure MCP to team {row.node_id}")
                print(f"   Config ID: {row.id}")
                print(f"   Version: {row.version}")
                print()
                print("📝 Configuration added:")
                print(f"   Tenant ID: {tenant_id[:8]}...")
                print(f"   Client ID: {client_id[:8]}...")
                print(f"   Subscription ID: {subscription_id[:8]}...")
                print(f"   Enabled: {enabled}")
                print()
                print("🔍 Verify configuration:")
                print("   SELECT config_json->'mcp_servers'->'azure-mcp'")
                print("   FROM node_configurations")
                print(f"   WHERE org_id = '{org_id}' AND node_id = '{team_id}';")
                return True
            else:
                print("❌ Failed to update team configuration")
                return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Add Azure MCP Server to team configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using command-line arguments
  python scripts/add_azure_mcp.py \\
      --org-id demo-org \\
      --team-id team-sre \\
      --tenant-id "xxx-xxx-xxx" \\
      --client-id "yyy-yyy-yyy" \\
      --client-secret "zzz-zzz-zzz" \\
      --subscription-id "www-www-www"

  # Using environment variables
  export AZURE_TENANT_ID="xxx-xxx-xxx"
  export AZURE_CLIENT_ID="yyy-yyy-yyy"
  export AZURE_CLIENT_SECRET="zzz-zzz-zzz"
  export AZURE_SUBSCRIPTION_ID="www-www-www"
  python scripts/add_azure_mcp.py --org-id demo-org --team-id team-sre

Environment Variables:
  DATABASE_URL              PostgreSQL connection string (required)
  AZURE_TENANT_ID           Azure AD tenant ID (optional, can use --tenant-id)
  AZURE_CLIENT_ID           Service Principal client ID (optional, can use --client-id)
  AZURE_CLIENT_SECRET       Service Principal secret (optional, can use --client-secret)
  AZURE_SUBSCRIPTION_ID     Azure subscription ID (optional, can use --subscription-id)
        """,
    )

    parser.add_argument("--org-id", required=True, help="Organization ID")
    parser.add_argument("--team-id", required=True, help="Team node ID")
    parser.add_argument(
        "--tenant-id", help="Azure Tenant ID (or set AZURE_TENANT_ID env var)"
    )
    parser.add_argument(
        "--client-id", help="Azure Client ID (or set AZURE_CLIENT_ID env var)"
    )
    parser.add_argument(
        "--client-secret",
        help="Azure Client Secret (or set AZURE_CLIENT_SECRET env var)",
    )
    parser.add_argument(
        "--subscription-id",
        help="Azure Subscription ID (or set AZURE_SUBSCRIPTION_ID env var)",
    )
    parser.add_argument(
        "--enabled",
        action="store_true",
        default=True,
        help="Enable the MCP server (default: True)",
    )
    parser.add_argument(
        "--disabled",
        action="store_true",
        help="Disable the MCP server (default: False)",
    )

    args = parser.parse_args()

    # Get credentials from args or environment
    tenant_id = args.tenant_id or os.getenv("AZURE_TENANT_ID")
    client_id = args.client_id or os.getenv("AZURE_CLIENT_ID")
    client_secret = args.client_secret or os.getenv("AZURE_CLIENT_SECRET")
    subscription_id = args.subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID")

    # Validate required credentials
    missing = []
    if not tenant_id:
        missing.append("--tenant-id or AZURE_TENANT_ID")
    if not client_id:
        missing.append("--client-id or AZURE_CLIENT_ID")
    if not client_secret:
        missing.append("--client-secret or AZURE_CLIENT_SECRET")
    if not subscription_id:
        missing.append("--subscription-id or AZURE_SUBSCRIPTION_ID")

    if missing:
        print("❌ Missing required Azure credentials:")
        for item in missing:
            print(f"   - {item}")
        print()
        print(
            "Provide credentials via command-line arguments or environment variables."
        )
        print("See --help for details.")
        sys.exit(1)

    # Determine enabled status
    enabled = not args.disabled if args.disabled else args.enabled

    # Add Azure MCP to team
    success = add_azure_mcp_to_team(
        org_id=args.org_id,
        team_id=args.team_id,
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        subscription_id=subscription_id,
        enabled=enabled,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
