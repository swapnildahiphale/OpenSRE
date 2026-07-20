from server_simple import _agent_for


def test_root_thought_has_no_agent_id():
    info = _agent_for({}, "planner", None)
    assert info["agent_type"] == "planner"
    assert info["depth"] == 0
    assert info["invocation_id"] is None


def test_subagent_thought_before_any_tool_call_resolves_via_task_agents():
    # task_agents is populated at the dispatching Task/Agent tool_start, which always
    # happens before the spawned subagent's own thoughts/tool calls — so this must
    # resolve correctly regardless of whether the subagent thinks or calls a tool first.
    task_agents = {
        "task-1": {
            "agent_type": "investigation",
            "depth": 1,
            "invocation_id": "task-1",
            "parent_invocation_id": None,
        }
    }
    info = _agent_for(task_agents, "planner", "task-1")
    assert info["agent_type"] == "investigation"
    assert info["depth"] == 1
    assert info["invocation_id"] == "task-1"
    assert info["parent_invocation_id"] is None


def test_thought_with_unknown_parent_tool_use_id_falls_back_to_root():
    # parent_tool_use_id is set but doesn't match anything in task_agents (e.g. a
    # stale or unrecognized id) -> falls back to the root agent, same shape as the
    # no-parent case.
    info = _agent_for({}, "planner", "some-unknown-id")
    assert info == {
        "agent_type": "planner",
        "depth": 0,
        "invocation_id": None,
        "parent_invocation_id": None,
    }
