from src.core.merge import deep_merge_dicts


def test_deep_merge_empty():
    assert deep_merge_dicts([]) == {}
    assert deep_merge_dicts([{}, {}]) == {}


def test_deep_merge_scalars_and_lists():
    a = {
        "team_name": "team-a",
        "mcp_servers": ["a"],
        "agents": {"code_fix_agent": {"enabled": False}},
    }
    b = {"mcp_servers": ["b1", "b2"], "agents": {"code_fix_agent": {"enabled": True}}}
    merged = deep_merge_dicts([a, b])
    assert merged["team_name"] == "team-a"
    assert merged["mcp_servers"] == ["b1", "b2"]
    assert merged["agents"]["code_fix_agent"]["enabled"] is True


def test_deep_merge_nested():
    org = {
        "tokens_vault_path": {"openai_token": "vault://org/openai"},
        "knowledge_source": {"grafana": ["dash-org"]},
        "agents": {"investigation_agent": {"prompt": "org-prompt"}},
    }
    group = {
        "knowledge_source": {"grafana": ["dash-group"], "google": ["g-folder"]},
        "agents": {"investigation_agent": {"enable_extra_tools": ["grafana"]}},
    }
    team = {
        "team_name": "platform-devops",
        "knowledge_source": {"confluence": ["space:PLAT:rb"]},
        "agents": {"investigation_agent": {"prompt": "team-prompt"}},
    }
    merged = deep_merge_dicts([org, group, team])
    assert merged["tokens_vault_path"]["openai_token"] == "vault://org/openai"
    assert merged["knowledge_source"]["grafana"] == ["dash-group"]
    assert merged["knowledge_source"]["google"] == ["g-folder"]
    assert merged["knowledge_source"]["confluence"] == ["space:PLAT:rb"]
    assert merged["agents"]["investigation_agent"]["prompt"] == "team-prompt"
    assert merged["agents"]["investigation_agent"]["enable_extra_tools"] == ["grafana"]
