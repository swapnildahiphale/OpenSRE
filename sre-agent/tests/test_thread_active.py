"""Tests for GET /threads/{thread_id}/active."""

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
    yield
    server_simple._background_tasks.clear()
    server_simple._active_sessions.clear()


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
