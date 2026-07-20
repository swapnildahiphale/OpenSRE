"""Tests for reachability-based sub-agent registry resolution (KI-1 fix)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    AgentConfig,
    PromptConfig,
    TeamConfig,
    resolve_registered_agents,
)


def _agent(name, enabled=True, system="prompt", sub_agents=None):
    return AgentConfig(
        enabled=enabled,
        name=name,
        prompt=PromptConfig(system=system),
        sub_agents=sub_agents or {},
    )


def _starship():
    """planner -> {investigation, coding, writeup}; investigation -> 3 children."""
    return TeamConfig(
        agents={
            "planner": _agent(
                "planner",
                sub_agents={"investigation": True, "coding": True, "writeup": True},
            ),
            "investigation": _agent(
                "investigation",
                sub_agents={"github": True, "kubernetes": True, "metrics": True},
            ),
            "coding": _agent("coding"),
            "writeup": _agent("writeup"),
            "github": _agent("github"),
            "kubernetes": _agent("kubernetes"),
            "metrics": _agent("metrics"),
        }
    )


def test_default_topology_registers_all_nonroot():
    result = resolve_registered_agents(_starship())
    assert set(result) == {
        "investigation",
        "coding",
        "writeup",
        "github",
        "kubernetes",
        "metrics",
    }
    assert "planner" not in result  # root excluded


def test_disabling_subagent_edge_drops_child():
    tc = _starship()
    tc.agents["investigation"].sub_agents["github"] = False
    result = resolve_registered_agents(tc)
    assert "github" not in result
    assert {"investigation", "kubernetes", "metrics"} <= set(result)


def test_disabling_midtier_cascades_to_children():
    tc = _starship()
    tc.agents["investigation"].enabled = False
    result = resolve_registered_agents(tc)
    # investigation and ALL its children are unreachable
    assert "investigation" not in result
    assert (
        "github" not in result
        and "kubernetes" not in result
        and "metrics" not in result
    )
    assert {"coding", "writeup"} <= set(result)


def test_agent_without_prompt_is_skipped():
    tc = _starship()
    tc.agents["coding"].prompt = PromptConfig(system="")
    result = resolve_registered_agents(tc)
    assert "coding" not in result


def test_topologyless_config_falls_back_to_all_enabled():
    # Root has NO sub_agents key -> fallback registers all enabled non-root w/ prompt
    tc = TeamConfig(
        agents={
            "planner": _agent("planner", sub_agents={}),
            "coding": _agent("coding"),
            "off": _agent("off", enabled=False),
        }
    )
    result = resolve_registered_agents(tc)
    assert set(result) == {"coding"}  # planner=root excluded, off disabled


def test_explicit_all_false_yields_empty_registry():
    tc = TeamConfig(
        agents={
            "planner": _agent("planner", sub_agents={"coding": False}),
            "coding": _agent("coding"),
        }
    )
    assert resolve_registered_agents(tc) == {}


def test_poc_template_excludes_disabled_subagents(sample_team_config):
    """The POC template disables github+aws via investigation.sub_agents."""
    result = resolve_registered_agents(sample_team_config)
    assert "github" not in result  # investigation.sub_agents.github = False
    assert "aws" not in result  # investigation.sub_agents.aws = False
    assert "investigation" in result
    assert {"k8s", "metrics", "log_analysis"} <= set(result)
