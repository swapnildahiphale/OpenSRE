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
    from config import (
        AgentConfig,
        MemoryConfig,
        ModelConfig,
        PromptConfig,
        SkillsConfig,
        TeamConfig,
        _coerce_tools,
    )

    with open(_TEMPLATE_PATH) as f:
        raw = json.load(f)

    agents = {}
    for name, cfg in raw.get("agents", {}).items():
        prompt_data = cfg.get("prompt", {})
        tools_data = cfg.get("tools", {})
        model_data = cfg.get("model", {})
        agents[name] = AgentConfig(
            enabled=cfg.get("enabled", True),
            name=name,
            prompt=PromptConfig(
                system=prompt_data.get("system", ""),
                prefix=prompt_data.get("prefix", ""),
                suffix=prompt_data.get("suffix", ""),
            ),
            tools=_coerce_tools(tools_data),
            skills=cfg.get("skills", {}),
            model=ModelConfig(
                name=model_data.get("name", "claude-sonnet-4-6"),
                temperature=model_data.get("temperature"),
                max_tokens=model_data.get("max_tokens"),
                top_p=model_data.get("top_p"),
            ),
            max_turns=cfg.get("max_turns"),
            sub_agents=cfg.get("sub_agents", {}),
        )

    return TeamConfig(
        agents=agents,
        skills=SkillsConfig(),
        memory=MemoryConfig(),
        team_context=[],
        raw_config=raw,
    )
