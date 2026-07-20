#!/usr/bin/env python3
"""Create a new Jira issue.

Usage:
    python create_issue.py --project PROJ --summary "Title" --description "Details"
    python create_issue.py --project PROJ --summary "Bug" --type Bug --priority High --labels "incident,p1"
"""

import argparse
import json
import sys

from jira_client import (
    get_browse_url,
    jira_request,
    make_assignee_field,
    make_text_body,
)


def main():
    parser = argparse.ArgumentParser(description="Create a new Jira issue")
    parser.add_argument("--project", required=True, help="Project key (e.g., PROJ)")
    parser.add_argument("--summary", required=True, help="Issue summary/title")
    parser.add_argument("--description", default="", help="Issue description")
    parser.add_argument(
        "--type", default="Task", help="Issue type (Task, Bug, Story, Epic)"
    )
    parser.add_argument("--priority", default="", help="Priority (High, Medium, Low)")
    parser.add_argument("--labels", default="", help="Comma-separated labels")
    parser.add_argument(
        "--assignee",
        default="",
        help="Assignee: Atlassian account ID (Cloud) or username (Data Center)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    try:
        fields = {
            "project": {"key": args.project},
            "summary": args.summary,
            "issuetype": {"name": args.type},
        }
        if args.description:
            # make_text_body picks ADF (Cloud v3) or Wiki Markup string (DC v2).
            fields["description"] = make_text_body(args.description)
        if args.priority:
            fields["priority"] = {"name": args.priority}
        if args.labels:
            fields["labels"] = [l.strip() for l in args.labels.split(",")]

        data = jira_request("POST", "/issue", json_body={"fields": fields})
        issue_key = data["key"]

        if args.assignee:
            try:
                # Assignee field shape differs by API version: Cloud v3 uses
                # accountId, Data Center v2 uses name. make_assignee_field picks.
                jira_request(
                    "PUT",
                    f"/issue/{issue_key}/assignee",
                    json_body=make_assignee_field(args.assignee),
                )
            except Exception:
                pass

        browse_url = get_browse_url()
        result = {
            "ok": True,
            "key": issue_key,
            "id": data.get("id"),
            "summary": args.summary,
            "type": args.type,
        }
        if browse_url:
            result["url"] = f"{browse_url}/browse/{issue_key}"

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Created: {issue_key} - {args.summary}")
            if result.get("url"):
                print(f"URL: {result['url']}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
