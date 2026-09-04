"""Config fields that must reach AgentDefinition and the session options."""

from config import AgentConfig, ModelConfig, PromptConfig, TeamConfig


def _team(**agents) -> TeamConfig:
    return TeamConfig(agents=agents)


def test_agent_config_parses_description():
    from config import _parse_agents

    agents = _parse_agents(
        {
            "planner": {"prompt": {"system": "root"}, "sub_agents": {"k8s": True}},
            "k8s": {
                "description": "Kubernetes troubleshooting: pods, deployments, events",
                "prompt": {"system": "k8s prompt"},
                "max_turns": 15,
            },
        }
    )
    assert agents["k8s"].description == (
        "Kubernetes troubleshooting: pods, deployments, events"
    )
    assert agents["k8s"].max_turns == 15


def test_agent_config_description_defaults_to_empty():
    from config import _parse_agents

    agents = _parse_agents({"k8s": {"prompt": {"system": "p"}}})
    assert agents["k8s"].description == ""


def test_description_reaches_agent_definition():
    from agent import InteractiveAgentSession

    team = _team(
        planner=AgentConfig(
            name="planner",
            prompt=PromptConfig(system="root prompt"),
            sub_agents={"k8s": True},
            model=ModelConfig(name="inherit"),
        ),
        k8s=AgentConfig(
            name="k8s",
            description="Kubernetes troubleshooting: pods, deployments, events",
            prompt=PromptConfig(system="k8s prompt"),
            max_turns=15,
            model=ModelConfig(name="sonnet"),
        ),
    )
    session = InteractiveAgentSession("t-wiring", team_config=team)
    session._build_options()

    defn = session.options.agents["k8s"]
    assert defn.description == ("Kubernetes troubleshooting: pods, deployments, events")
    assert defn.maxTurns == 15


def test_description_falls_back_when_unset():
    from agent import InteractiveAgentSession

    team = _team(
        planner=AgentConfig(
            name="planner",
            prompt=PromptConfig(system="root prompt"),
            sub_agents={"k8s": True},
        ),
        k8s=AgentConfig(name="k8s", prompt=PromptConfig(system="k8s prompt")),
    )
    session = InteractiveAgentSession("t-fallback", team_config=team)
    session._build_options()

    assert session.options.agents["k8s"].description == "k8s specialist"
    assert session.options.agents["k8s"].maxTurns is None


def test_root_model_reaches_session_options():
    from agent import InteractiveAgentSession

    team = _team(
        planner=AgentConfig(
            name="planner",
            prompt=PromptConfig(system="root prompt"),
            model=ModelConfig(name="opus"),
        )
    )
    session = InteractiveAgentSession("t-root-model", team_config=team)
    session._build_options()

    assert session.options.model == "opus"


def test_root_model_omitted_when_inherit():
    from agent import InteractiveAgentSession

    team = _team(
        planner=AgentConfig(
            name="planner",
            prompt=PromptConfig(system="root prompt"),
            model=ModelConfig(name="gpt-5.2"),
        )
    )
    session = InteractiveAgentSession("t-root-inherit", team_config=team)
    session._build_options()

    assert session.options.model is None


def test_model_config_has_no_unsupported_knobs():
    assert set(ModelConfig.__dataclass_fields__) == {"name"}


def test_subagent_prompts_carry_the_investigation_guidance():
    from agent import InteractiveAgentSession
    from investigation_lifecycle import investigation_guidance_append

    team = _team(
        planner=AgentConfig(
            name="planner",
            prompt=PromptConfig(system="root prompt"),
            sub_agents={"k8s": True},
        ),
        k8s=AgentConfig(
            name="k8s",
            description="Kubernetes troubleshooting",
            prompt=PromptConfig(system="k8s prompt"),
        ),
    )
    session = InteractiveAgentSession("t-guidance", team_config=team)
    session._build_options()

    guidance = investigation_guidance_append()
    assert session.options.agents["k8s"].prompt.endswith(guidance)
    assert "memory-search" in session.options.agents["k8s"].prompt
    assert "infrastructure-neo4j" in session.options.agents["k8s"].prompt
