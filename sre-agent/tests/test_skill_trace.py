"""Unit tests for skill_trace — deterministic skill invocation detection."""

from tests.skill_trace import (
    count_skill_invocations,
    early_skill_invocations,
    is_kg_skill_invocation,
    is_memory_skill_invocation,
)


def test_memory_skill_detected_from_skill_tool():
    assert is_memory_skill_invocation(
        {
            "name": "Skill",
            "input": {"skill": "memory-search", "args": "--query checkout timeout"},
        }
    )


def test_memory_skill_detected_from_bash():
    assert is_memory_skill_invocation(
        {
            "name": "Bash",
            "input": {
                "command": "python .claude/skills/memory-search/scripts/search.py --query oom"
            },
        }
    )


def test_kg_skill_detected_from_topology_search():
    assert is_kg_skill_invocation(
        {
            "name": "Bash",
            "input": {
                "command": "python .claude/skills/infrastructure-neo4j/scripts/topology_search.py --service checkout"
            },
        }
    )


def test_kg_skill_detected_from_skill_tool():
    assert is_kg_skill_invocation(
        {
            "name": "skill",
            "input": {"skill": "infrastructure-neo4j"},
        }
    )


def test_unrelated_tools_not_counted():
    assert not is_memory_skill_invocation(
        {"name": "Bash", "input": {"command": "kubectl get pods"}}
    )
    assert not is_kg_skill_invocation(
        {"name": "Bash", "input": {"command": "kubectl get pods"}}
    )


def test_vague_early_tools_have_no_skill_hits():
    """Simulates first tools on a vague Jenkins ticket — no memory/KG yet."""
    early_tools = [
        {
            "name": "Bash",
            "input": {"command": "curl -s https://jenkins.example/job/442/consoleText"},
        },
        {"name": "Read", "input": {"file_path": "/tmp/console.log"}},
        {"name": "TaskCreate", "input": {"subject": "Read Jenkins console"}},
    ]
    counts = early_skill_invocations(early_tools, limit=5)
    assert counts["memory"] == 0
    assert counts["kg"] == 0


def test_rich_prompt_tools_include_memory_and_kg():
    """After scoping, agent may invoke both skills."""
    tools = [
        {
            "name": "Bash",
            "input": {
                "command": "python .claude/skills/infrastructure-neo4j/scripts/topology_search.py --service checkout"
            },
        },
        {
            "name": "skill",
            "input": {
                "skill": "memory-search",
                "args": "connection pool timeout checkout",
            },
        },
    ]
    counts = count_skill_invocations(tools)
    assert counts["memory"] == 1
    assert counts["kg"] == 1
