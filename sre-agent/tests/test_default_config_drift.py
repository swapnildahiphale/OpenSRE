"""Drift guards over the config-service default agent config and templates.

These fail when LangGraph-era shapes reappear: tools that are not SDK tools,
prompts naming tools that do not exist, sub_agents edges pointing at nothing.
"""

import json
import os
import re
import sys

_SRE_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_SRE_AGENT_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "config_service", "src"))

_TEMPLATE = os.path.join(
    _REPO_ROOT, "config_service", "templates", "01_slack_incident_triage.json"
)

# Tools the LangGraph era invented. None of them exist in the Claude Agent SDK.
_PHANTOM_TOOLS = ("think", "llm_call", "web_search")


def _default_agents() -> dict:
    from core.hierarchical_config import get_default_agent_config

    return get_default_agent_config()["agents"]


def test_default_topology_has_no_mid_tier():
    agents = _default_agents()
    assert "investigation" not in agents
    assert "traces" not in agents


def test_default_sub_agent_edges_all_resolve():
    agents = _default_agents()
    for name, cfg in agents.items():
        for child in cfg.get("sub_agents") or {}:
            assert child in agents, f"{name}.sub_agents names missing agent {child!r}"


def test_default_root_dispatches_specialists_directly():
    planner = _default_agents()["planner"]
    assert set(planner["sub_agents"]) == {
        "kubernetes",
        "aws",
        "metrics",
        "log_analysis",
        "github",
        "coding",
        "writeup",
    }


# The exact strings the brief specifies. The SDK routes sub-agent selection
# on `description`, so a silent edit to one of these degrades routing with no
# runtime error - only an exact-match test catches that.
_EXPECTED_DESCRIPTIONS = {
    "planner": (
        "Root incident coordinator: triages severity, investigates directly, "
        "and dispatches specialists when a domain needs depth"
    ),
    "kubernetes": (
        "Kubernetes and container diagnosis: CrashLoopBackOff, OOMKilled, "
        "Pending pods, failing deployments, pod events and container logs"
    ),
    "aws": (
        "AWS resource diagnosis: RDS connection exhaustion, Lambda timeouts, "
        "ECS task failures, load balancer and CloudWatch signals"
    ),
    "metrics": (
        "Metric anomaly detection and correlation: error-rate and latency "
        "spikes, change points, saturation, and dependency degradation"
    ),
    "log_analysis": (
        "High-volume log investigation: error-pattern extraction, log "
        "signatures, and correlating log bursts against incident timing"
    ),
    "github": (
        "Change correlation: recent deployments, commits, pull requests and "
        "diffs that line up with when the incident started"
    ),
    "coding": (
        "Source-level analysis and fixes: reading application code, locating "
        "a defect in a diff, and proposing or making a change"
    ),
    "writeup": (
        "Blameless postmortem and incident documentation: timeline, "
        "contributing factors, and follow-up actions from findings"
    ),
}


def test_every_default_agent_has_a_real_description():
    for name, cfg in _default_agents().items():
        desc = cfg.get("description", "")
        assert desc, f"{name} has no description; the SDK routes on it"
        assert desc != f"{name} specialist", f"{name} still has a placeholder"
        assert (
            len(desc) > 30
        ), f"{name} description is too thin to win routing: {desc!r}"
        assert desc == _EXPECTED_DESCRIPTIONS[name], (
            f"{name} description drifted from the spec:\n  got:      {desc!r}\n"
            f"  expected: {_EXPECTED_DESCRIPTIONS[name]!r}"
        )


def test_default_agents_declare_no_phantom_tools():
    for name, cfg in _default_agents().items():
        for tool in cfg.get("tools") or {}:
            assert tool not in _PHANTOM_TOOLS, f"{name} declares phantom tool {tool!r}"


def test_default_agents_declare_no_unsupported_model_knobs():
    for name, cfg in _default_agents().items():
        model = cfg.get("model") or {}
        for knob in ("temperature", "max_tokens", "top_p"):
            assert knob not in model, f"{name}.model still declares {knob}"


def test_template_prompts_name_no_phantom_tools():
    with open(_TEMPLATE) as f:
        template = json.load(f)
    for name, agent in template["agents"].items():
        prompt = agent.get("prompt", {}).get("system", "")
        for tool in _PHANTOM_TOOLS:
            assert f"`{tool}`" not in prompt, f"{name} prompt still cites `{tool}`"


