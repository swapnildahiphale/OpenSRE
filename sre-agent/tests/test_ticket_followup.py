"""Tests for explicit ticket extract + ticket follow-up decisions."""

import pytest

from ticket_followup import (
    evaluate_ticket_followup,
    extract_created_issue_key,
    extract_explicit_ticket_key,
)


def test_extract_browse_url():
    assert (
        extract_explicit_ticket_key(
            "see https://jira.example.com/browse/HIX-42 for ops"
        )
        == "HIX-42"
    )


def test_extract_ticket_label():
    assert extract_explicit_ticket_key("please track ticket: abc-9") == "ABC-9"


def test_extract_sole_key():
    assert extract_explicit_ticket_key("  OPS-100  ") == "OPS-100"


def test_extract_ignores_bare_key_in_long_text():
    text = (
        "Investigate checkout latency. Similar to OPS-100 last week but "
        "this is a new spike after deploy."
    )
    assert extract_explicit_ticket_key(text) is None


def test_extract_created_issue_from_bash_output():
    key = extract_created_issue_key(
        "Bash",
        {
            "command": (
                "python .claude/skills/project-jira/scripts/create_issue.py "
                '--project HIX --summary "Checkout latency"'
            )
        },
        "Created: OPS-991 - Checkout latency\n"
        "URL: https://example.atlassian.net/browse/OPS-991\n",
    )
    assert key == "OPS-991"


def test_extract_created_issue_from_json_output():
    key = extract_created_issue_key(
        "Bash",
        {"command": "python create_issue.py --project OPS --summary x --json"},
        '{"ok": true, "key": "OPS-55", "summary": "x"}',
    )
    assert key == "OPS-55"


def test_extract_created_issue_ignores_unrelated_bash():
    assert (
        extract_created_issue_key(
            "Bash",
            {"command": "echo hello"},
            "Created: OPS-1 - nope",
        )
        is None
    )


def test_extract_created_issue_from_inline_jira_rest():
    """Agent often creates via requests when create_issue.py hits field errors."""
    key = extract_created_issue_key(
        "Bash",
        {
            "command": (
                "python3 - <<'EOF'\n"
                "import os, requests\n"
                'url = os.environ.get("JIRA_URL", "").rstrip("/")\n'
                'token = os.environ.get("JIRA_API_TOKEN", "")\n'
                "requests.post(f'{url}/rest/api/3/issue', ...)\n"
                "EOF"
            )
        },
        'Status: 201\nCreated: OPS-42\n'
        "URL: https://example.atlassian.net/browse/OPS-42",
    )
    assert key == "OPS-42"


def test_extract_created_issue_from_browse_url_alone():
    key = extract_created_issue_key(
        "Bash",
        {"command": "python3 /tmp/make_ticket.py"},
        "Created: TAHOE-12\nURL: https://example.atlassian.net/browse/TAHOE-12",
    )
    assert key == "TAHOE-12"


def test_skip_when_active_run():
    out = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-1",
        has_active_run=True,
    )
    assert out["action"] == "skip"


def test_resolved_with_fix_applies_memory():
    applied = {}

    async def fake_apply(**kwargs):
        applied.update(kwargs)
        return {"status": "confirmed"}

    issue = {
        "fields": {
            "status": {"name": "Done", "statusCategory": {"name": "Done"}},
            "resolution": {
                "name": "Done",
                "description": "Work has been completed on this issue.",
            },
            "assignee": {"displayName": "Ada"},
            "comment": {
                "comments": [
                    {
                        "body": (
                            "Restarted redis pool and checkout latency is back "
                            "to normal — this is fixed."
                        ),
                        "created": "2026-09-18T11:00:00+00:00",
                    }
                ]
            },
            "description": "short",
        }
    }

    result = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-1",
        apply_resolution_fn=fake_apply,
        fetch_issue_fn=lambda _k: issue,
        post_comment_fn=lambda *_a, **_k: None,
    )
    assert result["action"] == "resolved"
    assert "redis" in result["fix_summary"].lower()
    assert result["_apply_kwargs"]["thread_id"] == "thread-1"


def test_ask_assignee_when_done_with_generic_resolution_description():
    """Cloud Done resolution.description is boilerplate — must ask, not resolve."""
    posted = []
    issue = {
        "fields": {
            "status": {"name": "Done", "statusCategory": {"name": "Done"}},
            "resolution": {
                "name": "Done",
                "description": "Work has been completed on this issue.",
            },
            "assignee": {"displayName": "Amol"},
            "comment": {"comments": []},
            "description": "long investigation text " + ("x" * 80),
        }
    }
    result = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-42",
        fetch_issue_fn=lambda _k: issue,
        post_comment_fn=lambda key, text: posted.append(text),
    )
    assert result["action"] == "ask_assignee"
    assert posted and "Amol" in posted[0]


