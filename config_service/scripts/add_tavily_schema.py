#!/usr/bin/env python3
"""Add Tavily integration schema to the database."""

import os
import sys

from sqlalchemy import create_engine, text

# Database connection from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Error: DATABASE_URL environment variable not set")
    sys.exit(1)


def main():
    """Add Tavily integration schema to database."""
    engine = create_engine(DATABASE_URL)

    try:
        with engine.begin() as conn:
            # Check if Tavily already exists
            result = conn.execute(
                text("SELECT id FROM integration_schemas WHERE id = 'tavily'")
            )
            if result.fetchone():
                print("ℹ️  Tavily integration schema already exists")
                return

            # Insert Tavily schema
            conn.execute(
                text("""
                INSERT INTO integration_schemas (
                    id, name, category, description, docs_url, icon_url,
                    display_order, featured, fields, created_at, updated_at
                ) VALUES (
                    :id, :name, :category, :description, :docs_url, :icon_url,
                    :display_order, :featured, :fields::jsonb, NOW(), NOW()
                )
            """),
                {
                    "id": "tavily",
                    "name": "Tavily",
                    "category": "search",
                    "description": "Tavily Search API for web search capabilities",
                    "docs_url": "https://tavily.com/",
                    "icon_url": None,
                    "display_order": 200,
                    "featured": False,
                    "fields": """[
                    {
                        "name": "api_key",
                        "type": "secret",
                        "required": true,
                        "level": "org",
                        "description": "Tavily API key",
                        "placeholder": "tvly-..."
                    }
                ]""",
                },
            )

            print("✅ Successfully added Tavily integration schema to database")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
