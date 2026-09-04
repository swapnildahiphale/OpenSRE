"""Shared fixtures and path setup for sre-agent tests."""

import json
import os
import sys

import pytest

# Never export telemetry from the test suite.
#
# agent.py calls load_dotenv() and initializes the observability backend at
# import time, so with Langfuse credentials in the repo .env every test that
# drives a session would ship spans to the real project — junk traces with
# session ids like "t-debounce", plus network calls that make tests slow and
# flaky. load_dotenv() does not override variables that are already set, and
# conftest is imported before any test module, so setting this here wins.
os.environ["OBSERVABILITY_BACKEND"] = "none"

# Add sre-agent root to sys.path so local modules (config, agent, events, ...) are importable
SRE_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRE_AGENT_ROOT not in sys.path:
    sys.path.insert(0, SRE_AGENT_ROOT)

# Path to config_service templates (relative to this file's location)
_REPO_ROOT = os.path.dirname(SRE_AGENT_ROOT)
_TEMPLATE_PATH = os.path.join(
    _REPO_ROOT, "config_service", "templates", "01_slack_incident_triage.json"
)


@pytest.fixture
def sample_team_config():
    """Load the POC incident-triage template into a TeamConfig for testing."""
    from config import MemoryConfig, SkillsConfig, TeamConfig, _parse_agents

    with open(_TEMPLATE_PATH) as f:
        raw = json.load(f)

    return TeamConfig(
        agents=_parse_agents(raw.get("agents", {})),
        skills=SkillsConfig(),
        memory=MemoryConfig(),
        team_context=[],
        raw_config=raw,
    )
