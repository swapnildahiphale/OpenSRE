from events import tool_end_event, tool_start_event


def test_tool_start_event_carries_agent_fields():
    evt = tool_start_event(
        "thread-1",
        "Bash",
        {"command": "ls"},
        tool_use_id="t1",
        agent_id="agent-B",
        agent_type="general-purpose",
        parent_agent_id="agent-A",
        parent_agent_type="investigation",
        depth=2,
    )
    assert evt.data["agent_id"] == "agent-B"
    assert evt.data["agent_type"] == "general-purpose"
    assert evt.data["parent_agent_id"] == "agent-A"
    assert evt.data["parent_agent_type"] == "investigation"
    assert evt.data["depth"] == 2


def test_tool_end_event_carries_agent_fields_and_root_defaults():
    evt = tool_end_event(
        "thread-1",
        "Bash",
        success=True,
        output="ok",
        tool_use_id="t1",
        agent_id=None,
        agent_type=None,
        parent_agent_id=None,
        parent_agent_type=None,
        depth=0,
    )
    assert evt.data["agent_id"] is None
    assert evt.data["depth"] == 0


def test_tool_start_event_defaults_root_when_no_agent_kwargs():
    # Existing callers that don't pass the new kwargs must keep working:
    # a root-level call should default to depth 0 with null agent fields.
    evt = tool_start_event("thread-1", "Bash", {"command": "ls"}, tool_use_id="t1")
    assert evt.data["agent_id"] is None
    assert evt.data["agent_type"] is None
    assert evt.data["parent_agent_id"] is None
    assert evt.data["parent_agent_type"] is None
    assert evt.data["depth"] == 0