def _template() -> dict:
    with open(_TEMPLATE) as f:
        return json.load(f)


def test_template_agent_ids_match_the_defaults():
    agents = set(_template()["agents"])
    assert "investigation" not in agents
    assert "k8s" not in agents
    assert "kubernetes" in agents
    assert agents == set(_default_agents())


def test_template_declares_a_flat_topology():
    template = _template()
    assert template["$topology"] == "flat"
    assert template["entrance_agent"] == "planner"


def test_template_sub_agent_edges_all_resolve():
    agents = _template()["agents"]
    for name, cfg in agents.items():
        for child in cfg.get("sub_agents") or {}:
            assert child in agents, f"{name}.sub_agents names missing agent {child!r}"


def test_template_models_do_not_silently_degrade():
    sys.path.insert(0, _SRE_AGENT_ROOT)
    from config import resolve_model

    for name, cfg in _template()["agents"].items():
        configured = (cfg.get("model") or {}).get("name", "")
        assert (
            configured == "inherit" or resolve_model(configured) != "inherit"
        ), f"{name} configures {configured!r}, which silently degrades to inherit"


def test_planner_prompt_keeps_the_load_bearing_sections():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "## REMEDIATION RECOMMENDATIONS" in prompt
    assert "## BEHAVIORAL PRINCIPLES" in prompt
    assert "## SEVERITY ASSESSMENT" in prompt


def test_planner_prompt_drops_the_dead_topology():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "STARSHIP" not in prompt
    assert "Investigation Agent" not in prompt


def test_planner_prompt_points_at_memory_and_topology_skills():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "memory-search" in prompt
    assert "infrastructure-neo4j" in prompt


def test_planner_prompt_tracks_hypotheses_with_real_tools():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "TaskCreate" in prompt
    assert "TaskUpdate" in prompt


# Reworded restatements of the same false premise (no direct API access; the
# gateway is mandatory), not just the exact sentences the first rewrite fixed.
_FALSE_ACCESS_CLAIM_PATTERNS = (
    re.compile(r"no direct .{0,40}(k8s|kubernetes|aws)[^.]{0,40}access", re.IGNORECASE),
    re.compile(
        r"kubectl[^.]{0,30}(will fail|fails|not available|does not work)", re.IGNORECASE
    ),
    re.compile(r"never run kubectl", re.IGNORECASE),
    re.compile(r"must go through the k8s-gateway", re.IGNORECASE),
)


def test_no_prompt_claims_the_k8s_gateway_is_mandatory():
    for name, cfg in _template()["agents"].items():
        prompt = cfg.get("prompt", {}).get("system", "")
        for pattern in _FALSE_ACCESS_CLAIM_PATTERNS:
            assert not pattern.search(
                prompt
            ), f"{name} prompt still claims: {pattern.pattern!r}"


def test_planner_prompt_does_not_self_serve_kubernetes():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "list_clusters.py" not in prompt
    assert "--cluster-id" not in prompt


def test_planner_prompt_dispatches_instead_of_handling_domain_work_itself():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "handle straightforward checks yourself" not in prompt


def test_planner_prompt_has_a_concrete_parallel_dispatch_example():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "same turn" in prompt


def test_planner_prompt_names_episodic_memory_explicitly():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "episodic memory" in prompt.lower()
    assert "search memory" not in prompt.lower()


def test_no_prompt_claims_writes_are_gated_or_intercepted():
    # No PreToolUse hook enforces approval on any write skill - these claims
    # describe a control that doesn't exist in code.
    for name, cfg in _template()["agents"].items():
        prompt = cfg.get("prompt", {}).get("system", "")
        assert "intercepted before execution" not in prompt.lower(), name
        assert "say the word" not in prompt.lower(), name


def test_planner_prompt_has_chat_safe_final_report_format():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "## FINAL REPORT FORMAT" in prompt
    assert "Timeline" in prompt


def test_planner_prompt_emits_structured_report_scoped_to_final_message():
    prompt = _template()["agents"]["planner"]["prompt"]["system"]
    assert "```json" in prompt
    # Scoped to the final report, not every reply - a future edit that drops
    # this qualifier would make every follow-up turn emit the block too.
    assert "only on the final-report message" in prompt.lower() or \
        "not on follow-up" in prompt.lower() or \
        "not on ordinary follow-up" in prompt.lower()
