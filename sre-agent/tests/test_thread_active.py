"""Tests for GET /threads/{thread_id}/active."""

import asyncio
from unittest.mock import MagicMock

import pytest
import server_simple
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(server_simple.app)


@pytest.fixture(autouse=True)
def clear_thread_state():
    server_simple._background_tasks.clear()
    server_simple._active_sessions.clear()
    server_simple._message_queues.clear()
    server_simple._response_queues.clear()
    yield
    server_simple._background_tasks.clear()
    server_simple._active_sessions.clear()
    server_simple._message_queues.clear()
    server_simple._response_queues.clear()


def test_thread_active_false_when_unknown(client):
    resp = client.get("/threads/thread-missing/active")
    assert resp.status_code == 200
    assert resp.json() == {"active": False, "sdk_session_id": None}


def test_thread_active_true_when_background_task_exists(client):
    server_simple._background_tasks["thread-1"] = MagicMock()
    session = MagicMock()
    session.session_id = "sess-live"
    server_simple._active_sessions["thread-1"] = session

    resp = client.get("/threads/thread-1/active")
    assert resp.status_code == 200
    assert resp.json() == {"active": True, "sdk_session_id": "sess-live"}


class _StubSession:
    def __init__(self, **kwargs):
        self.client = None
        self.session_id = None

    async def start(self):
        return None

    async def cleanup(self):
        return None


def test_background_task_finally_removes_thread_from_active_map(monkeypatch):
    monkeypatch.setattr("agent.InteractiveAgentSession", _StubSession)
    thread_id = "thread-finally"

    async def launch():
        q = asyncio.Queue()
        rq = asyncio.Queue()
        server_simple._message_queues[thread_id] = q
        server_simple._response_queues[thread_id] = rq
        t = asyncio.create_task(server_simple.agent_background_task(thread_id))
        server_simple._background_tasks[thread_id] = t
        await q.put(None)  # shutdown signal
        await t

    asyncio.run(launch())
    assert thread_id not in server_simple._background_tasks
    assert thread_id not in server_simple._message_queues
    assert thread_id not in server_simple._response_queues
