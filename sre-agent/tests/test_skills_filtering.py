"""Tests for ENABLED_SKILLS env var filtering."""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    AgentConfig,
    SkillsConfig,
    TeamConfig,
    _normalize_skill_names,
    build_skill_name_map,
    compute_enabled_skills_from_agents,
    parse_enabled_skills_env,
    remove_disabled_skill_dirs,
    resolve_enabled_skills,
)

# Fixture: simulated name map (directory_name -> frontmatter_name)
SAMPLE_NAME_MAP = {
    "investigate": "investigate",
    "observability-coralogix": "coralogix-analysis",
    "infrastructure-kubernetes": "kubernetes-debug",
    "observability": "observability",
    "remediation": "remediation",
}


# --- parse_enabled_skills_env ---


def test_parse_enabled_skills_env_unset():
    """Unset ENABLED_SKILLS returns None (all skills)."""
    os.environ.pop("ENABLED_SKILLS", None)
    assert parse_enabled_skills_env() is None


def test_parse_enabled_skills_env_all():
    """ENABLED_SKILLS=all returns None (all skills)."""
    os.environ["ENABLED_SKILLS"] = "all"
    try:
        assert parse_enabled_skills_env() is None
    finally:
        del os.environ["ENABLED_SKILLS"]


def test_parse_enabled_skills_env_csv():
    """ENABLED_SKILLS=a,b,c returns set of names."""
    os.environ["ENABLED_SKILLS"] = "investigate, kubernetes-debug, coralogix-analysis"
    try:
        result = parse_enabled_skills_env()
        assert result == {"investigate", "kubernetes-debug", "coralogix-analysis"}
    finally:
        del os.environ["ENABLED_SKILLS"]


def test_parse_enabled_skills_env_empty():
    """ENABLED_SKILLS='' returns None (all skills)."""
    os.environ["ENABLED_SKILLS"] = ""
    try:
        assert parse_enabled_skills_env() is None
    finally:
        del os.environ["ENABLED_SKILLS"]


# --- _normalize_skill_names ---


def test_normalize_dir_to_frontmatter():
    """Directory name is converted to frontmatter name."""
    result = _normalize_skill_names({"observability-coralogix"}, SAMPLE_NAME_MAP)
    assert result == {"coralogix-analysis"}


def test_normalize_frontmatter_passthrough():
    """Already a frontmatter name — passes through unchanged."""
    result = _normalize_skill_names({"coralogix-analysis"}, SAMPLE_NAME_MAP)
    assert result == {"coralogix-analysis"}


def test_normalize_mixed():
    """Mix of directory names and frontmatter names."""
    result = _normalize_skill_names(
        {"observability-coralogix", "investigate", "kubernetes-debug"},
        SAMPLE_NAME_MAP,
    )
    assert result == {"coralogix-analysis", "investigate", "kubernetes-debug"}


# --- resolve_enabled_skills ---


def test_resolve_env_overrides_config():
    """Env var takes priority over config."""
    env_skills = {"investigate", "coralogix-analysis"}
    config = SkillsConfig(enabled=["kubernetes-debug"])
    result = resolve_enabled_skills(env_skills, config, SAMPLE_NAME_MAP)
    assert result == {"investigate", "coralogix-analysis"}


def test_resolve_config_when_no_env():
    """Config used as fallback when env is None."""
    config = SkillsConfig(enabled=["investigate", "infrastructure-kubernetes"])
    result = resolve_enabled_skills(None, config, SAMPLE_NAME_MAP)
    # infrastructure-kubernetes should be normalized to kubernetes-debug
    assert result == {"investigate", "kubernetes-debug"}


def test_resolve_none_when_both_absent():
    """All skills when both env and config are defaults."""
    config = SkillsConfig()  # enabled=["*"], disabled=[]
    result = resolve_enabled_skills(None, config, SAMPLE_NAME_MAP)
    assert result is None


def test_resolve_wildcard_with_disabled():
    """Wildcard enabled minus disabled skills."""
    config = SkillsConfig(enabled=["*"], disabled=["remediation"])
    result = resolve_enabled_skills(None, config, SAMPLE_NAME_MAP)
    all_frontmatter = set(SAMPLE_NAME_MAP.values())
    assert result == all_frontmatter - {"remediation"}


# --- SkillsConfig defaults ---


def test_skills_config_defaults():
    """Default SkillsConfig has wildcard enabled and empty disabled."""
    config = SkillsConfig()
    assert config.enabled == ["*"]
    assert config.disabled == []


# --- build_skill_name_map (with temp dir) ---


