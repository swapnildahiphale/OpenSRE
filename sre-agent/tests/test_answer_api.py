import asyncio

import pytest
import server_simple
from agent import InteractiveAgentSession
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(server_simple.app)


@pytest.fixture(autouse=True)
def clear_active_sessions():
    server_simple._active_sessions.clear()
    yield
    server_simple._active_sessions.clear()


def _session(thread_id: str, is_running: bool = False) -> InteractiveAgentSession:
    session = InteractiveAgentSession.__new__(InteractiveAgentSession)
    session.thread_id = thread_id
    session.is_running = is_running
    return session


def test_answer_returns_404_for_missing_thread(client):
    response = client.post(
        "/answer", json={"thread_id": "missing", "answers": {"q": "a"}}
    )

    assert response.status_code == 404


def test_answer_returns_409_for_idle_session(client):
    server_simple._active_sessions["idle"] = _session("idle")

    response = client.post(
        "/answer", json={"thread_id": "idle", "answers": {"q": "a"}}
    )

    assert response.status_code == 409


def test_answer_returns_409_for_running_session_without_pending_question(client):
    server_simple._active_sessions["running"] = _session("running", is_running=True)

    response = client.post(
        "/answer", json={"thread_id": "running", "answers": {"q": "a"}}
    )

    assert response.status_code == 409


def test_answer_delivers_to_running_session_with_pending_question(client):
    session = _session("pending", is_running=True)
    session._pending_answer_event = asyncio.Event()
    session._pending_answer = None
    server_simple._active_sessions["pending"] = session
    answers = {"question": "answer"}

    response = client.post("/answer", json={"thread_id": "pending", "answers": answers})

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "thread_id": "pending"}
    assert session._pending_answer == answers
    assert session._pending_answer_event.is_set()
