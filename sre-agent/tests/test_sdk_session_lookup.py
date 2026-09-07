import asyncio
from unittest.mock import MagicMock, patch

import pytest
import server_simple


@pytest.fixture(autouse=True)
def clear_spawn_state():
    server_simple._background_tasks.clear()
    server_simple._message_queues.clear()
    server_simple._response_queues.clear()
    server_simple._team_identity_by_thread.clear()
    yield
    server_simple._background_tasks.clear()
    server_simple._message_queues.clear()
    server_simple._response_queues.clear()
    server_simple._team_identity_by_thread.clear()


def test_lookup_latest_sdk_session_id_gets_expected_query():
    server_simple._team_identity_by_thread["thread-z"] = ("pilot", "SRE")
    with patch("server_simple.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            raise_for_status=lambda: None,
            json=lambda: {"sdk_session_id": "sess-db"},
        )
        sid = server_simple._lookup_latest_sdk_session_id("thread-z")
    url = (
        mock_get.call_args.args[0]
        if mock_get.call_args.args
        else mock_get.call_args.kwargs.get("url")
    )
    assert url.endswith("/api/v1/internal/agent-runs/latest-sdk-session")
    assert mock_get.call_args.kwargs["params"] == {
        "correlation_id": "thread-z",
        "org_id": "pilot",
        "team_node_id": "SRE",
    }
    assert mock_get.call_args.kwargs["headers"] == server_simple._INTERNAL_HEADERS
    assert sid == "sess-db"


def test_lookup_latest_sdk_session_id_none_on_null_and_error():
    server_simple._team_identity_by_thread["thread-z"] = ("pilot", "SRE")
    with patch("server_simple.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            raise_for_status=lambda: None,
            json=lambda: {"sdk_session_id": None},
        )
        assert server_simple._lookup_latest_sdk_session_id("thread-z") is None
    with patch("server_simple.httpx.get") as mock_get:
        mock_get.side_effect = Exception("down")
        assert server_simple._lookup_latest_sdk_session_id("thread-z") is None


def test_ensure_background_task_looks_up_when_resume_omitted(monkeypatch):
    captured = {}

    async def fake_bg(thread_id, resume_session_id=None):
        captured["resume"] = resume_session_id

    monkeypatch.setattr(server_simple, "agent_background_task", fake_bg)
    monkeypatch.setattr(
        server_simple, "_lookup_latest_sdk_session_id", lambda tid: "sess-from-db"
    )
    asyncio.run(
        server_simple._ensure_background_task("thread-cold", resume_session_id=None)
    )
    assert captured["resume"] == "sess-from-db"


def test_ensure_background_task_client_resume_skips_lookup(monkeypatch):
    captured = {}
    called = []

    async def fake_bg(thread_id, resume_session_id=None):
        captured["resume"] = resume_session_id

    monkeypatch.setattr(server_simple, "agent_background_task", fake_bg)
    monkeypatch.setattr(
        server_simple,
        "_lookup_latest_sdk_session_id",
        lambda tid: called.append(tid) or "sess-from-db",
    )
    asyncio.run(
        server_simple._ensure_background_task(
            "thread-cold", resume_session_id="sess-client"
        )
    )
    assert captured["resume"] == "sess-client"
    assert called == []


def test_ensure_background_task_warm_skips_lookup(monkeypatch):
    called = []
    server_simple._background_tasks["thread-warm"] = MagicMock()
    monkeypatch.setattr(
        server_simple,
        "_lookup_latest_sdk_session_id",
        lambda tid: called.append(tid) or "x",
    )
    asyncio.run(
        server_simple._ensure_background_task("thread-warm", resume_session_id=None)
    )
    assert called == []


def test_start_interactive_session_falls_back_when_resume_fails(monkeypatch):
    starts = []

    class FakeSession:
        def __init__(self, thread_id, team_config=None, resume=None):
            self.thread_id = thread_id
            self.resume = resume
            self.client = object()
            self.session_id = None

        async def start(self):
            starts.append(self.resume)
            if self.resume:
                raise RuntimeError("session file not found")

        async def cleanup(self):
            self.client = None

    monkeypatch.setattr("agent.InteractiveAgentSession", FakeSession)
    session = asyncio.run(
        server_simple._start_interactive_session("t1", None, "sess-gone")
    )
    assert session.resume is None
    assert starts == ["sess-gone", None]


def test_start_interactive_session_reraises_when_no_resume(monkeypatch):
    class FakeSession:
        def __init__(self, thread_id, team_config=None, resume=None):
            self.resume = resume
            self.client = None

        async def start(self):
            raise RuntimeError("anthropic down")

        async def cleanup(self):
            return None

    monkeypatch.setattr("agent.InteractiveAgentSession", FakeSession)
    with pytest.raises(RuntimeError, match="anthropic down"):
        asyncio.run(server_simple._start_interactive_session("t1", None, None))
