"""Tests for interrupted agent-run completion in simple mode."""

from unittest.mock import MagicMock, patch

import server_simple


def test_complete_agent_run_interrupted_status():
    server_simple._run_id_by_thread["thread-int"] = "run-int"
    with patch("server_simple.httpx.patch") as mock_patch:
        mock_patch.return_value = MagicMock(raise_for_status=lambda: None)
        server_simple._complete_agent_run(
            thread_id="thread-int",
            success=True,
            result_text="Task interrupted. Send a new message to continue.",
            tool_calls=[],
            duration_seconds=3.5,
            run_status="interrupted",
        )
    body = mock_patch.call_args.kwargs["json"]
    assert body["status"] == "interrupted"
    assert body["output_summary"].startswith("Task interrupted")


def test_complete_agent_run_failed_when_not_interrupted():
    server_simple._run_id_by_thread["thread-fail"] = "run-fail"
    with patch("server_simple.httpx.patch") as mock_patch:
        mock_patch.return_value = MagicMock(raise_for_status=lambda: None)
        server_simple._complete_agent_run(
            thread_id="thread-fail",
            success=False,
            result_text="boom",
            tool_calls=[],
            duration_seconds=1.0,
        )
    body = mock_patch.call_args.kwargs["json"]
    assert body["status"] == "failed"
