"""The task under evaluation: run one real investigation against the agent.

The eval deliberately drives the agent over its HTTP/SSE API rather than
importing InteractiveAgentSession. That way an experiment measures the system a
responder actually talks to — server, config-service team resolution, skills,
subagents and memory included — instead of a re-implementation of it.
"""

import json
import time
from typing import Any

import requests

from .config import (
    ADMIN_TOKEN,
    AGENT_URL,
    CONFIG_SERVICE_URL,
    SCENARIO_TIMEOUT_SECONDS,
)

# Cached so a full experiment run mints one token instead of one per scenario.
_team_token: str | None = None


def get_team_token() -> str:
    """Return a team token for the agent API, minting one if needed.

    Investigations run under a team token (not the admin token) because the
    agent resolves org/team — and therefore config, skills and memory — from it.
    """
    global _team_token
    if _team_token is not None:
        return _team_token

    import os

    if os.getenv("EVAL_TEAM_TOKEN"):
        _team_token = os.environ["EVAL_TEAM_TOKEN"]
        return _team_token

    response = requests.post(
        f"{CONFIG_SERVICE_URL}/api/v1/admin/orgs/local/teams/default/tokens",
        headers={
            "Authorization": f"Bearer {ADMIN_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "description": "langfuse-eval",
            "permissions": ["team:read", "team:write"],
        },
        timeout=15,
    )
    response.raise_for_status()
    _team_token = response.json()["token"]
    return _team_token


def _event_payload(raw_line: str) -> dict[str, Any] | None:
    """Parse one `data: {...}` SSE line into an event dict."""
    if not raw_line.startswith("data: "):
        return None
    body = raw_line[len("data: ") :]
    if body.strip() in ("", "[DONE]"):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def run_investigation(prompt: str, timeout: int = SCENARIO_TIMEOUT_SECONDS) -> dict:
    """Send one prompt to the agent and collect the full investigation result.

    Returns a dict shaped for the evaluators:
        report      final report text the agent produced
        trajectory  every tool call, in order, with its input and attribution
        skills      skill ids the agent loaded
        succeeded   whether the agent reported a successful terminal result
        duration_seconds / error / thread_id
    """
    started = time.monotonic()
    report = ""
    trajectory: list[dict[str, Any]] = []
    skills: list[str] = []
    succeeded = False
    error: str | None = None
    thread_id: str | None = None

    # A transport failure must fail this one scenario, not abort the whole
    # experiment — the other items still carry information, and a run that dies
    # halfway is worse than a run with one recorded failure.
    try:
        response = requests.post(
            f"{AGENT_URL}/investigate",
            json={"prompt": prompt},
            headers={
                "Authorization": f"Bearer {get_team_token()}",
                "Content-Type": "application/json",
            },
            stream=True,
            timeout=timeout,
        )
        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=True):
            event = _event_payload(line or "")
            if event is None:
                continue

            event_type = event.get("type")
            data = event.get("data") or {}
            thread_id = event.get("thread_id") or thread_id

            if event_type == "tool_start":
                tool_input = data.get("input") or {}
                trajectory.append(
                    {
                        "name": data.get("name", ""),
                        "input": tool_input,
                        "agent_type": data.get("agent_type"),
                        "depth": data.get("depth", 0),
                    }
                )
                # Skill loads arrive as a `Skill` tool call naming the skill.
                if str(data.get("name", "")).lower() == "skill":
                    skill = tool_input.get("skill") or tool_input.get("name")
                    if skill:
                        skills.append(str(skill))

            elif event_type == "result":
                # The terminal result carries the final report text.
                report = data.get("text", "") or report
                succeeded = bool(data.get("success"))

            elif event_type == "error":
                error = data.get("message")

    except requests.exceptions.Timeout:
        error = f"Agent did not respond within {timeout}s"
        succeeded = False
    except requests.exceptions.RequestException as exc:
        # Covers connection resets and mid-stream disconnects, which otherwise
        # surface as an exception partway through iter_lines().
        error = f"Transport error talking to the agent: {exc}"
        succeeded = False

    return {
        "report": report,
        "trajectory": trajectory,
        "skills": sorted(set(skills)),
        "succeeded": succeeded,
        "error": error,
        "thread_id": thread_id,
        "duration_seconds": round(time.monotonic() - started, 1),
    }


def investigation_task(*, item, **kwargs) -> dict:
    """Langfuse experiment task: run the agent on one dataset item.

    Reads only `item.input` — never `item.expected_output`, which would leak the
    answer into the system being measured.
    """
    # Langfuse passes a DatasetItem for hosted datasets and a plain dict for
    # local data; support both so the runner works either way.
    item_input = item.input if hasattr(item, "input") else item["input"]
    return run_investigation(item_input["prompt"])
