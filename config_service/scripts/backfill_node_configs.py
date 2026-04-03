"""
One-time script to backfill node_configurations for existing org nodes.

This fixes orgs/teams created before we added automatic config creation.
"""

from src.db.config_repository import get_or_create_node_configuration
from src.db.models import OrgNode
from src.db.session import get_session_maker


def backfill():
    SessionMaker = get_session_maker()
    session = SessionMaker()
    try:
        # Get all nodes
        nodes = session.query(OrgNode).all()

        created_count = 0
        for node in nodes:
            # This will create if doesn't exist, or return existing
            config = get_or_create_node_configuration(
                session, node.org_id, node.node_id, node.node_type.value
            )
            if config.version == 1 and not config.config_json:
                created_count += 1
                print(
                    f"Created config for {node.org_id}/{node.node_id} ({node.node_type.value})"
                )

        session.commit()
        print(f"\nBackfill complete! Created {created_count} new configurations.")
        print(f"Total nodes: {len(nodes)}")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    backfill()