def test_ask_assignee_when_done_without_fix():
    posted = []
    issue = {
        "fields": {
            "status": {"name": "Resolved", "statusCategory": {"name": "Done"}},
            "resolution": {"name": "Done"},
            "assignee": {"displayName": "Bob"},
            "comment": {"comments": []},
            "description": "tiny",
        }
    }
    result = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-2",
        fetch_issue_fn=lambda _k: issue,
        post_comment_fn=lambda key, text: posted.append((key, text)),
    )
    assert result["action"] == "ask_assignee"
    assert posted and "Bob" in posted[0][1]


def test_ask_assignee_when_done_but_only_ticket_description():
    """Bug: description is investigation text, not proof the fix was applied."""
    posted = []
    issue = {
        "fields": {
            "status": {"name": "Done", "statusCategory": {"name": "Done"}},
            "resolution": {"name": "Done"},
            "assignee": {"displayName": "Amol"},
            "comment": {
                "comments": [
                    {
                        "body": "OpenSRE follow-up (1 of 3): has this been fixed yet?",
                        "created": "2026-09-18T11:00:00+00:00",
                    }
                ]
            },
            "description": (
                "The sandbox deploy failed. Fix: Add the ECR digest pin placeholder "
                "to dags/tahoe_yonyx.py. Build: https://jenkins.example/2/console"
            ),
        }
    }
    result = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-42",
        fetch_issue_fn=lambda _k: issue,
        post_comment_fn=lambda key, text: posted.append(text),
    )
    assert result["action"] == "ask_assignee"
    assert posted and "Amol" in posted[0]


def test_nudge_when_still_open():
    posted = []
    issue = {
        "fields": {
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "comment": {"comments": []},
            "description": "",
        }
    }
    result = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-3",
        nudge_count=1,
        fetch_issue_fn=lambda _k: issue,
        post_comment_fn=lambda key, text: posted.append(text),
    )
    assert result["action"] == "nudge"
    assert "fixed yet" in posted[0].lower()
    assert "2 of 3" in posted[0]


def test_soft_defer_when_recent_human_comment_and_still_open():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    issue = {
        "fields": {
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "comment": {
                "comments": [
                    {
                        "body": "Looking at redis pool saturation now",
                        "created": (now - timedelta(seconds=30)).isoformat(),
                    }
                ]
            },
            "description": "",
        }
    }
    posted = []
    result = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-4",
        nudge_count=0,
        now=now,
        fetch_issue_fn=lambda _k: issue,
        post_comment_fn=lambda key, text: posted.append(text),
    )
    assert result["action"] == "defer"
    assert result["reason"] == "recent_activity"
    assert posted == []


def test_nudge_when_human_comment_is_stale():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    issue = {
        "fields": {
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "comment": {
                "comments": [
                    {
                        "body": "Started looking yesterday",
                        "created": (now - timedelta(hours=2)).isoformat(),
                    }
                ]
            },
            "description": "",
        }
    }
    posted = []
    result = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-5",
        nudge_count=0,
        now=now,
        fetch_issue_fn=lambda _k: issue,
        post_comment_fn=lambda key, text: posted.append(text),
    )
    assert result["action"] == "nudge"
    assert posted


def test_soft_defer_ignores_opensre_followup_comments():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    issue = {
        "fields": {
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "comment": {
                "comments": [
                    {
                        "body": (
                            "OpenSRE follow-up (1 of 3): has this been fixed yet?"
                        ),
                        "created": (now - timedelta(seconds=20)).isoformat(),
                    }
                ]
            },
            "description": "",
        }
    }
    result = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-6",
        nudge_count=1,
        now=now,
        fetch_issue_fn=lambda _k: issue,
        post_comment_fn=lambda *_a, **_k: None,
    )
    assert result["action"] == "nudge"


def test_resolve_when_still_open_but_fix_confirmed_in_comment():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    async def fake_apply(**kwargs):
        return {"status": "confirmed"}

    issue = {
        "fields": {
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "assignee": {"displayName": "Ada"},
            "comment": {
                "comments": [
                    {
                        "body": (
                            "Restarted the redis pool and checkout latency is back "
                            "to normal — this is fixed."
                        ),
                        "created": (now - timedelta(minutes=10)).isoformat(),
                    }
                ]
            },
            "description": "",
        }
    }
    result = evaluate_ticket_followup(
        correlation_id="thread-1",
        ticket_key="OPS-7",
        nudge_count=0,
        now=now,
        apply_resolution_fn=fake_apply,
        fetch_issue_fn=lambda _k: issue,
        post_comment_fn=lambda *_a, **_k: None,
    )
    assert result["action"] == "resolved"
    assert "redis" in result["fix_summary"].lower()
