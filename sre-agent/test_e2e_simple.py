"""
End-to-end smoke test for OpenSRE simple mode.

Runs against a live local stack started with:
  docker compose -f docker-compose.yml -f docker-compose.override.yml \
    up -d postgres config-service neo4j sre-agent web-ui

Usage:
  cd sre-agent
  AGENT_BASE=http://localhost:8000 uv run pytest test_e2e_simple.py -v

Environment variables:
  AGENT_BASE      sre-agent base URL  (default: http://localhost:8000)
  CONFIG_BASE     config-service URL  (default: http://localhost:8080)

NOTE: This test is intentionally placed at sre-agent/ root (not under tests/)
so that `uv run pytest tests/` does NOT collect it during unit-test runs.
A real ANTHROPIC_API_KEY and a running stack are required.
"""

import json
import os
import uuid

import httpx

BASE = os.getenv("AGENT_BASE", "http://localhost:8000")
CONFIG_BASE = os.getenv("CONFIG_BASE", "http://localhost:8080")
# Episodes are stored under the agent's tenant id (OPENSRE_TENANT_ID; "local" in
# the simple-mode POC), not "default". Query the same org the finalizer writes to.
ORG_ID = os.getenv("OPENSRE_TENANT_ID", "local")


def test_health_simple_mode():
    """Confirm sre-agent is up and reports mode=simple."""
    r = httpx.get(f"{BASE}/health", timeout=10)
    assert r.status_code == 200, f"health returned {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("status") == "healthy", f"unexpected health body: {body}"
    assert body.get("mode") == "simple", (
        f"expected mode=simple, got {body.get('mode')!r}. "
        "Is the stack running server_simple.py?"
    )


def test_investigate_streams_events_and_stores_episode():
    """
    POST /investigate with a simple prompt, consume the SSE stream, and verify:
    1. Stream contains a 'result' event (investigation completed).
    2. Stream contains at least one of 'thought' or 'tool_start' (agent was active).
    3. config-service episode store has at least one episode for org=default.
    """
    tid = f"smoke-{uuid.uuid4().hex[:8]}"
    seen: set[str] = set()

    with httpx.stream(
        "POST",
        f"{BASE}/investigate",
        json={
            "prompt": "List pods in the default namespace and report status.",
            "thread_id": tid,
        },
        timeout=300,
    ) as r:
        assert r.status_code == 200, f"/investigate returned {r.status_code}"
        for line in r.iter_lines():
            if line.startswith("data: "):
                try:
                    payload = json.loads(line[6:])
                    event_type = payload.get("type")
                    if event_type:
                        seen.add(event_type)
                except json.JSONDecodeError:
                    pass  # skip malformed lines

    assert (
        "result" in seen
    ), f"Stream did not emit a 'result' event. Events seen: {seen}"
    assert seen & {"thought", "tool_start"}, (
        f"Stream had no 'thought' or 'tool_start' event — agent may not have run. "
        f"Events seen: {seen}"
    )

    # Verify at least one episode was persisted in the config-service
    stats_r = httpx.get(
        f"{CONFIG_BASE}/api/v1/internal/episodes/stats",
        params={"org_id": ORG_ID},
        headers={"X-Internal-Service": "sre-agent"},
        timeout=15,
    )
    # Episode endpoint may not exist yet — treat 404 as a soft skip rather than fail
    if stats_r.status_code == 404:
        import pytest

        pytest.skip(
            "Episode stats endpoint not found (404) — skipping episode assertion. "
            "Verify manually via config-service logs."
        )
    assert (
        stats_r.status_code == 200
    ), f"Episode stats returned {stats_r.status_code}: {stats_r.text}"
    stats = stats_r.json()
    assert (
        stats.get("total_episodes", 0) >= 1
    ), f"Expected at least 1 episode stored, got: {stats}"
