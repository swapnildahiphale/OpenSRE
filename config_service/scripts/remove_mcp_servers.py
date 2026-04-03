#!/usr/bin/env python3
"""Remove MCP servers from team_a config"""

import json
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Database connection from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Error: DATABASE_URL environment variable not set")
    sys.exit(1)


def main():
    """Remove MCP servers from team_a"""
    engine = create_engine(DATABASE_URL)

    try:
        with engine.begin() as conn:
            # Get current config
            result = conn.execute(
                text("""
                SELECT config_json
                FROM node_configurations
                WHERE org_id = :org_id AND node_id = :node_id
            """),
                {"org_id": "internal-test", "node_id": "team_a"},
            )

            row = result.fetchone()
            if not row:
                print("❌ Error: team_a not found")
                sys.exit(1)

            current_config = row[0] if row[0] else {}
            print(f"Current config keys: {list(current_config.keys())}")
            print(f"Current MCP servers: {current_config.get('mcp_servers', {})}")

            # Update config to remove MCP servers
            current_config["mcp_servers"] = {}

            # Save updated config
            conn.execute(
                text("""
                UPDATE node_configurations
                SET config_json = :config_json,
                    updated_at = NOW()
                WHERE org_id = :org_id AND node_id = :node_id
            """),
                {
                    "org_id": "internal-test",
                    "node_id": "team_a",
                    "config_json": json.dumps(current_config),
                },
            )

            print("✅ Successfully removed MCP servers from team_a")
            print(f"Updated MCP servers: {current_config.get('mcp_servers', {})}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
