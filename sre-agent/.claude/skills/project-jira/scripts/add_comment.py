#!/usr/bin/env python3
"""Add a comment to a Jira issue.

Usage:
    python add_comment.py --issue-key PROJ-123 --comment "Investigation findings..."
"""

import argparse
import json
import sys

from jira_client import jira_request, make_text_body


def main():
    parser = argparse.ArgumentParser(description="Add comment to a Jira issue")
    parser.add_argument("--issue-key", required=True, help="Issue key (e.g., PROJ-123)")
    parser.add_argument("--comment", required=True, help="Comment text")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    try:
        data = jira_request(
            "POST",
            f"/issue/{args.issue_key}/comment",
            # make_text_body picks ADF (Cloud v3) or Wiki Markup string (DC v2).
            json_body={"body": make_text_body(args.comment)},
        )
        author = data.get("author", {})
        result = {
            "ok": True,
            "id": data.get("id"),
            "issue_key": args.issue_key,
            "author": author.get("displayName"),
            "created": data.get("created"),
        }

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Comment added to {args.issue_key}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
