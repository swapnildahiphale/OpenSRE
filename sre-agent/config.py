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
from team_context import TeamContextSection

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
    """OpenSRE skill filtering config emitted by config_service under the 'skills' key."""

    enabled: list[str] = field(default_factory=lambda: ["*"])
    disabled: list[str] = field(default_factory=list)


_ALL_SKILLS = object()

_ANTHROPIC_MODEL_ALIASES = {"sonnet", "opus", "haiku", "inherit"}

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


@dataclass
class ModelConfig:
    """Model settings for LLM calls.

    These settings apply globally to the session (Claude SDK limitation).
    """

    name: str = "claude-sonnet-4-6"
    temperature: float | None = None  # 0.0-1.0, None = provider default
    max_tokens: int | None = None  # Maximum response tokens
    top_p: float | None = None  # Nucleus sampling parameter (0.0-1.0)


@dataclass
class MemoryConfig:
    """Memory system configuration (OpenSRE-specific)."""

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
    team_context: list[TeamContextSection] = field(default_factory=list)
    raw_config: dict = field(default_factory=dict)


def _parse_team_context(raw: dict) -> list[TeamContextSection]:
    tc = raw.get("team_context") or {}
    sections_raw = tc.get("sections") if isinstance(tc, dict) else []
    if not isinstance(sections_raw, list):
        return []
    out: list[TeamContextSection] = []
    for item in sections_raw:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "")
        if not sid and not title and not content.strip():
            continue
        if not sid:
            sid = "section"  # render still works; UI should always assign id
        out.append(TeamContextSection(id=sid, title=title or sid, content=content))
    return out


