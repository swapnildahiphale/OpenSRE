"""Tests for GET /internal/episodes/{thread_id}/nudge-context."""

from unittest.mock import MagicMock

import pytest
import server_simple
from fastapi.testclient import TestClient
from memory.models import Episode


@pytest.fixture
def client():
    return TestClient(server_simple.app)


@pytest.fixture(autouse=True)
def clear_thread_state():
    server_simple._background_tasks.clear()
    server_simple._run_id_by_thread.clear()
    yield
    server_simple._background_tasks.clear()
    server_simple._run_id_by_thread.clear()


def test_nudge_context_empty_defaults_when_no_episode(client, monkeypatch):
    store = MagicMock()
    store.get_by_correlation.return_value = None
    monkeypatch.setattr(server_simple, "EpisodeStore", lambda: store)

    resp = client.get("/internal/episodes/thread-missing/nudge-context")
    assert resp.status_code == 200
    assert resp.json() == {
        "summary": None,
        "root_cause": None,
        "recommended_actions": [],
        "has_active_run": False,
    }
    store.get_by_correlation.assert_called_once_with("thread-missing")


def test_nudge_context_returns_episode_fields(client, monkeypatch):
    ep = Episode(
        episode_id="e1",
        correlation_id="thread-1",
        summary="checkout slow",
        root_cause="redis",
        recommended_actions=["restart redis", "check pool"],
    )
    store = MagicMock()
    store.get_by_correlation.return_value = ep
    monkeypatch.setattr(server_simple, "EpisodeStore", lambda: store)

    resp = client.get("/internal/episodes/thread-1/nudge-context")
    assert resp.status_code == 200
    assert resp.json() == {
        "summary": "checkout slow",
        "root_cause": "redis",
        "recommended_actions": ["restart redis", "check pool"],
        "has_active_run": False,
    }


def test_nudge_context_has_active_run_true(client, monkeypatch):
    store = MagicMock()
    store.get_by_correlation.return_value = None
    monkeypatch.setattr(server_simple, "EpisodeStore", lambda: store)
    # Warm BG session alone must NOT count as active (would block nudges forever).
    server_simple._background_tasks["thread-busy"] = MagicMock()
    server_simple._run_id_by_thread["thread-busy"] = "run-in-flight"

    resp = client.get("/internal/episodes/thread-busy/nudge-context")
    assert resp.status_code == 200
    assert resp.json()["has_active_run"] is True


def test_nudge_context_warm_session_not_active_run(client, monkeypatch):
    store = MagicMock()
    store.get_by_correlation.return_value = None
    monkeypatch.setattr(server_simple, "EpisodeStore", lambda: store)
    server_simple._background_tasks["thread-warm"] = MagicMock()

    resp = client.get("/internal/episodes/thread-warm/nudge-context")
    assert resp.status_code == 200
    assert resp.json()["has_active_run"] is False


def test_abandon_episode_sets_resolution_status(client, monkeypatch):
    ep = Episode(
        episode_id="e1",
        correlation_id="thread-abandon",
        summary="latency",
        resolution_status="open",
    )
    store = MagicMock()
    store.get_by_correlation.return_value = ep
    store.upsert_episode = MagicMock()
    monkeypatch.setattr(server_simple, "EpisodeStore", lambda: store)

    resp = client.post("/internal/episodes/thread-abandon/abandon")
    assert resp.status_code == 200
    assert resp.json()["resolution_status"] == "abandoned"
    assert ep.resolution_status == "abandoned"
    store.upsert_episode.assert_called_once_with(ep)


def test_abandon_episode_noop_when_missing(client, monkeypatch):
    store = MagicMock()
    store.get_by_correlation.return_value = None
    store.upsert_episode = MagicMock()
    monkeypatch.setattr(server_simple, "EpisodeStore", lambda: store)

    resp = client.post("/internal/episodes/thread-gone/abandon")
    assert resp.status_code == 200
    assert resp.json() == {"correlation_id": "thread-gone", "resolution_status": None}
    store.upsert_episode.assert_not_called()
