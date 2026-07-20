from agent import InteractiveAgentSession


def _session():
    s = InteractiveAgentSession.__new__(InteractiveAgentSession)
    s._agent_registry = {}
    s._open_dispatches = []
    s._pending_tool_starts = []
    s._pending_tool_ends = []
    return s


def test_root_level_tool_has_no_agent():
    s = _session()
    s._on_pre_tool_use({"tool_name": "Bash", "agent_id": None}, "tool-1", {})
    rec = s._pending_tool_starts[0]
    assert rec["agent_id"] is None
    assert rec["depth"] == 0
    assert rec["parent_agent_id"] is None


def test_direct_subagent_dispatch_and_call_resolves_depth_1():
    s = _session()
    # Root dispatches a Task tool (subagent about to start)
    s._on_pre_tool_use({"tool_name": "Task", "agent_id": None}, "task-1", {})
    # SDK announces the new subagent
    s._on_subagent_start(
        {"agent_id": "agent-A", "agent_type": "investigation"}, None, {}
    )
    # That subagent runs its own tool
    s._on_pre_tool_use({"tool_name": "Bash", "agent_id": "agent-A"}, "tool-2", {})
    rec = s._pending_tool_starts[-1]
    assert (
        rec["agent_id"] == "task-1"
    )  # invocation_id = tool_use_id of dispatching Task
    assert rec["agent_type"] == "investigation"
    assert rec["parent_agent_id"] is None
    assert rec["parent_agent_type"] is None
    assert rec["depth"] == 1


def test_grandchild_subagent_resolves_depth_2_via_open_dispatch():
    s = _session()
    s._on_pre_tool_use({"tool_name": "Task", "agent_id": None}, "task-1", {})
    s._on_subagent_start(
        {"agent_id": "agent-A", "agent_type": "investigation"}, None, {}
    )
    # investigation (agent-A) itself dispatches a nested, unnamed Task
    s._on_pre_tool_use({"tool_name": "Task", "agent_id": "agent-A"}, "task-2", {})
    s._on_subagent_start(
        {"agent_id": "agent-B", "agent_type": "general-purpose"}, None, {}
    )
    s._on_pre_tool_use({"tool_name": "Bash", "agent_id": "agent-B"}, "tool-3", {})
    rec = s._pending_tool_starts[-1]
    assert (
        rec["agent_id"] == "task-2"
    )  # invocation_id = tool_use_id of dispatching Task
    assert rec["parent_agent_id"] == "task-1"  # parent's invocation_id
    assert rec["parent_agent_type"] == "investigation"
    assert rec["depth"] == 2


def test_post_tool_use_marks_dispatch_ended_and_drains_queue():
    s = _session()
    s._on_pre_tool_use({"tool_name": "Task", "agent_id": None}, "task-1", {})
    s._on_post_tool_use(
        {"tool_name": "Task", "agent_id": None, "tool_response": "done"},
        "task-1",
        {},
    )
    assert s._open_dispatches[0]["ended"] is True
    assert len(s._pending_tool_ends) == 1
    assert s._pending_tool_ends[0]["tool_use_id"] == "task-1"


def test_post_tool_use_serializes_dict_tool_response_as_json():
    s = _session()
    s._on_post_tool_use(
        {
            "tool_name": "TaskCreate",
            "agent_id": None,
            "tool_response": {"task": {"id": "1", "subject": "List pods"}},
        },
        "tool-tc-1",
        {},
    )
    assert s._pending_tool_ends[0]["output"] == (
        '{"task": {"id": "1", "subject": "List pods"}}'
    )


def test_reused_sdk_agent_id_gets_distinct_invocation_ids():
    """Regression test for the bug confirmed live in run 34b47dd08d23426884c13a1e0b9dd552:
    the SDK reused the same agent_id for two unrelated, sequential subagent dispatches
    (once nested under "investigation" at depth 2, later a fresh dispatch directly under
    root at depth 1). invocation_id must differ between them even though the SDK agent_id
    is identical, so the frontend tree can tell them apart.
    """
    s = _session()
    # First dispatch: root -> investigation (agent-I) -> general-purpose (agent_id "X")
    s._on_pre_tool_use({"tool_name": "Task", "agent_id": None}, "task-1", {})
    s._on_subagent_start(
        {"agent_id": "agent-I", "agent_type": "investigation"}, None, {}
    )
    s._on_pre_tool_use({"tool_name": "Task", "agent_id": "agent-I"}, "task-2", {})
    s._on_subagent_start({"agent_id": "X", "agent_type": "general-purpose"}, None, {})
    s._on_pre_tool_use({"tool_name": "Bash", "agent_id": "X"}, "tool-1", {})
    s._on_post_tool_use(
        {"tool_name": "Bash", "agent_id": "X", "tool_response": "ok"}, "tool-1", {}
    )
    s._on_post_tool_use(
        {"tool_name": "Task", "agent_id": "agent-I", "tool_response": "done"},
        "task-2",
        {},
    )
    s._on_post_tool_use(
        {"tool_name": "Task", "agent_id": None, "tool_response": "done"}, "task-1", {}
    )
    first_rec = s._pending_tool_starts[-1]  # tool-1's start

    # Second, unrelated dispatch, much later: root -> general-purpose (SDK reuses "X")
    s._on_pre_tool_use({"tool_name": "Task", "agent_id": None}, "task-3", {})
    s._on_subagent_start({"agent_id": "X", "agent_type": "general-purpose"}, None, {})
    s._on_pre_tool_use({"tool_name": "Bash", "agent_id": "X"}, "tool-2", {})
    second_rec = s._pending_tool_starts[-1]

    assert first_rec["depth"] == 2
    assert second_rec["depth"] == 1
    # Same raw SDK agent_id ("X") reused, but invocation_id (what we now emit as
    # "agent_id" on the wire) must differ, since it's derived from the distinct
    # dispatching tool_use_id (task-2 vs task-3), not the reused SDK id.
    assert first_rec["agent_id"] != second_rec["agent_id"]
    assert first_rec["agent_id"] == "task-2"
    assert second_rec["agent_id"] == "task-3"
    assert first_rec["parent_agent_id"] == "task-1"
    assert second_rec["parent_agent_id"] is None


def test_post_tool_use_failure_queues_error_tool_end_and_closes_dispatch():
    s = _session()
    s._on_pre_tool_use({"tool_name": "Bash", "agent_id": None}, "tool-1", {})
    s._on_post_tool_use_failure(
        {"tool_name": "Bash", "agent_id": None, "error": "command not found"},
        "tool-1",
        {},
    )
    assert len(s._pending_tool_ends) == 1
    end = s._pending_tool_ends[0]
    assert end["success"] is False
    assert end["error"] == "command not found"
    assert end["tool_use_id"] == "tool-1"


def test_post_tool_use_failure_closes_open_task_dispatch():
    s = _session()
    s._on_pre_tool_use({"tool_name": "Task", "agent_id": None}, "task-1", {})
    s._on_post_tool_use_failure(
        {"tool_name": "Task", "agent_id": None, "error": "subagent crashed"},
        "task-1",
        {},
    )
    assert s._open_dispatches[0]["ended"] is True
