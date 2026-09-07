from unittest.mock import MagicMock, patch

import server_simple


def test_finalize_running_rows_posts_internal_endpoint():
    server_simple._team_identity_by_thread["thread-z"] = ("pilot", "SRE")
    with patch("server_simple.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(raise_for_status=lambda: None)
        server_simple._finalize_running_rows_for_thread("thread-z")
    url = mock_post.call_args.args[0]
    assert url.endswith("/api/v1/internal/agent-runs/finalize-running-for-thread")
    body = mock_post.call_args.kwargs["json"]
    assert body["correlation_id"] == "thread-z"
    assert body["org_id"] == "pilot"
    assert body["team_node_id"] == "SRE"
    assert body["status"] == "interrupted"
    assert body["error_message"] == "Superseded by new turn"
    assert mock_post.call_args.kwargs["headers"] == server_simple._INTERNAL_HEADERS


def test_finalize_running_rows_swallows_http_errors():
    server_simple._team_identity_by_thread["thread-z"] = ("pilot", "SRE")
    with patch("server_simple.httpx.post") as mock_post:
        mock_post.side_effect = Exception("down")
        server_simple._finalize_running_rows_for_thread("thread-z")  # must not raise
