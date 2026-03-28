"""
Team configuration loader for sre-agent.

Fetches team-specific config (system prompts, tools, subagents) from the
config_service at sandbox startup. This enables per-team customization of
agent behavior without rebuilding the image.

Auth priority:
1. TEAM_TOKEN env var → Bearer token auth (resolves correct org/team via routing)
2. OPENSRE_TENANT_ID + OPENSRE_TEAM_ID → X-Org-Id/X-Team-Node-Id headers
"""

import os
from dataclasses import dataclass, field
from typing import Optional

import httpx

CONFIG_SERVICE_URL = os.getenv(
    "CONFIG_SERVICE_URL",
    "http://opensre-config-service.opensre.svc.cluster.local:8080",
)


@dataclass
class PromptConfig:
    system: str = ""
    prefix: str = ""
    suffix: str = ""


@dataclass
class ToolsConfig:
    enabled: list[str] = field(default_factory=lambda: ["*"])
    disabled: list[str] = field(default_factory=list)


@dataclass
class SkillsConfig:
    enabled: list[str] = field(default_factory=lambda: ["*"])
    disabled: list[str] = field(default_factory=list)


@dataclass
class ModelConfig:
    """Model settings for LLM calls.

    Supported by LiteLLM in credential-proxy (llm_proxy.py lines 460-470).
    These settings apply globally to the session (Claude SDK limitation).
    """

    name: str = "claude-sonnet-4-20250514"
    temperature: float | None = None  # 0.0-1.0, None = provider default
    max_tokens: int | None = None  # Maximum response tokens
    top_p: float | None = None  # Nucleus sampling parameter (0.0-1.0)


@dataclass
class MemoryConfig:
    """Memory system configuration."""

    enabled: bool = True
    store_all: bool = True  # Store unsuccessful investigations too
    strategy_window: int = 5  # Episodes for strategy generation
    max_similar_episodes: int = 3  # Episodes to prepend to prompt


