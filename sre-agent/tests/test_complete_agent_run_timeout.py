"""Tests for timeout agent-run completion in simple mode."""

from unittest.mock import MagicMock, patch

import server_simple


def test_complete_agent_run_timeout_status():
    server_simple._run_id_by_thread["thread-to"] = "run-to"
    with patch("server_simple.httpx.patch") as mock_patch:
        mock_patch.return_value = MagicMock(raise_for_status=lambda: None)
        server_simple._complete_agent_run(
            thread_id="thread-to",
            success=False,
            result_text="",
            tool_calls=[],
            duration_seconds=600.0,
            run_status="timeout",
            error_message="Investigation stopped after 10 minutes (time limit).",
        )
    body = mock_patch.call_args.kwargs["json"]
    assert body["status"] == "timeout"
    assert "time limit" in body["error_message"]


def test_finalize_investigation_passes_timeout_error_message():
    server_simple._run_id_by_thread["thread-fin"] = "run-fin"
    with patch("server_simple.httpx.patch") as mock_patch, patch(
        "server_simple._il.finalize_investigation"
    ):
        mock_patch.return_value = MagicMock(raise_for_status=lambda: None)
        server_simple.finalize_investigation(
            thread_id="thread-fin",
            prompt="investigate",
            result_text="",
            success=False,
            tool_calls=[],
            duration_seconds=120.0,
            run_status="timeout",
            error_message="Investigation stopped after 2 minutes (time limit).",
        )
    body = mock_patch.call_args.kwargs["json"]
    assert body["status"] == "timeout"
    assert body["error_message"].startswith("Investigation stopped")