def _coerce_tools(raw) -> "ToolsConfig":
    """Accept either {"enabled": [...], "disabled": [...]} or a {name: bool} dict."""
    if isinstance(raw, dict) and ("enabled" in raw or "disabled" in raw):
        return ToolsConfig(
            enabled=raw.get("enabled", ["*"]),
            disabled=raw.get("disabled", []),
        )
    if isinstance(raw, dict):
        return ToolsConfig(
            enabled=[k for k, v in raw.items() if v],
            disabled=[k for k, v in raw.items() if not v],
        )
    return ToolsConfig()


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

    # Parse team-level skills config
    skills_data = effective.get("skills", {})
    skills_cfg = SkillsConfig(
        enabled=skills_data.get("enabled", ["*"]),
        disabled=skills_data.get("disabled", []),
    )

    # Parse memory config
    memory_data = effective.get("memory", {})
    memory_cfg = MemoryConfig(
        enabled=memory_data.get("enabled", True),
        store_all=memory_data.get("store_all", True),
        strategy_window=memory_data.get("strategy_window", 5),
        max_similar_episodes=memory_data.get("max_similar_episodes", 3),
    )

    return TeamConfig(
        agents=agents,
        skills=skills_cfg,
        memory=memory_cfg,
        team_context=_parse_team_context(effective),
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


def resolve_registered_agents(team_config: TeamConfig) -> dict[str, AgentConfig]:
    """Compute the flat set of sub-agents to register with the SDK.

    KI-1 fix: an agent is registered iff it is reachable from the root agent by
    following only enabled `sub_agents[child] == True` edges through enabled nodes
    that have a system prompt. The root itself is excluded (it is the orchestrator).

    Fallback: if there is no root, or the root has no `sub_agents` map at all
    (a topology-less config), register every enabled non-root agent that has a
    system prompt — the pre-fix behavior — so unwired configs do not regress.
    An explicit `sub_agents` map containing `False` values is respected, even
    down to an empty registry (the operator disabled everything).
    """
    agents = team_config.agents
    root = get_root_agent_config(team_config)

    def _fallback() -> dict[str, AgentConfig]:
        return {
            name: cfg
            for name, cfg in agents.items()
            if (root is None or name != root.name) and cfg.enabled and cfg.prompt.system
        }

    if root is None or not root.sub_agents:
        return _fallback()

    reached: set[str] = set()
    visited: set[str] = set()
    queue: list[str] = [root.name]
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        current_cfg = agents.get(current)
        if current_cfg is None:
            continue
        for child, allowed in current_cfg.sub_agents.items():
            if not allowed:
                continue
            child_cfg = agents.get(child)
            if (
                child_cfg is None
                or not child_cfg.enabled
                or not child_cfg.prompt.system
            ):
                continue
            if child not in reached:
                reached.add(child)
                queue.append(child)

    reached.discard(root.name)
    return {name: agents[name] for name in reached}


def resolve_model(name: str | None) -> str:
    """Map a configured model name to an SDK-safe value (Anthropic-only).

    Aliases and any explicit `claude-*` id pass through; anything else (legacy
    OpenAI names like `gpt-5.2`, unknown strings, empty) falls back to "inherit"
    so the agent uses the session/default model and nothing breaks.
    """
    if not name:
        return "inherit"
    if name in _ANTHROPIC_MODEL_ALIASES:
        return name
    if name.startswith("claude-"):
        return name
    return "inherit"


def build_delegation_addendum(agent_names: list[str]) -> str:
    """Authoritative runtime delegation list appended to the root system prompt.

    Behaviorally overrides any stale static sub-agent table baked into the prompt
    so the LLM only delegates to (and only describes) the agents actually
    registered this session. Empty when there are no sub-agents.
    """
    if not agent_names:
        return ""
    listing = ", ".join(sorted(agent_names))
    return (
        "\n\n## AVAILABLE SUB-AGENTS\n"
        f"You may delegate ONLY to these sub-agents: {listing}.\n"
        "Ignore any other agents named elsewhere in this prompt."
    )


def parse_enabled_skills_env() -> "set[str] | None | object":
    """Parse ENABLED_SKILLS env var.

    Returns:
      - _ALL_SKILLS sentinel if explicitly "all"
      - None if unset (no override)
      - set of skill names if specific skills listed
    """
    raw = os.getenv("ENABLED_SKILLS", "").strip()
    if not raw:
        return None
    if raw.lower() == "all":
        return _ALL_SKILLS
    return {s.strip() for s in raw.split(",") if s.strip()}


def build_skill_name_map(skills_dir: str) -> dict[str, str]:
    """Read SKILL.md frontmatter from all skill dirs -> {directory_name: frontmatter_name}."""
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
            match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            if match:
                for line in match.group(1).splitlines():
                    if line.startswith("name:"):
                        name_map[dir_name] = line.split(":", 1)[1].strip()
                        break
                else:
                    name_map[dir_name] = dir_name
            else:
                name_map[dir_name] = dir_name
        except Exception:
            name_map[dir_name] = dir_name
    return name_map


def _normalize_skill_names(names: set[str], name_map: dict[str, str]) -> set[str]:
    """Convert directory/legacy names to current frontmatter names; unknowns pass through."""
    frontmatter_values = set(name_map.values())
    result: set[str] = set()
    for name in names:
        if name in frontmatter_values:
            result.add(name)
        elif name in name_map:
            result.add(name_map[name])
        elif name in LEGACY_SKILL_NAME_MAP:
            current_name = LEGACY_SKILL_NAME_MAP[name]
            result.add(name_map.get(current_name, current_name))
        else:
            result.add(name)
    return result


def resolve_enabled_skills(
    env_skills: "set[str] | None | object",
    config_skills: SkillsConfig,
    name_map: dict[str, str],
    agent_skills: "set[str] | None" = None,
) -> "set[str] | None":
    """Resolve the final enabled-skill set. Priority: env > agent > team. None = all allowed."""
    if env_skills is _ALL_SKILLS:
        return None
    if env_skills is not None:
        return _normalize_skill_names(env_skills, name_map)
    if agent_skills is not None:
        return agent_skills
    if "*" in config_skills.enabled:
        if config_skills.disabled:
            all_skills = set(name_map.values())
            disabled_normalized = _normalize_skill_names(
                set(config_skills.disabled), name_map
            )
            return all_skills - disabled_normalized
        return None
    return _normalize_skill_names(set(config_skills.enabled), name_map)


def compute_enabled_skills_from_agents(
    team_config: "TeamConfig",
    name_map: dict[str, str],
) -> "set[str] | None":
    """Union of enabled per-agent skill toggles across enabled agents. None = don't restrict."""
    has_agent_skills = any(
        agent.skills for agent in team_config.agents.values() if agent.enabled
    )
    if not has_agent_skills:
        return None
    enabled_ids: set[str] = set()
    for agent in team_config.agents.values():
        if not agent.enabled:
            continue
        for skill_id, is_enabled in agent.skills.items():
            if is_enabled:
                enabled_ids.add(skill_id)
    if not enabled_ids:
        return None
    return _normalize_skill_names(enabled_ids, name_map)


# Valid SDK tool names — must mirror InteractiveAgentSession.DEFAULT_TOOLS in agent.py.
# Kept here (not imported from agent.py) to avoid a circular import.
# "Skill" intentionally excluded: it's no longer a member of allowed_tools (see
# agent.py's skills="all" option); a config that names it explicitly now falls
# through to the wildcard/full-default branch in resolve_agent_tools below.
_SDK_TOOL_NAMES: frozenset[str] = frozenset(
    [
        "Read",
        "Write",
        "Edit",
        "Bash",
        "Glob",
        "Grep",
        "WebSearch",
        "WebFetch",
        "AskUserQuestion",
        "Task",
        "TaskCreate",
        "TaskUpdate",
        "TaskList",
        "TaskGet",
    ]
)


def resolve_agent_tools(tools_cfg: "ToolsConfig") -> "list[str] | None":
    """Return a real SDK tools allowlist, or None (wildcard / full tool set).

    Rules:
    - Empty enabled list  → None (no restriction).
    - enabled == ["*"]    → None (explicit wildcard).
    - enabled is a non-empty proper subset of _SDK_TOOL_NAMES → return as-is.
    - Otherwise (contains any LangGraph / unknown name) → None so agents are
      never silently crippled by stale config names.
    """
    enabled = tools_cfg.enabled
    if not enabled:
        return None
    if enabled == ["*"] or "*" in enabled:
        return None
    if enabled and all(t in _SDK_TOOL_NAMES for t in enabled):
        return enabled
    # One or more names are not valid SDK tool names (e.g. LangGraph leftovers).
    return None


def remove_disabled_skill_dirs(
    skills_dir: str,
    enabled_skills: "set[str] | None",
    name_map: dict[str, str],
) -> list[str]:
    """Delete skill dirs not in the enabled set (primary enforcement). Returns removed dir names."""
    import shutil
    from pathlib import Path

    if enabled_skills is None:
        return []
    skills_path = Path(skills_dir)
    if not skills_path.is_dir():
        return []
    removed = []
    for skill_dir in sorted(skills_path.iterdir()):
        if not skill_dir.is_dir():
            continue
        dir_name = skill_dir.name
        frontmatter_name = name_map.get(dir_name, dir_name)
        if frontmatter_name not in enabled_skills:
            shutil.rmtree(skill_dir)
            removed.append(dir_name)
    return removed
