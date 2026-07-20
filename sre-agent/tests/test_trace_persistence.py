"""Tests for incremental + completion trace persistence in simple mode."""

import json
from unittest.mock import MagicMock, patch

import server_simple


def _captured_patch_body(mock_patch):
    assert mock_patch.called, "expected a PATCH to config-service"
    return mock_patch.call_args.kwargs["json"]


def test_completion_persists_untruncated_output_and_structured_report():
    long_text = "X" * 2000 + "\n```json\n" + json.dumps({"title": "RC"}) + "\n```"
    server_simple._run_id_by_thread["t1"] = "run-1"
    with patch("server_simple.httpx.patch") as mock_patch:
        mock_patch.return_value = MagicMock(raise_for_status=lambda: None)
        server_simple.finalize_investigation(
            thread_id="t1",
            prompt="p",
            result_text=long_text,
            success=True,
            tool_calls=[],
            duration_seconds=1.0,
        )
    body = _captured_patch_body(mock_patch)
    assert len(body["output_summary"]) > 500  # NOT truncated
    assert body["output_summary"] == long_text
    assert body["output_json"] == {"title": "RC"}  # structured report persisted


def test_persist_tool_call_posts_expected_body():
    with patch("server_simple.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(raise_for_status=lambda: None)
        server_simple._persist_tool_call(
            "run-1",
            {
                "id": "tu_1",
                "tool_name": "Bash",
                "agent_name": "sre-agent",
                "parent_agent": None,
                "tool_input": {"command": "ls"},
                "tool_output": "files",
                "duration_ms": 12,
                "status": "success",
                "sequence_number": 3,
            },
        )
    url = (
        mock_post.call_args.args[0]
        if mock_post.call_args.args
        else mock_post.call_args.kwargs.get("url")
    )
    assert url.endswith("/api/v1/internal/agent-runs/run-1/tool-calls")
    body = mock_post.call_args.kwargs["json"]
    assert body["run_id"] == "run-1"
    assert body["tool_calls"][0]["tool_name"] == "Bash"
    assert body["tool_calls"][0]["sequence_number"] == 3


def test_flush_thoughts_puts_expected_body():
    with patch("server_simple.httpx.put") as mock_put:
        mock_put.return_value = MagicMock(raise_for_status=lambda: None)
        server_simple._flush_thoughts(
            "run-1", [{"text": "hi", "ts": "t", "seq": 0, "agent": "sre-agent"}]
        )
    body = mock_put.call_args.kwargs["json"]
    assert body["thoughts"][0]["text"] == "hi"
    assert body["thoughts"][0]["seq"] == 0


def test_tool_call_record_always_sets_started_at_and_captures_input():
    """Regression: config-service agent_tool_calls.started_at is NOT NULL, and tool_end
    events don't carry input — the record must set started_at and pull input from tool_start.
    """
    started = {"seq": 3, "t": 1000.0, "input": {"command": "ls"}, "name": "Bash"}
    rec = server_simple._tool_call_record(
        {"tool_use_id": "tu1", "name": "Bash", "success": True, "output": "files"},
        started,
        "sre-agent",
        {},
        9,
    )
    assert rec["started_at"] is not None
    assert rec["tool_input"] == {
        "command": "ls"
    }  # captured from tool_start, not the (inputless) tool_end
    assert rec["tool_output"] == "files"
    assert rec["sequence_number"] == 3
    assert rec["status"] == "success"


def test_tool_call_record_sets_started_at_even_without_matching_start():
    """started_at must be non-null even when the tool_start wasn't captured."""
    rec = server_simple._tool_call_record(
        {"tool_use_id": "tu2", "name": "Grep", "success": False, "error": "boom"},
        None,
        "sre-agent",
        {},
        7,
    )
    assert rec["started_at"] is not None
    assert rec["status"] == "error"
    assert rec["error_message"] == "boom"
    assert rec["sequence_number"] == 7


def test_tool_call_record_attributes_child_tool_to_subagent():
    """A direct-subagent child tool is attributed to that subagent, parent is root.

    Under the hook-based attribution (Task 3 of the nested-attribution fix),
    agent_name/parent_agent/depth come from the SDK-hook-derived fields on the
    event `data` (agent_type/parent_agent_type/depth), not from
    parent_tool_use_id + task_agents lookup. task_agents is now unused for
    attribution but kept as a parameter for call-site compatibility.
    """
    rec = server_simple._tool_call_record(
        {
            "tool_use_id": "c1",
            "name": "Read",
            "success": True,
            "agent_id": "agent-A",
            "agent_type": "kubernetes",
            "parent_agent_id": None,
            "parent_agent_type": None,
            "depth": 1,
        },
        {"seq": 5, "t": 1000.0},
        "sre-agent",
        {"task1": "kubernetes"},
        5,
    )
    assert rec["agent_name"] == "kubernetes"
    assert rec["parent_agent"] == "sre-agent"
    assert rec["agent_id"] == "agent-A"
    assert rec["depth"] == 1


def test_tool_call_record_redacts_env_dump_output():
    """Defense-in-depth: _tool_call_record must strip env values before DB POST."""
    started = {
        "seq": 4,
        "t": 1000.0,
        "input": {"command": "env | grep BKT"},
        "name": "Bash",
    }
    rec = server_simple._tool_call_record(
        {
            "tool_use_id": "tu-env",
            "name": "Bash",
            "success": True,
            "output": "BKT_TOKEN=ATATT3xFfGF0leaked\nBKT_HOST=api.example.com",
        },
        started,
        "sre-agent",
        {},
        4,
    )
    assert "ATATT" not in rec["tool_output"]
    assert "api.example.com" not in rec["tool_output"]
    assert "BKT_TOKEN=<redacted>" in rec["tool_output"]
    assert "BKT_HOST=<redacted>" in rec["tool_output"]


def test_complete_agent_run_includes_sdk_session_id(monkeypatch):
    import server_simple

    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

    def _fake_patch(url, json=None, headers=None, timeout=None):
        captured["body"] = json
        return _Resp()

    monkeypatch.setattr(server_simple.httpx, "patch", _fake_patch)
    server_simple._run_id_by_thread["thread-z"] = "run-z"

    server_simple._complete_agent_run(
        thread_id="thread-z",
        success=True,
        result_text="done",
        tool_calls=[],
        duration_seconds=1.0,
        sdk_session_id="sess-z",
    )

    assert captured["body"]["sdk_session_id"] == "sess-z"


def test_exception_path_finalizes_run_as_failed(monkeypatch):
    """When agent_background_task raises, _complete_agent_run is called with success=False."""
    import server_simple

    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

    def _fake_patch(url, json=None, headers=None, timeout=None):
        captured["body"] = json
        return _Resp()

    monkeypatch.setattr(server_simple.httpx, "patch", _fake_patch)
    server_simple._run_id_by_thread["thread-ex"] = "run-ex"

    # Simulate the exception path: call _complete_agent_run exactly as the
    # except block does, then verify the PATCH body reflects failure.
    server_simple._complete_agent_run(
        thread_id="thread-ex",
        success=False,
        result_text="Investigation failed: session file corrupt",
        tool_calls=[],
        duration_seconds=0.0,
    )

    assert captured["body"]["status"] == "failed"
    assert "Investigation failed" in captured["body"]["output_summary"]
    # run_id must be popped — a second call is a no-op (no PATCH re-sent)
    captured.clear()
    server_simple._complete_agent_run(
        thread_id="thread-ex",
        success=False,
        result_text="double call",
        tool_calls=[],
        duration_seconds=0.0,
    )
    assert captured == {}
