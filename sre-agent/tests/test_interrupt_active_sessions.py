"""Tests for /interrupt wiring in simple mode."""

from unittest.mock import MagicMock

import pytest
import server_simple
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(server_simple.app)


@pytest.fixture(autouse=True)
def clear_active_sessions():
    server_simple._active_sessions.clear()
    yield
    server_simple._active_sessions.clear()


def test_interrupt_404_when_no_active_session(client):
    resp = client.post("/interrupt", json={"thread_id": "missing-thread"})
    assert resp.status_code == 404


def test_interrupt_drains_session_generator(client):
    drained = []

    async def fake_interrupt():
        drained.append(True)
        yield MagicMock()

    session = MagicMock()
    session.interrupt = fake_interrupt
    server_simple._active_sessions["thread-1"] = session

    resp = client.post("/interrupt", json={"thread_id": "thread-1"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "thread_id": "thread-1"}
    assert drained == [True]


def test_interrupt_returns_500_when_session_raises(client):
    async def failing_interrupt():
        if False:
            yield MagicMock()
        raise RuntimeError("sdk interrupt failed")

    session = MagicMock()
    session.interrupt = failing_interrupt
    server_simple._active_sessions["thread-2"] = session

    resp = client.post("/interrupt", json={"thread_id": "thread-2"})
    assert resp.status_code == 500
    assert "sdk interrupt failed" in resp.json()["detail"]
