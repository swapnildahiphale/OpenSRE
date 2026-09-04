import os
from unittest.mock import MagicMock

import pytest

pytest.importorskip("neo4j")


def test_memory_stats_endpoint_shape():
    pytest.importorskip("neo4j")
    if not os.getenv("NEO4J_URI"):
        pytest.skip("needs Neo4j")
    import server_simple
    from fastapi.testclient import TestClient

    client = TestClient(server_simple.app)
    r = client.get("/memory/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "total_episodes" in body["result"]


def test_memory_overview_endpoint_shape():
    pytest.importorskip("neo4j")
    if not os.getenv("NEO4J_URI"):
        pytest.skip("needs Neo4j")
    import server_simple
    from fastapi.testclient import TestClient

    client = TestClient(server_simple.app)
    r = client.get("/memory/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    result = body["result"]
    for key in (
        "total_episodes",
        "resolved",
        "unresolved",
        "resolution_rate",
        "episodes_this_week",
        "issue_type_counts",
        "recent_episodes",
        "strategy_count",
        "latest_strategies",
    ):
        assert key in result


def test_reextract_calls_finalize_with_run_data(monkeypatch):
    import server_simple
    from fastapi.testclient import TestClient
    from memory.models import Episode

    ep = Episode(
        episode_id="e1",
        correlation_id="corr-1",
        agent_run_id="run-1",
        org_id="local",
        team_node_id="default",
        issue_type="db",
        extraction_status="failed",
        created_at="t",
        updated_at="t",
    )
    updated_ep = Episode(
        episode_id="e1",
        correlation_id="corr-1",
        agent_run_id="run-1",
        org_id="local",
        team_node_id="default",
        issue_type="db",
        extraction_status="ok",
        summary="fixed",
        created_at="t",
        updated_at="t2",
    )
    finalize_kwargs = {}

    def fake_finalize(**kwargs):
        finalize_kwargs.update(kwargs)

    def fake_get(url, headers=None, timeout=None):
        resp = MagicMock()
        if url.endswith("/tool-calls"):
            resp.is_success = True
            resp.json.return_value = {
                "tool_calls": [
                    {
                        "tool_name": "Skill",
                        "tool_input": {"skill": "memory-search"},
                        "tool_output": "found similar",
                    }
                ]
            }
        else:
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {
                "trigger_message": "checkout slow",
                "output_summary": "root cause was a missing index " * 5,
            }
        return resp

    class FakeStore:
        def __init__(self):
            self._call = 0

        def get_by_episode_id(self, episode_id, org_id, team_node_id):
            self._call += 1
            assert episode_id == "e1"
            assert org_id == "local"
            assert team_node_id == "default"
            if self._call == 1:
                return ep
            return updated_ep

    monkeypatch.setattr(server_simple, "_tenancy_from_request", lambda _r: ("local", "default"))
    monkeypatch.setattr(server_simple, "EpisodeStore", FakeStore)
    monkeypatch.setattr(server_simple._il, "finalize_investigation", fake_finalize)
    monkeypatch.setattr(server_simple.httpx, "get", fake_get)

    client = TestClient(server_simple.app)
    resp = client.post("/memory/episodes/e1/reextract")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["result"]["extraction_status"] == "ok"
    assert body["result"]["episode_id"] == "e1"
    assert finalize_kwargs["prompt"] == "checkout slow"
    assert "missing index" in finalize_kwargs["result_text"]
    assert finalize_kwargs["correlation_id"] == "corr-1"
    assert finalize_kwargs["agent_run_id"] == "run-1"
    assert finalize_kwargs["org_id"] == "local"
    assert finalize_kwargs["team_node_id"] == "default"
    assert len(finalize_kwargs["tool_calls"]) == 1
    assert finalize_kwargs["tool_calls"][0]["tool_name"] == "Skill"


def test_reextract_episode_not_found(monkeypatch):
    import server_simple
    from fastapi.testclient import TestClient

    class FakeStore:
        def get_by_episode_id(self, episode_id, org_id, team_node_id):
            return None

    monkeypatch.setattr(server_simple, "_tenancy_from_request", lambda _r: ("local", "default"))
    monkeypatch.setattr(server_simple, "EpisodeStore", FakeStore)

    client = TestClient(server_simple.app)
    resp = client.post("/memory/episodes/missing/reextract")

    assert resp.status_code == 404
    assert "episode not found" in resp.json()["detail"]


def test_reextract_no_agent_run_id(monkeypatch):
    import server_simple
    from fastapi.testclient import TestClient
    from memory.models import Episode

    ep = Episode(
        episode_id="e1",
        correlation_id="corr-1",
        agent_run_id=None,
        org_id="local",
        team_node_id="default",
        created_at="t",
        updated_at="t",
    )

    class FakeStore:
        def get_by_episode_id(self, episode_id, org_id, team_node_id):
            return ep

    monkeypatch.setattr(server_simple, "_tenancy_from_request", lambda _r: ("local", "default"))
    monkeypatch.setattr(server_simple, "EpisodeStore", FakeStore)

    client = TestClient(server_simple.app)
    resp = client.post("/memory/episodes/e1/reextract")

    assert resp.status_code == 409
    assert "no agent run" in resp.json()["detail"]
