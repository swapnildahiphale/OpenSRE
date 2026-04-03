#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `import src.*` works when running as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import argparse

from sqlalchemy import select
from src.core.dotenv import load_dotenv
from src.core.security import get_token_pepper
from src.db.models import NodeType, OrgNode
from src.db.repository import issue_team_token
from src.db.session import db_session


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Issue an opaque bearer token for a team."
    )
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--team-node-id", required=True)
    parser.add_argument("--issued-by", default="admin")
    parser.add_argument(
        "--ensure-team-node",
        action="store_true",
        help="Create team node if missing (parent required).",
    )
    parser.add_argument(
        "--parent-node-id", help="Parent node id (required if --ensure-team-node)"
    )
    parser.add_argument("--team-name", default=None)
    args = parser.parse_args()

    pepper = get_token_pepper()

    with db_session() as s:
        team = s.execute(
            select(OrgNode).where(
                OrgNode.org_id == args.org_id, OrgNode.node_id == args.team_node_id
            )
        ).scalar_one_or_none()

        if team is None and args.ensure_team_node:
            if not args.parent_node_id:
                raise SystemExit(
                    "--parent-node-id is required when --ensure-team-node is set"
                )
            s.add(
                OrgNode(
                    org_id=args.org_id,
                    node_id=args.team_node_id,
                    parent_id=args.parent_node_id,
                    node_type=NodeType.team,
                    name=args.team_name,
                )
            )
        elif team is None:
            raise SystemExit(
                "Team node not found. Create it first (or pass --ensure-team-node)."
            )

        token = issue_team_token(
            s,
            org_id=args.org_id,
            team_node_id=args.team_node_id,
            issued_by=args.issued_by,
            pepper=pepper,
        )

    print("TOKEN (save this; it won't be shown again):")
    print(token)


if __name__ == "__main__":
    load_dotenv()
    main()