def test_build_skill_name_map_with_frontmatter(tmp_path):
    """Reads SKILL.md frontmatter correctly."""
    skill_dir = tmp_path / "observability-coralogix"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: coralogix-analysis\ndescription: test\n---\n# Coralogix\n"
    )

    result = build_skill_name_map(str(tmp_path))
    assert result == {"observability-coralogix": "coralogix-analysis"}


def test_build_skill_name_map_no_frontmatter(tmp_path):
    """Falls back to directory name when no frontmatter."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill\nNo frontmatter here.\n")

    result = build_skill_name_map(str(tmp_path))
    assert result == {"my-skill": "my-skill"}


def test_build_skill_name_map_missing_dir():
    """Non-existent directory returns empty map."""
    result = build_skill_name_map("/nonexistent/path")
    assert result == {}


# --- compute_enabled_skills_from_agents ---


def test_compute_agent_skills_union():
    """Union of enabled skills across all agents."""
    tc = TeamConfig(
        agents={
            "k8s_agent": AgentConfig(
                enabled=True,
                name="k8s_agent",
                skills={"kubernetes-debug": True, "observability": False},
            ),
            "log_agent": AgentConfig(
                enabled=True,
                name="log_agent",
                skills={"observability": True, "coralogix-analysis": True},
            ),
        }
    )
    result = compute_enabled_skills_from_agents(tc, SAMPLE_NAME_MAP)
    assert result == {"kubernetes-debug", "observability", "coralogix-analysis"}


def test_compute_agent_skills_disabled_agent_ignored():
    """Disabled agents don't contribute skills."""
    tc = TeamConfig(
        agents={
            "active": AgentConfig(
                enabled=True,
                name="active",
                skills={"kubernetes-debug": True},
            ),
            "disabled": AgentConfig(
                enabled=False,
                name="disabled",
                skills={"remediation": True},
            ),
        }
    )
    result = compute_enabled_skills_from_agents(tc, SAMPLE_NAME_MAP)
    assert result == {"kubernetes-debug"}


def test_compute_agent_skills_none_when_no_skills():
    """Returns None when no agents have skills configured."""
    tc = TeamConfig(
        agents={
            "agent1": AgentConfig(enabled=True, name="agent1", skills={}),
        }
    )
    result = compute_enabled_skills_from_agents(tc, SAMPLE_NAME_MAP)
    assert result is None


def test_compute_agent_skills_normalizes_dir_names():
    """Directory names in agent skills are normalized to frontmatter names."""
    tc = TeamConfig(
        agents={
            "agent1": AgentConfig(
                enabled=True,
                name="agent1",
                skills={"infrastructure-kubernetes": True},  # dir name
            ),
        }
    )
    result = compute_enabled_skills_from_agents(tc, SAMPLE_NAME_MAP)
    assert result == {"kubernetes-debug"}  # frontmatter name


# --- resolve_enabled_skills with agent_skills ---


def test_resolve_agent_skills_override_config():
    """Agent-level skills override team-level config."""
    config = SkillsConfig(enabled=["*"])
    agent_skills = {"kubernetes-debug", "observability"}
    result = resolve_enabled_skills(None, config, SAMPLE_NAME_MAP, agent_skills)
    assert result == {"kubernetes-debug", "observability"}


def test_resolve_env_overrides_agent_skills():
    """Env var overrides agent-level skills."""
    env_skills = {"investigate"}
    config = SkillsConfig()
    agent_skills = {"kubernetes-debug", "observability"}
    result = resolve_enabled_skills(env_skills, config, SAMPLE_NAME_MAP, agent_skills)
    assert result == {"investigate"}


# --- remove_disabled_skill_dirs ---


def test_remove_disabled_skill_dirs(tmp_path):
    """Removes directories for disabled skills."""
    # Create skill dirs with SKILL.md
    for name in ["investigate", "observability-coralogix", "remediation"]:
        d = tmp_path / name
        d.mkdir()
        fm_name = SAMPLE_NAME_MAP.get(name, name)
        (d / "SKILL.md").write_text(f"---\nname: {fm_name}\n---\n# Skill\n")

    name_map = build_skill_name_map(str(tmp_path))
    enabled = {"investigate"}  # Only investigate is enabled

    removed = remove_disabled_skill_dirs(str(tmp_path), enabled, name_map)

    assert sorted(removed) == ["observability-coralogix", "remediation"]
    assert (tmp_path / "investigate").exists()
    assert not (tmp_path / "observability-coralogix").exists()
    assert not (tmp_path / "remediation").exists()


def test_remove_disabled_skill_dirs_all_enabled(tmp_path):
    """No removal when all skills enabled (None)."""
    d = tmp_path / "investigate"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: investigate\n---\n")

    removed = remove_disabled_skill_dirs(str(tmp_path), None, SAMPLE_NAME_MAP)
    assert removed == []
    assert (tmp_path / "investigate").exists()
