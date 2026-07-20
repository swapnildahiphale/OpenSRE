from state import ToolCall
from tool_display import (
    humanize_tool_summary,
    is_plan_tool,
    nest_bash_under_skills,
)


def _tool(name: str, input: dict | None = None, **kw) -> ToolCall:
    return ToolCall(name=name, input=input or {}, **kw)


def test_humanize_skill_with_args():
    t = _tool("Skill", {"skill": "project-jira", "args": "fetch OC-2263"})
    assert humanize_tool_summary(t) == "project-jira — fetch OC-2263"


def test_humanize_skill_without_args():
    t = _tool("Skill", {"skill": "infrastructure-kubernetes"})
    assert humanize_tool_summary(t) == "infrastructure-kubernetes"


def test_humanize_bash_skill_script():
    cmd = (
        "python /tmp/sessions/x/.claude/skills/infrastructure-kubernetes/"
        "scripts/list_pods.py -n nv13qa-cix"
    )
    s = humanize_tool_summary(_tool("Bash", {"command": cmd}))
    assert s.startswith("list_pods.py")
    assert ".claude/skills" not in s


def test_humanize_bash_plain():
    s = humanize_tool_summary(_tool("Bash", {"command": "kubectl get pods -n default"}))
    assert "kubectl get pods" in s


def test_humanize_read_basename():
    t = _tool(
        "Read", {"file_path": "/app/sre-agent/.claude/skills/investigate/SKILL.md"}
    )
    assert humanize_tool_summary(t) == "SKILL.md"


def test_humanize_agent():
    t = _tool(
        "Agent", {"subagent_type": "kubernetes", "description": "Check pod health"}
    )
    assert humanize_tool_summary(t) == "kubernetes: Check pod health"


def test_nest_bash_under_skill():
    skill = _tool("Skill", {"skill": "project-jira", "args": "fetch OC-2263"})
    bash = _tool(
        "Bash",
        {
            "command": "python .claude/skills/project-jira/scripts/fetch_issue.py --issue-key OC-2263"
        },
    )
    out = nest_bash_under_skills([skill, bash])
    assert len(out) == 1
    assert out[0].name == "Skill"
    assert len(out[0].nested_bash) == 1


def test_nest_closes_on_agent():
    skill = _tool("Skill", {"skill": "project-jira"})
    agent = _tool("Agent", {"subagent_type": "kubernetes", "description": "pods"})
    bash = _tool("Bash", {"command": "kubectl get pods"})
    out = nest_bash_under_skills([skill, agent, bash])
    assert [t.name for t in out] == ["Skill", "Agent", "Bash"]
    assert out[0].nested_bash == []


def test_nest_closes_on_read_then_bash_toplevel():
    skill = _tool("Skill", {"skill": "project-jira"})
    read = _tool("Read", {"file_path": "/tmp/SKILL.md"})
    bash = _tool(
        "Bash",
        {
            "command": "python .claude/skills/infrastructure-kubernetes/scripts/list_pods.py"
        },
    )
    out = nest_bash_under_skills([skill, read, bash])
    assert [t.name for t in out] == ["Skill", "Read", "Bash"]


def test_is_plan_tool():
    assert is_plan_tool("TaskCreate")
    assert is_plan_tool("TaskUpdate")
    assert is_plan_tool("TodoWrite")
    assert not is_plan_tool("Skill")
    assert not is_plan_tool("Bash")
