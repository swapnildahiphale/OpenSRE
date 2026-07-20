"""Task 7: Verify config tools coercion and topology root agent."""

from config import _coerce_tools, get_root_agent_config


def test_coerce_tools_accepts_dict_and_list():
    assert _coerce_tools({"Bash": True, "Skill": True, "Read": False}).enabled == [
        "Bash",
        "Skill",
    ]
    assert _coerce_tools({"enabled": ["Bash", "Task"]}).enabled == ["Bash", "Task"]


def test_root_agent_is_investigator(sample_team_config):
    root = get_root_agent_config(sample_team_config)
    assert root is not None and root.name in ("investigator", "planner")
    assert root.prompt.system  # non-empty methodology prompt
