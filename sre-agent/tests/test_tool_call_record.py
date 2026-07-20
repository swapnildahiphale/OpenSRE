from server_simple import _tool_call_record


def test_root_level_call_has_no_parent():
    rec = _tool_call_record(
        {
            "tool_use_id": "t1",
            "name": "Bash",
            "output": "ok",
            "agent_id": None,
            "agent_type": None,
            "parent_agent_id": None,
            "parent_agent_type": None,
            "depth": 0,
        },
        {"seq": 0, "t": 1000.0, "input": {"command": "ls"}, "name": "Bash"},
        "planner",
        {},
        0,
    )
    assert rec["agent_name"] == "planner"
    assert rec["parent_agent"] is None
    assert rec["agent_id"] is None
    assert rec["depth"] == 0


def test_direct_subagent_call_parent_is_root():
    rec = _tool_call_record(
        {
            "tool_use_id": "t2",
            "name": "Bash",
            "output": "ok",
            "agent_id": "agent-A",
            "agent_type": "investigation",
            "parent_agent_id": None,
            "parent_agent_type": None,
            "depth": 1,
        },
        {"seq": 1, "t": 1000.0, "input": {}, "name": "Bash"},
        "planner",
        {},
        1,
    )
    assert rec["agent_name"] == "investigation"
    assert rec["parent_agent"] == "planner"
    assert rec["depth"] == 1


def test_grandchild_call_parent_is_named_subagent_not_root():
    rec = _tool_call_record(
        {
            "tool_use_id": "t3",
            "name": "Bash",
            "output": "ok",
            "agent_id": "agent-B",
            "agent_type": "general-purpose",
            "parent_agent_id": "agent-A",
            "parent_agent_type": "investigation",
            "depth": 2,
        },
        {"seq": 2, "t": 1000.0, "input": {}, "name": "Bash"},
        "planner",
        {},
        2,
    )
    assert rec["agent_name"] == "general-purpose"
    assert rec["parent_agent"] == "investigation"
    assert rec["depth"] == 2


def test_grandchild_call_carries_parent_invocation_id():
    rec = _tool_call_record(
        {
            "tool_use_id": "t3",
            "name": "Bash",
            "output": "ok",
            "agent_id": "task-2",
            "agent_type": "general-purpose",
            "parent_agent_id": "task-1",
            "parent_agent_type": "investigation",
            "depth": 2,
        },
        {"seq": 2, "t": 1000.0, "input": {}, "name": "Bash"},
        "planner",
        {},
        2,
    )
    assert rec["agent_id"] == "task-2"
    assert rec["parent_agent_id"] == "task-1"