@dataclass
class AgentConfig:
    """Agent configuration matching config_service schema.

    Fields:
        enabled: Whether this agent is active
        name: Agent identifier
        prompt: System prompt configuration
        tools: Tool filtering configuration
        skills: Per-agent skill toggles {skill_id: bool} from UI
        model: Model settings (temperature, max_tokens, top_p)
        max_turns: Maximum conversation turns (prevents infinite loops)
        sub_agents: Allowed child agents {agent_name: bool} for routing enforcement
    """

    enabled: bool = True
    name: str = ""
    prompt: PromptConfig = field(default_factory=PromptConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    skills: dict[str, bool] = field(default_factory=dict)
    model: ModelConfig = field(default_factory=ModelConfig)
    max_turns: int | None = None
    sub_agents: dict[str, bool] = field(default_factory=dict)


@dataclass
class TeamConfig:
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    business_context: str = ""
    raw_config: dict = field(default_factory=dict)


# Sentinel to distinguish "all skills" from "no env override"
_ALL_SKILLS = object()


def parse_enabled_skills_env() -> set[str] | None | object:
    """Parse ENABLED_SKILLS env var.

    Returns:
      - _ALL_SKILLS sentinel if explicitly set to "all" (forces all skills)
      - None if unset (no env override, fall through to agent/team config)
      - set of skill names if specific skills listed
    """
    raw = os.getenv("ENABLED_SKILLS", "").strip()
    if not raw:
        return None  # Not set — no env override
    if raw.lower() == "all":
        return _ALL_SKILLS  # Explicitly "all" — force all skills enabled
    return {s.strip() for s in raw.split(",") if s.strip()}


def build_skill_name_map(skills_dir: str) -> dict[str, str]:
    """Read SKILL.md frontmatter from all skill directories.

    Returns a mapping of {directory_name: frontmatter_name}.
    If a SKILL.md has no frontmatter name, the directory name is used.
    """
    import re
    from pathlib import Path

    name_map: dict[str, str] = {}
    skills_path = Path(skills_dir)
    if not skills_path.is_dir():
        return name_map

    for skill_dir in sorted(skills_path.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        dir_name = skill_dir.name
        try:
            text = skill_md.read_text(encoding="utf-8")
            # Parse YAML frontmatter: --- ... ---
            match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            if match:
                for line in match.group(1).splitlines():
                    if line.startswith("name:"):
                        fm_name = line.split(":", 1)[1].strip()
                        name_map[dir_name] = fm_name
                        break
                else:
                    name_map[dir_name] = dir_name
            else:
                name_map[dir_name] = dir_name
        except Exception:
            name_map[dir_name] = dir_name
    return name_map


# Legacy mapping: old frontmatter names → current directory names.
# Used for backward compatibility when config-service stores old skill IDs.
LEGACY_SKILL_NAME_MAP = {
    "opsgenie-integration": "alerting-opsgenie",
    "google-docs-integration": "docs-google",
    "notion-integration": "docs-notion",
    "blameless-integration": "incident-blameless",
    "firehydrant-integration": "incident-firehydrant",
    "incidentio-integration": "incident-incidentio",
    "aws-infrastructure": "infrastructure-aws",
    "azure-infrastructure": "infrastructure-azure",
    "docker-debugging": "infrastructure-docker",
    "gcp-infrastructure": "infrastructure-gcp",
    "kubernetes-debug": "infrastructure-kubernetes",
    "victoriametrics-metrics": "metrics-victoriametrics",
    "coralogix-analysis": "observability-coralogix",
    "datadog-analysis": "observability-datadog",
    "elasticsearch-analysis": "observability-elasticsearch",
    "grafana-dashboards": "observability-grafana",
    "honeycomb-analysis": "observability-honeycomb",
    "jaeger-analysis": "observability-jaeger",
    "newrelic-observability": "observability-newrelic",
    "sentry-monitoring": "observability-sentry",
    "splunk-analysis": "observability-splunk",
    "victorialogs-analysis": "observability-victorialogs",
    "jira-integration": "project-jira",
    "linear-integration": "project-linear",
    "kafka-streaming": "streaming-kafka",
    "gitlab-integration": "vcs-gitlab",
    "sourcegraph-integration": "vcs-sourcegraph",
}


def _normalize_skill_names(names: set[str], name_map: dict[str, str]) -> set[str]:
    """Convert skill names to frontmatter names where possible.

    Accepts directory names, frontmatter names, or legacy (old frontmatter) names.
    Returns a set of current frontmatter names (what Claude SDK's Skill tool uses).
    """
    frontmatter_values = set(name_map.values())
    result: set[str] = set()
    for name in names:
        if name in frontmatter_values:
            # Already a current frontmatter name
            result.add(name)
        elif name in name_map:
            # Directory name → convert to frontmatter name
            result.add(name_map[name])
        elif name in LEGACY_SKILL_NAME_MAP:
            # Legacy frontmatter name → convert to current directory/frontmatter name
            current_name = LEGACY_SKILL_NAME_MAP[name]
            result.add(name_map.get(current_name, current_name))
        else:
            # Unknown name — pass through (may be custom/dynamic)
            result.add(name)
    return result


def resolve_enabled_skills(
    env_skills: set[str] | None | object,
    config_skills: SkillsConfig,
    name_map: dict[str, str],
    agent_skills: set[str] | None = None,
) -> set[str] | None:
    """Resolve the final set of enabled skills.

    Priority: env var > agent-level (UI toggles) > team-level config.
    Returns None if all skills are allowed.
    """
    # Env var takes highest priority
    if env_skills is _ALL_SKILLS:
        return None  # Explicitly "all" — override everything, allow all skills
    if env_skills is not None:
        return _normalize_skill_names(env_skills, name_map)

    # Agent-level skills from UI (per-agent toggles)
    if agent_skills is not None:
        return agent_skills  # Already normalized by compute_enabled_skills_from_agents

    # Fall back to team-level config
    if "*" in config_skills.enabled:
        if config_skills.disabled:
            all_skills = set(name_map.values())
            disabled_normalized = _normalize_skill_names(
                set(config_skills.disabled), name_map
            )
            return all_skills - disabled_normalized
        return None  # All skills allowed

    return _normalize_skill_names(set(config_skills.enabled), name_map)


def compute_enabled_skills_from_agents(
    team_config: "TeamConfig",
    name_map: dict[str, str],
) -> set[str] | None:
    """Compute enabled skills from per-agent skill toggles.

    The UI saves per-agent skills as {skill_id: true/false}.
    This function unions all enabled skills across all agents.

    Returns None if no agents have skills configured (meaning all allowed),
    or the set of frontmatter skill names that are enabled.
    """
    # Check if any agent has per-agent skills configured
    has_agent_skills = any(
        agent.skills for agent in team_config.agents.values() if agent.enabled
    )
    if not has_agent_skills:
        return None  # No per-agent skills → don't restrict

    # Union of all enabled skill IDs across all enabled agents
    enabled_ids: set[str] = set()
    for agent in team_config.agents.values():
        if not agent.enabled:
            continue
        for skill_id, is_enabled in agent.skills.items():
            if is_enabled:
                enabled_ids.add(skill_id)

    if not enabled_ids:
        return None  # Safety: if everything is false, don't restrict

    return _normalize_skill_names(enabled_ids, name_map)


def remove_disabled_skill_dirs(
    skills_dir: str,
    enabled_skills: set[str] | None,
    name_map: dict[str, str],
) -> list[str]:
    """Remove skill directories not in the enabled set.

    This is the primary enforcement mechanism since Claude SDK
    auto-approves Skill tool calls and ignores PreToolUse denials.
    Skills that don't exist on disk can't be discovered or invoked.

    Returns list of removed directory names.
    """
    import shutil
    from pathlib import Path

    if enabled_skills is None:
        return []  # All skills allowed

    skills_path = Path(skills_dir)
    if not skills_path.is_dir():
        return []

    removed = []
    for skill_dir in sorted(skills_path.iterdir()):
        if not skill_dir.is_dir():
            continue
        dir_name = skill_dir.name
        # Get the frontmatter name for this directory
        frontmatter_name = name_map.get(dir_name, dir_name)
        if frontmatter_name not in enabled_skills:
            shutil.rmtree(skill_dir)
            removed.append(dir_name)

    return removed


def _parse_tools_config(tools_data: dict) -> ToolsConfig:
    """Parse tools config supporting both formats:

    1. {"enabled": [...], "disabled": [...]} — explicit list format
    2. {"tool_name": true, ...} — UI toggle format (flat dict of booleans)
    """
    if not tools_data:
        return ToolsConfig()  # defaults: enabled=["*"], disabled=[]

    if "enabled" in tools_data or "disabled" in tools_data:
        # Explicit list format
        return ToolsConfig(
            enabled=tools_data.get("enabled", ["*"]),
            disabled=tools_data.get("disabled", []),
        )

    # Flat dict format: {"think": true, "bash": false, ...}
    enabled_tools = [k for k, v in tools_data.items() if v]
    disabled_tools = [k for k, v in tools_data.items() if not v]
    return ToolsConfig(
        enabled=enabled_tools if enabled_tools else ["*"],
        disabled=disabled_tools,
    )


def load_team_config() -> TeamConfig:
    """
    Load team config from config_service. Raises on failure.

    Auth priority:
    1. TEAM_TOKEN → Bearer auth (token encodes correct org/team from routing)
    2. OPENSRE_TENANT_ID + OPENSRE_TEAM_ID → header-based auth
    """
    team_token = os.getenv("TEAM_TOKEN")
    tenant_id = os.getenv("OPENSRE_TENANT_ID")
    team_id = os.getenv("OPENSRE_TEAM_ID")

    url = f"{CONFIG_SERVICE_URL}/api/v1/config/me/effective"

    if team_token:
        # Preferred: Bearer token auth (resolves correct org/team via routing)
        headers = {"Authorization": f"Bearer {team_token}"}
    elif tenant_id and team_id:
        # Fallback: direct header auth
        headers = {"X-Org-Id": tenant_id, "X-Team-Node-Id": team_id}
    else:
        raise RuntimeError(
            "Either TEAM_TOKEN or both OPENSRE_TENANT_ID and "
            "OPENSRE_TEAM_ID must be set. Cannot load team configuration."
        )

    resp = httpx.get(url, headers=headers, timeout=10.0)
    resp.raise_for_status()

    data = resp.json()
    effective = data.get("effective_config", data)

    # Parse agents
    agents: dict[str, AgentConfig] = {}
    for name, cfg in effective.get("agents", {}).items():
        prompt_data = cfg.get("prompt", {})
        tools_data = cfg.get("tools", {})
        model_data = cfg.get("model", {})
        skills_data = cfg.get("skills", {})

        # Per-agent skills: UI stores as {skill_id: true/false}
        agent_skills = {}
        if isinstance(skills_data, dict):
            agent_skills = {k: bool(v) for k, v in skills_data.items()}

        # Parse sub_agents: {agent_name: bool} for routing enforcement
        sub_agents_data = cfg.get("sub_agents", {})
        sub_agents = {}
        if isinstance(sub_agents_data, dict):
            sub_agents = {k: bool(v) for k, v in sub_agents_data.items()}

        agents[name] = AgentConfig(
            enabled=cfg.get("enabled", True),
            name=name,
            prompt=PromptConfig(
                system=prompt_data.get("system", ""),
                prefix=prompt_data.get("prefix", ""),
                suffix=prompt_data.get("suffix", ""),
            ),
            tools=_parse_tools_config(tools_data),
            skills=agent_skills,
            model=ModelConfig(
                name=model_data.get("name", "claude-sonnet-4-20250514"),
                temperature=model_data.get("temperature"),
                max_tokens=model_data.get("max_tokens"),
                top_p=model_data.get("top_p"),
            ),
            max_turns=cfg.get("max_turns"),
            sub_agents=sub_agents,
        )

    # Parse skills config
    skills_data = effective.get("skills", {})
    skills_config = SkillsConfig(
        enabled=skills_data.get("enabled", ["*"]),
        disabled=skills_data.get("disabled", []),
    )

    # Parse memory config
    memory_data = effective.get("memory", {})
    memory_config = MemoryConfig(
        enabled=memory_data.get("enabled", True),
        store_all=memory_data.get("store_all", True),
        strategy_window=memory_data.get("strategy_window", 5),
        max_similar_episodes=memory_data.get("max_similar_episodes", 3),
    )

    return TeamConfig(
        agents=agents,
        skills=skills_config,
        memory=memory_config,
        business_context=effective.get("business_context", ""),
        raw_config=effective,
    )


def get_root_agent_config(team_config: TeamConfig) -> Optional[AgentConfig]:
    """Find root agent: prefers 'investigator' > 'planner' > first enabled."""
    for name in ["investigator", "planner"]:
        if name in team_config.agents and team_config.agents[name].enabled:
            return team_config.agents[name]
    for cfg in team_config.agents.values():
        if cfg.enabled:
            return cfg
    return None


def get_skills_for_agent(
    agent_name: str,
    team_config: TeamConfig,
    skills_dir: str = "/app/.claude/skills",
) -> set[str] | None:
    """Get the set of enabled skills for a specific agent.

    Combines env var overrides, per-agent UI toggles, and team-level config.
    Returns None if all skills are allowed.
    """
    env_skills = parse_enabled_skills_env()
    name_map = build_skill_name_map(skills_dir)

    # Check for per-agent skill config
    agent_config = team_config.agents.get(agent_name)
    agent_skills = None
    if agent_config and agent_config.skills:
        enabled_ids = {k for k, v in agent_config.skills.items() if v}
        if enabled_ids:
            agent_skills = _normalize_skill_names(enabled_ids, name_map)

    return resolve_enabled_skills(
        env_skills, team_config.skills, name_map, agent_skills
    )


def build_llm(agent_config: AgentConfig):
    """Build a ChatOpenAI instance pointed at LiteLLM proxy.

    Uses the agent's model config (name, temperature, max_tokens, top_p).
    LiteLLM proxy handles routing to the actual provider.
    """
    from langchain_openai import ChatOpenAI

    litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://litellm:4000/v1")
    litellm_api_key = os.getenv(
        "LITELLM_API_KEY", os.getenv("OPENROUTER_API_KEY", "sk-placeholder")
    )

    kwargs = {
        "base_url": litellm_base_url,
        "api_key": litellm_api_key,
        "model": agent_config.model.name,
    }

    if agent_config.model.temperature is not None:
        kwargs["temperature"] = agent_config.model.temperature
    if agent_config.model.max_tokens is not None:
        kwargs["max_tokens"] = agent_config.model.max_tokens
    if agent_config.model.top_p is not None:
        kwargs["top_p"] = agent_config.model.top_p

    return ChatOpenAI(**kwargs)
