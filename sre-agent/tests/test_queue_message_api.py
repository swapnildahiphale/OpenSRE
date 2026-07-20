from unittest.mock import MagicMock

import pytest
import server_simple as srv
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(srv.app)


def test_queue_message_404_unknown_thread(client):
    r = client.post("/threads/unknown/queue-message", json={"text": "hi"})
    assert r.status_code == 404


def test_queue_message_409_not_executing(client):
    mock_session = MagicMock()
    mock_session.is_running = False
    mock_session.enqueue_message = MagicMock()
    srv._active_sessions["t1"] = mock_session
    try:
        r = client.post("/threads/t1/queue-message", json={"text": "hi"})
        assert r.status_code == 409
    finally:
        srv._active_sessions.pop("t1", None)


def test_queue_message_200(client):
    mock_session = MagicMock()
    mock_session.is_running = True
    mock_session.enqueue_message.return_value = 1
    srv._active_sessions["t1"] = mock_session
    srv._response_queues["t1"] = __import__("asyncio").Queue()
    try:
        r = client.post("/threads/t1/queue-message", json={"text": "check redis"})
        assert r.status_code == 200
        assert r.json()["pending_count"] == 1
        mock_session.enqueue_message.assert_called_once_with("check redis")
    finally:
        srv._active_sessions.pop("t1", None)
        srv._response_queues.pop("t1", None)
