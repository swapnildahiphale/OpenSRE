"""Jira ticket follow-up — agent-owned inspect + memory + comment post.

Scheduler owns the clock and calls POST /internal/.../ticket-followup.
This module never advances nudge_due_at; it only decides and may write
Episode memory / post a Jira comment.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Explicit paste only — browse URL or "ticket: KEY" / "ticket KEY".
_BROWSE_RE = re.compile(
    r"/browse/([A-Z][A-Z0-9]+-\d+)\b",
    re.IGNORECASE,
)
_TICKET_LABEL_RE = re.compile(
    r"\btickets?\s*[:=]\s*([A-Z][A-Z0-9]+-\d+)\b",
    re.IGNORECASE,
)
_JIRA_LABEL_RE = re.compile(
    r"\bjira\s*[:=]\s*([A-Z][A-Z0-9]+-\d+)\b",
    re.IGNORECASE,
)
_SOLE_KEY_RE = re.compile(
    r"^\s*([A-Z][A-Z0-9]+-\d+)\s*$",
    re.IGNORECASE,
)

_DONE_STATUS_NAMES = {
    "done",
    "resolved",
    "closed",
    "fixed",
    "complete",
    "completed",
}

_ASK_ASSIGNEE_TMPL = (
    "OpenSRE follow-up ({n} of {max}): this ticket looks resolved, but we could not find "
    "what fixed the production issue. @{assignee} — please reply here with "
    "the action that resolved it so we can record it in investigation memory."
)

_NUDGE_TMPL = (
    "OpenSRE follow-up ({n} of {max}): has this been fixed yet? Please comment with what "
    "was done (or confirm it is still open)."
)

MAX_NUDGES = 3

# Match config-service TEMP cadence for "recent activity" soft-defer.
# Revert with production windows (30m / 3h / 24h) before merge.
_ACTIVITY_WINDOW = {
    0: timedelta(minutes=1),
    1: timedelta(minutes=2),
    2: timedelta(minutes=3),
}

# Conservative: only treat as confirmed fix when still-open comments say so clearly.
_FIX_CONFIRM_RE = re.compile(
    r"(?i)\b("
    r"this (?:is|has been) fixed"
    r"|issue (?:is |has been )?(?:fixed|resolved|mitigated)"
    r"|(?:fixed|resolved|mitigated) (?:it|the issue|in prod(?:uction)?)"
    r"|root cause was\b"
    r"|we (?:restarted|rolled back|reverted)\b.+\b(?:fixed|back to normal|resolved)"
    r"|latency (?:is )?back(?: to normal)?"
    r")\b"
)


def activity_window(nudge_count: int) -> timedelta:
    """How recent a human Jira comment must be to soft-defer a nudge."""
    return _ACTIVITY_WINDOW.get(int(nudge_count or 0), _ACTIVITY_WINDOW[2])


def _is_opensre_followup(text: str) -> bool:
    return (text or "").lstrip().startswith("OpenSRE follow-up")


def _parse_jira_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        # Jira often uses +0000; fromisoformat wants +00:00
        if re.search(r"[+-]\d{4}$", raw):
            raw = raw[:-5] + raw[-5:-2] + ":" + raw[-2:]
        raw = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def extract_explicit_ticket_key(text: str) -> Optional[str]:
    """Return a Jira key only when the user explicitly pasted one.

    Accepts /browse/KEY, ticket:/jira: KEY, or a message that is solely KEY.
    Does not scrape bare keys from long investigation text.
    """
    if not text or not str(text).strip():
        return None
    raw = str(text)
    for pattern in (_BROWSE_RE, _TICKET_LABEL_RE, _JIRA_LABEL_RE):
        m = pattern.search(raw)
        if m:
            return m.group(1).upper()
    m = _SOLE_KEY_RE.match(raw.strip())
    if m:
        return m.group(1).upper()
    return None


_CREATED_LINE_RE = re.compile(
    r"Created:\s*([A-Z][A-Z0-9]+-\d+)\b",
    re.IGNORECASE,
)
_CREATED_JSON_KEY_RE = re.compile(
    r'"key"\s*:\s*"([A-Z][A-Z0-9]+-\d+)"',
    re.IGNORECASE,
)
# create_issue.py OR inline Jira REST create (agent often falls back to requests).
_JIRA_CREATE_SIGNAL_RE = re.compile(
    r"create_issue\.py\b|"
    r"project-jira\b|"
    r"\bJIRA_URL\b|"
    r"\bJIRA_API_TOKEN\b|"
    r"atlassian\.net\b|"
    r"/rest/api/[23]/issue\b",
    re.IGNORECASE,
)


def extract_created_issue_key(
    tool_name: str,
    tool_input: Any,
    tool_output: str,
) -> Optional[str]:
    """Detect a successful Jira issue create and return its key.

    Matches create_issue.py and inline REST creates (Status 201 + Created: KEY).
    Requires a Jira signal in the command and/or a matching /browse/KEY URL
    so unrelated \"Created:\" lines are ignored.
    """
    if not tool_output:
        return None
    cmd_parts: list[str] = [tool_name or ""]
    if isinstance(tool_input, dict):
        for k in ("command", "args", "skill", "description"):
            if tool_input.get(k):
                cmd_parts.append(str(tool_input[k]))
        # Serialized Bash payloads sometimes nest stdout-only; keep command.
    elif tool_input is not None:
        cmd_parts.append(str(tool_input))
    cmd = " ".join(cmd_parts)

    m = _CREATED_LINE_RE.search(tool_output)
    key = m.group(1).upper() if m else None
    if not key:
        m = _CREATED_JSON_KEY_RE.search(tool_output)
        key = m.group(1).upper() if m else None
    if not key:
        return None

    browse_ok = bool(
        re.search(rf"/browse/{re.escape(key)}\b", tool_output, re.IGNORECASE)
    )
    if _JIRA_CREATE_SIGNAL_RE.search(cmd) or browse_ok:
        return key
    return None


def attach_ticket_to_followup(correlation_id: str, ticket_key: str) -> bool:
    """Best-effort bind ticket + reset cadence via config-service."""
    import os

    import httpx

    if not correlation_id or not ticket_key:
        return False
    base = os.getenv("CONFIG_SERVICE_URL", "http://config-service:8080")
    headers = {"X-Internal-Service": "sre-agent"}
    try:
        resp = httpx.post(
            f"{base}/api/v1/internal/investigation-followups/"
            f"{correlation_id}/attach-ticket",
            headers=headers,
            json={"ticket_key": ticket_key, "ticket_provider": "jira"},
            timeout=5.0,
        )
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        logger.info(
            "[FOLLOWUP] ticket attached corr=%s key=%s",
            correlation_id,
            ticket_key,
        )
        return True
    except Exception as e:
        logger.warning(
            "[FOLLOWUP] attach-ticket failed for corr=%s: %s",
            correlation_id,
            e,
        )
        return False


def _load_jira_client():
    """Import project-jira scripts client (same env as skills)."""
    scripts = (
        Path(__file__).resolve().parent / ".claude" / "skills" / "project-jira" / "scripts"
    )
    path = str(scripts)
    if path not in sys.path:
        sys.path.insert(0, path)
    import jira_client  # type: ignore

    return jira_client


def _status_is_done(status_name: Optional[str], status_category: Optional[str]) -> bool:
    if status_category and status_category.strip().lower() in {"done", "complete"}:
        return True
    if status_name and status_name.strip().lower() in _DONE_STATUS_NAMES:
        return True
    return False


def _comment_records(issue: dict, extract_adf_text=None) -> list[dict[str, Any]]:
    """Return [{text, created}] for issue comments (created may be None)."""
    fields = issue.get("fields") or {}
    comments = ((fields.get("comment") or {}).get("comments")) or []
    out: list[dict[str, Any]] = []
    for c in comments:
        body = c.get("body")
        if isinstance(body, str):
            text = body.strip()
        elif extract_adf_text is not None:
            text = (extract_adf_text(body) or "").strip()
        else:
            text = ""
        if not text:
            continue
        out.append({"text": text, "created": _parse_jira_dt(c.get("created"))})
    return out


def _comment_bodies(issue: dict, extract_adf_text=None) -> list[str]:
    return [c["text"] for c in _comment_records(issue, extract_adf_text)]


def _has_recent_human_activity(
    records: list[dict[str, Any]],
    *,
    now: datetime,
    within: timedelta,
) -> bool:
    """True when a non-OpenSRE comment was created within `within` of now."""
    cutoff = now - within
    for rec in records:
        text = rec.get("text") or ""
        if _is_opensre_followup(text):
            continue
        created = rec.get("created")
        if created is None:
            # No timestamp — treat as activity only if we cannot tell age;
            # prefer not to soft-defer forever on undated comments.
            continue
        if created >= cutoff:
            return True
    return False


def _fix_confirm_from_comments(records: list[dict[str, Any]]) -> Optional[str]:
    """Return fix text when a still-open ticket has an explicit confirm comment."""
    for rec in reversed(records):
        text = (rec.get("text") or "").strip()
        if not text or _is_opensre_followup(text):
            continue
        if _FIX_CONFIRM_RE.search(text):
            return text[:2000]
    return None


def _extract_fix_text(
    issue: dict,
    records: list[dict[str, Any]],
    extract_adf_text=None,
) -> Optional[str]:
    """Return proven fix text for a Done ticket, or None to ask the assignee.

    Only explicit human confirmation in comments counts. Jira resolution
    name/description are workflow metadata (e.g. Done → \"Work has been
    completed on this issue.\") and the issue description is usually the
    original problem / recommended fix — neither proves what was implemented.
    """
    del issue, extract_adf_text
    return _fix_confirm_from_comments(records)


def fetch_issue(ticket_key: str) -> dict[str, Any]:
    jira_client = _load_jira_client()
    data = jira_client.jira_request(
        "GET",
        f"/issue/{ticket_key}",
        params={"fields": "summary,status,resolution,description,assignee,comment"},
    )
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected Jira response for {ticket_key}")
    return data


def post_jira_comment(ticket_key: str, text: str) -> None:
    jira_client = _load_jira_client()
    jira_client.jira_request(
        "POST",
        f"/issue/{ticket_key}/comment",
        json_body={"body": jira_client.make_text_body(text)},
    )


def evaluate_ticket_followup(
    *,
    correlation_id: str,
    ticket_key: str,
    has_active_run: bool = False,
    nudge_count: int = 0,
    now: Optional[datetime] = None,
    apply_resolution_fn=None,
    fetch_issue_fn=None,
    post_comment_fn=None,
) -> dict[str, Any]:
    """Decide follow-up action for a linked Jira ticket.

    Returns dict with keys:
      action: resolved | ask_assignee | nudge | skip | defer
      ticket_key, comment_text (optional), fix_summary (optional)
    """
    if has_active_run:
        return {
            "action": "skip",
            "ticket_key": ticket_key,
            "reason": "active_run",
        }

    fetch = fetch_issue_fn or fetch_issue
    post = post_comment_fn or post_jira_comment
    apply = apply_resolution_fn
    n = min(max(int(nudge_count or 0) + 1, 1), MAX_NUDGES)
    clock = now or datetime.now(timezone.utc)

    try:
        issue = fetch(ticket_key)
    except Exception as e:
        logger.warning(
            "[TICKET_FOLLOWUP] fetch failed corr=%s key=%s: %s",
            correlation_id,
            ticket_key,
            e,
        )
        return {
            "action": "defer",
            "ticket_key": ticket_key,
            "reason": f"jira_fetch_failed: {e}",
        }

    extract_adf = None
    if fetch_issue_fn is None:
        try:
            extract_adf = _load_jira_client().extract_adf_text
        except Exception:
            extract_adf = None

    fields = issue.get("fields") or {}
    status = fields.get("status") or {}
    status_name = status.get("name")
    status_category = (status.get("statusCategory") or {}).get("name")
    records = _comment_records(issue, extract_adf)
    assignee = None
    if isinstance(fields.get("assignee"), dict):
        assignee = fields["assignee"].get("displayName") or fields["assignee"].get(
            "name"
        )

    if _status_is_done(status_name, status_category):
        fix = _extract_fix_text(issue, records, extract_adf)
        if fix:
            if apply is None:
                from resolution_tool import apply_resolution

                apply = apply_resolution
            return {
                "action": "resolved",
                "ticket_key": ticket_key,
                "fix_summary": fix,
                "_apply": apply,
                "_apply_kwargs": {
                    "thread_id": correlation_id,
                    "text": fix,
                    "resolved_by": assignee or "jira",
                    "matched_suggestion": "unsure",
                    "fix_summary": fix,
                },
            }

        text = _ASK_ASSIGNEE_TMPL.format(
            assignee=assignee or "assignee", n=n, max=MAX_NUDGES
        )
        try:
            post(ticket_key, text)
        except Exception as e:
            logger.warning(
                "[TICKET_FOLLOWUP] ask_assignee comment failed key=%s: %s",
                ticket_key,
                e,
            )
            return {
                "action": "defer",
                "ticket_key": ticket_key,
                "reason": f"jira_comment_failed: {e}",
            }
        return {
            "action": "ask_assignee",
            "ticket_key": ticket_key,
            "comment_text": text,
        }

    # Still open — explicit fix confirmation in comments wins over soft-defer.
    fix_open = _fix_confirm_from_comments(records)
    if fix_open:
        if apply is None:
            from resolution_tool import apply_resolution

            apply = apply_resolution
        return {
            "action": "resolved",
            "ticket_key": ticket_key,
            "fix_summary": fix_open,
            "_apply": apply,
            "_apply_kwargs": {
                "thread_id": correlation_id,
                "text": fix_open,
                "resolved_by": assignee or "jira",
                "matched_suggestion": "unsure",
                "fix_summary": fix_open,
            },
        }

    if _has_recent_human_activity(
        records, now=clock, within=activity_window(nudge_count)
    ):
        return {
            "action": "defer",
            "ticket_key": ticket_key,
            "reason": "recent_activity",
        }

    text = _NUDGE_TMPL.format(n=n, max=MAX_NUDGES)
    try:
        post(ticket_key, text)
    except Exception as e:
        logger.warning(
            "[TICKET_FOLLOWUP] nudge comment failed key=%s: %s", ticket_key, e
        )
        return {
            "action": "defer",
            "ticket_key": ticket_key,
            "reason": f"jira_comment_failed: {e}",
        }
    return {
        "action": "nudge",
        "ticket_key": ticket_key,
        "comment_text": text,
    }


async def run_ticket_followup(
    *,
    correlation_id: str,
    ticket_key: str,
    has_active_run: bool = False,
    nudge_count: int = 0,
) -> dict[str, Any]:
    """Async entry used by the HTTP handler (awaits apply_resolution when needed)."""
    result = evaluate_ticket_followup(
        correlation_id=correlation_id,
        ticket_key=ticket_key,
        has_active_run=has_active_run,
        nudge_count=nudge_count,
    )
    apply = result.pop("_apply", None)
    kwargs = result.pop("_apply_kwargs", None)
    if apply is not None and kwargs is not None:
        await apply(**kwargs)
    return result
